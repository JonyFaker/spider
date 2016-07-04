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
            node.sub_node[key] = Node(key, func)

        if len(urls[1:]) > 0:
            sub_node = node.sub_node.get(key)
            self._add(sub_node, urls[1:], func)

    def search(self, url):
        node = self.root
        args = {}

        urls = urlparse(url).path[1:].split('/')

        pattern_dict = collections.OrderedDict([
            ('int', '^<int:([a-zA-Z_]\w+)>$'),
            ('string', '^<string:([a-zA-Z_]\w+)>$'),
            ('float', '^<float:([a-zA-Z_]\w+)>$')
        ])

        i = 0
        while len(node.sub_node) > 0:
            if i == len(urls):
                break

            sub_url = urls[i]
            i += 1

            if sub_url in node.sub_node:
                node = node.sub_node[sub_url]
                continue

            

        if node is None:
            return None
        else:
            return node.func

    def __str__(self):
        return str(self.root.sub_node)


class Node(object):
    def __init__(self, name, func=None):
        self.name = name
        self.sub_node = {}
        self.func = func

    def add(self, node):
        self.sub_node[node.name] = node

    def __str__(self):
        return self.name + ' ' + str(self.sub_node)


class Task(object):
    def __init__(self, type, url=None):
        self.type = type
        self.url = url
        self.result = None


class Download(threading.Thread):
    def __init__(self, url, spider):
        super().__init__()
        self.url = url
        self.spider = spider

    def run(self):
        r = requests.get(self.url)
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

            if self.spider is not None:
                for url in [convert(a['href']) for a in soup.select('a') if a['href'] != 'javascript:;']:
                    task = Task("parse", url)
                    task.result = r.text
                    self.spider.task_queue(task)


class Spider(object):
    def __init__(self, start_url):
        self.r = Route()
        self.task_queue = queue.Queue()
        self.task_queue.put(Task('download', start_url))

    def route(self, url):

        def _deco(func):
            self.r.add(url, func)

            def __deco(*args, **kwargs):
                func(*args, **kwargs)

            return __deco

        return _deco

    def run(self):
        while True:
            task = self.task_queue.get()

            if task.type == 'download':
                Download(task.url, self).start()
            elif task.type == 'parse':
                func = self.r.search(task.url)
                if func is not None:
                    func()
spider = Spider('')

@spider.route('/abc/<int:id>')
def test():
    print(test)

if __name__ == '__main__':
    spider.r.search('/abc/123')()
    print()
    spider.r.search('/abc/def')()
