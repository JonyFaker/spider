import queue
import collections
import threading
import requests
import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup

int_number = re.compile('^[+,1]{0,1}\d+')
float_number = re.compile('^[+,-]{0,1}\d+.{0,1}\d+$')


class Route(object):
    def __init__(self):
        self.root = Node('/')

    def add(self, url, func):
        node = self.root

        parse_result = urlparse(url)
        urls = [url for url in parse_result.path.split('/') if url]
        if len(urls) == 0:
            node.func = func
        else:
            self._add(node, urls, func)

    def _add(self, node, urls, func):
        key = urls[0]
        keys = node.sub_node.keys()
        if key not in keys:
            node.sub_node[key] = Node(key, None)

        if len(urls[1:]) > 0:
            sub_node = node.sub_node.get(key)
            self._add(sub_node, urls[1:], func)
        else:
            node.sub_node[key].func = func

    def search(self, url):
        node = self.root
        args = {}

        urls = urlparse(url).path[1:].split('/')

        i = 0
        while len(node.sub_node) > 0 and len(urls) > i:
            sub_url = urls[i]
            i += 1

            for item in node.sub_node.values():
                if item == sub_url:
                    node = item
                    if item.param_type == 'int':
                        args[item.param_name] = int(sub_url)
                    elif item.param_type == 'string':
                        args[item.param_name] = sub_url
                    elif item.param_type == 'float':
                        args[item.param_name] = float(sub_url)
                    break
            else:
                node = None
                break
        if node is None or i < len(urls):
            return None, args
        else:
            return node.func, args

    def __str__(self):
        return str(self.root.sub_node)


param_re = re.compile('^<(int|string|float):([a-zA-Z_]\w+)>$')


class Node(object):
    def __init__(self, name, func=None):
        self.name = name
        self.sub_node = {}
        self.func = func

        result = param_re.match(name)
        if result:
            self.param_type = result.group(1)
            self.param_name = result.group(2)
        else:
            self.param_type = 'base'

    def add(self, node):
        self.sub_node[node.name] = node

    def __str__(self):
        return '[' + self.name + ' ' + str(self.sub_node) + ']'


    def __eq__(self, other):
        if self.param_type == 'base':
            return other == self.name
        elif self.param_type == 'string':
            return True
        elif self.param_type == 'int':
            return (True if int_number.match(other) else False)
        elif self.param_type == 'float':
            return (True if float_number.match(other) else False)
        else:
            return False


class Download(threading.Thread):
    def __init__(self, task):
        super().__init__()
        self.task = task

    def run(self):
        print(self.task.url)
        r = requests.get(self.task.url)
        if r.status_code == 200:
            parse_result = urlparse(r.url)
            soup = BeautifulSoup(r.text, "lxml")

            def convert(href):
                href_result = urlparse(href)

                if href_result.scheme != '':
                    return href_result.geturl()
                elif href_result.netloc != '':
                    return parse_result.scheme + "://" + href_result.geturl().replace('//', '')
                else:
                    return parse_result.scheme + "://" + parse_result.netloc + href_result.geturl()

            if self.task.spider is not None:
                for url in [convert(a['href']) for a in soup.select('a') if a['href'] != 'javascript:;']:
                    task = Task("parse", url)
                    task.result = r
                    self.task.spider.task_queue(task)


class Request(object):
    def __init__(self):
        self.req = {}

    def get_request(self):
        return self.req[threading.current_thread().ident]

    def add_request(self, pid, req):
        self.req[pid] = req

request = Request()

class Parser(threading.Thread):
    def __init__(self, task):
        super().__init__()
        self.task = task

    def run(self):
        self.task.func(**self.args)

class Task(object):
    def __init__(self, type, url=None):
        self.type = type
        self.url = url
        self.result = None
        self.func = None
        self.args = None
        self.spider = None


class Spider(object):
    def __init__(self, start_url):
        self.r = Route()
        self.task_queue = queue.Queue()
        self.task_queue.put(Task('download', start_url))

    def route(self, url):
        def _deco(func):
            self.r.add(url, func)
        return _deco

    def run(self):
        while True:
            task = self.task_queue.get()

            if task.type == 'download':
                task.spider = self
                Download(task).start()
            elif task.type == 'parse':
                func, args = self.r.search(task.url)
                if func is not None:
                    task.func = func
                    task.args = args
                    p = Parser(task)
                    request.add_request(p.ident, task.result)
                    p.start()


spider = Spider('http://www.csdn.net/')


@spider.route('/news/detail/<int:id>')
def test(id):
    result = request.get_request()
    print(result)

if __name__ == '__main__':
    spider.run()
