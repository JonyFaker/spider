from urllib.parse import urlparse


class Route(object):
    def __init__(self):
        self.root = Node('/')

    def add(self, url, func):
        node = self.root
        print(node)

        parse_result = urlparse(url)
        print(parse_result.path)
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


class Spider(object):
    def __init__(self):
        self.r = Route()

    def route(self, url):
        print(url)

        def _deco(func):
            self.r.add(url, func)

            def __deco(*args, **kwargs):
                func(*args, **kwargs)

            return __deco

        return _deco

    def run(self):
        pass
