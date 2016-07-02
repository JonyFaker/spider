import queue
import threading
import requests
from urllib.parse import urlparse
from bs4 import BeautifulSoup


class Route(object):
    def __init__(self):
        self.root = Node('/')

    def add(self, url, func):
        node = self.root

        parse_result = urlparse(url)
        urls = [url for url in parse_result.path.split('/') if url]
        print(urls)
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

        parse_result = urlparse(url)
        urls = parse_result.path[1:].split('/')
        i = 0
        while len(node.sub_node) > 0:
            if i == len(urls):
                break

            if urls[i] in node.sub_node:
                node = node.sub_node[urls[i]]

            i += 1
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
        return str(self.sub_node)


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
                    return parse_result.scheme + "://" + href_result.geturl()
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
        self.url_queue.put(Task('download', start_url))

    def route(self, url):
        print(url)

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
                self.r.search(task.url)()


if __name__ == '__main__':
    download = Download("http://www.baidu.com", None)
    download.start()
