import queue
import collections
import threading
import requests
import re
import redis
import pickle
import time
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

    def get_func(self, url):
        node = self.root
        args = {}
        if type(url) != type(''):
            return None, args
        urls = [url for url in urlparse(url).path.split('/') if url != '']

        i = 0
        while len(node.sub_node) > 0 and len(urls) > i:
            sub_url = urls[i]
            i += 1
            for item in node.sub_node.values():
                if item.param_type == 'base':
                    if item.name != sub_url:
                        continue
                else:
                    value = item.get_value(sub_url)
                    if value is None:
                        continue
                    args[item.param_name] = value
                node = item
                break
            else:
                node = None
                break

        if node is None or i < len(urls):
            return None, args
        else:
            return node.func, args

    def search(self, url):
        func, args = self.get_func(url)
        if func is None:
            return False
        else:
            return True

    def __str__(self):
        return str(self.root.sub_node)


param_re = re.compile('<(int|string|float):([a-zA-Z_]\w+)>')


class Node(object):
    def __init__(self, name, func=None):
        self.name = name
        self.sub_node = {}
        self.func = func

        result = param_re.match(name)
        if result:
            self.param_type = result.group(1)
            self.param_name = result.group(2)

            if self.param_type == 'int':
                self.pattern = re.sub('<int:\w+>', '([+,-]{0,1}\d+)', self.name)
            elif self.param_type == 'string':
                self.pattern = re.sub('<string:\w+>', '\w+', self.name)
            elif self.param_type == 'float':
                self.pattern = re.sub('<float:\w+>', '([+,-]{0,1}\d+.{0,1}\d+)', self.name)
        else:
            self.param_type = 'base'

    def add(self, node):
        self.sub_node[node.name] = node

    def get_value(self, sub_url):
        result = re.match(self.pattern, sub_url)

        funcs = {
            'int': lambda result: int(result.group(1)),
            'string': lambda result: result.group(1),
            'float': lambda result: float(result.group(1))
        }

        if result is None:
            return None
        return funcs[self.param_type](result)

    def __str__(self):
        return '[' + self.name + ' ' + str(self.sub_node) + ']'


class Response(object):
    def __init__(self):
        self.req = {}

    def get_response(self):
        return self.req[threading.current_thread().ident]

    def add_response(self, pid, req):
        self.req[pid] = req


response = Response()


class Worker(threading.Thread):
    def __init__(self, spider):
        super().__init__()
        self.spider = spider

    def run(self):
        while True:
            if self.spider is None:
                # 记得错误处理
                return

            tmp = self.spider.pop_task()
            if tmp is None:
                continue
            task = pickle.loads(tmp)
            url = task.url

            # todo 标记该网页已经被爬过
            self.spider.redis.set(url, True)
            r = requests.get(url)
            if r.status_code != 200:
                pass

            soup = BeautifulSoup(r.text, "lxml")
            for a in soup.select('a'):
                href = a.get('href')
                sub_url = self.convert(href, url)
                if type(sub_url) != type('') or not sub_url.startswith('http'):
                    continue

                # 暂时放弃https的页面
                if sub_url.startswith('https'):
                    continue

                # 这个地方还需要修改，去除不必要的url，从route里面找
                # if not self.spider.r.search(sub_url):
                #     continue
                if self.spider.redis.exists(sub_url) and not self.spider.redis.get(sub_url):
                    continue

                sub_task = Task(sub_url)
                self.spider.push_task(sub_task)

            func, args = self.spider.r.get_func(url)
            if func is None:
                continue
            response.add_response(threading.get_ident(), r)
            func(**args)

    def convert(self, href, url):
        parse_result = urlparse(url)
        href_result = urlparse(href)

        if parse_result.netloc != href_result.netloc:
            return None

        if href_result.scheme != '':
            return href_result.geturl()
        elif href_result.netloc != '':
            return parse_result.scheme + "://" + href_result.geturl().replace('//', '')
        else:
            return parse_result.scheme + "://" + parse_result.netloc + href_result.geturl()


class Task(object):
    def __init__(self, url, type=None):
        self.type = type
        self.url = url


class Config(object):
    def __init__(self):
        self.config = {
            'worker': 5
        }

    def get(self, key):
        return self.config.get(key)


class Spider(object):
    def __init__(self, start_url):
        self.r = Route()
        self.redis = redis.Redis(host='localhost', port=6379, db=0)
        self.redis.flushall()

        task = Task(start_url)
        self.push_task(task)

        self.config = Config()

    def route(self, url):
        def _deco(func):
            self.r.add(url, func)

        return _deco

    def run(self):
        for i in range(self.config.get('worker')):
            Worker(self).start()

    def push_task(self, task):
        mutex = threading.Lock()
        mutex.acquire()
        if self.r.search(task.url):
            self.redis.rpush('task_queue', pickle.dumps(task))
        else:
            self.redis.lpush('task_queue', pickle.dumps(task))
        self.redis.set(task.url, False)
        mutex.release()

    def pop_task(self):
        return self.redis.rpop('task_queue')


spider = Spider('http://www.mahua.com/xiaohua/1628976.htm')


@spider.route('/xiaohua/<int:id>.htm')
def test(id):
    result = response.get_response()
    soup = BeautifulSoup(result.text, "lxml")
    now = time.strftime('[%Y-%m-%d %H:%M:%S]',time.localtime(time.time()))
    print(now, id, threading.current_thread().ident, soup.select('h1'))
    with open('log.txt', 'a') as f:
        f.write('{0} {1} {2} {3}\n'.format(now, id, threading.current_thread().ident, soup.select('h1')))


# test main
if __name__ == '__main__':
    spider.run()
