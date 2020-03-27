#!/usr/bin/env python3
"""Server backend of WebScrapBook toolkit.
"""
import os
import time
from ipaddress import IPv6Address, AddressValueError
import webbrowser
from threading import Thread

# dependency
import bottle

# this package
from . import *
from .app import init_app


class WSBServer(bottle.ServerAdapter):
    """Tweaked from bottle.WSGIRefServer

    - Remove starting message of bottle.
    - Support of SSL.
    - Support multi-threading.
    """
    def run(self, app): # pragma: no cover
        #! we have bypassed bottle
        self.quiet = False

        from wsgiref.handlers import BaseHandler
        from wsgiref.simple_server import WSGIRequestHandler, WSGIServer
        import multiprocessing.pool
        import socket
        import ssl

        class FixedHandler(WSGIRequestHandler):
            def address_string(self): # Prevent reverse DNS lookups please.
                return self.client_address[0]
            def log_request(*args, **kw):
                if not self.quiet:
                    return WSGIRequestHandler.log_request(*args, **kw)

        class ThreadPoolWSGIServer(WSGIServer):
            """WSGI-compliant HTTP server.  Dispatches requests to a pool of threads.
            
            ref: https://github.com/RonRothman/mtwsgi
            """

            def __init__(self, thread_count=None, *args, **kwargs):
                """If 'thread_count' == None, we'll use multiprocessing.cpu_count() threads."""
                WSGIServer.__init__(self, *args, **kwargs)
                self.thread_count = thread_count
                self.pool = multiprocessing.pool.ThreadPool(self.thread_count)

            # Inspired by SocketServer.ThreadingMixIn.
            def process_request_thread(self, request, client_address):
                try:
                    self.finish_request(request, client_address)
                except:
                    self.handle_error(request, client_address)
                finally:
                    self.shutdown_request(request)

            def process_request(self, request, client_address):
                self.pool.apply_async(self.process_request_thread, args=(request, client_address))


        def make_server(host, port, app, server_cls, handler_class, thread_count=None):
            '''Create a new WSGI server listening on `host` and `port` for `app`'''
            httpd = server_cls(thread_count, (host, port), handler_class)
            httpd.set_app(app)
            return httpd

        BaseHandler.http_version = self.options.get('http_version', "1.1")
        handler_cls = self.options.get('handler_class', FixedHandler)
        server_cls  = self.options.get('server_class', ThreadPoolWSGIServer)

        if ':' in self.host: # Fix wsgiref for IPv6 addresses.
            if getattr(server_cls, 'address_family') == socket.AF_INET:
                class server_cls(server_cls):
                    address_family = socket.AF_INET6

        srv = make_server(self.host, self.port, app, server_cls, handler_cls, self.options.get('threads') or None)

        #! add SSL support here
        if self.options.get('ssl_on'):
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(
                certfile=self.options.get('ssl_cert'),
                keyfile=self.options.get('ssl_key'),
                password=self.options.get('ssl_pw'),
                )
            srv.socket = context.wrap_socket(srv.socket,
                    server_side=True,
                    )
            srv.base_environ['HTTPS'] = 'on'

        srv.serve_forever()


def serve(root, **kwargs):
    # switch to the specified directory and reload configs
    os.chdir(root)
    config.load()

    # set params
    host = config['server']['host'] or ''
    port = config['server'].getint('port')
    ssl_on = config['server'].getboolean('ssl_on')
    ssl_key = config['server']['ssl_key']
    ssl_cert = config['server']['ssl_cert']
    threads = config['server'].getint('threads')
    scheme = 'https' if ssl_on else 'http'

    host2 = host3 = '[{}]'.format(host) if ':' in host else host
    try:
        if host == '0.0.0.0' or IPv6Address(host) == IPv6Address('::'):
            host3 = 'localhost'
    except AddressValueError:
        pass
    port2 = '' if (not ssl_on and port == 80) or (ssl_on and port == 443) else ':' + str(port)

    # start server
    print('WebScrapBook server starting up...')
    print('Document Root: {}'.format(os.path.abspath(root)))
    print('Listening on {scheme}://{host}:{port}'.format(
            scheme=scheme, host=host2, port=port))
    print('Hit Ctrl-C to shutdown.')

    thread = Thread(target=init_app().run, kwargs={
        'host': host,
        'port': port,
        'server': WSBServer,
        'ssl_on': ssl_on,
        'ssl_key': ssl_key,
        'ssl_cert': ssl_cert,
        'threads': threads,
        'quiet': True,  # bypass Bottle init message, will be reset in server
        })
    thread.daemon = True
    thread.start()

    # launch the browser
    if config['server'].getboolean('browse'):
        base = config['app']['base'].rstrip('/')
        index = config['browser']['index'].lstrip('/')
        path = base + (('/' + index) if index else '')

        url = '{scheme}://{host}{port}{path}'.format(
                scheme=scheme,
                host=host3,
                port=port2,
                path=path,
                )

        browser = webbrowser.get(config['browser']['command'] or None)

        print('Launching browser at {url} ...'.format(url=url))
        thread = Thread(target=browser.open, args=[url])
        thread.daemon = True
        thread.start()

    try:
        while True: time.sleep(100)
    except (KeyboardInterrupt, SystemExit):
        print('Keyboard interrupt received, shutting down server.')


def main():
    serve(".")


if __name__ == '__main__':
    main()
