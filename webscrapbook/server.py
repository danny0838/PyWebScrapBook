#!/usr/bin/env python3
"""Server backend of WebScrapBook toolkit.
"""
import os
import time
import webbrowser
from threading import Thread

# dependency
from werkzeug.serving import WSGIRequestHandler, make_server

# this package
from . import *
from . import Config
from .app import make_app
from .util import is_nullhost

def serve(root, **kwargs):
    config = Config()
    config.load(root)

    # set params
    host = config['server']['host'] or '127.0.0.1'
    port = config['server'].getint('port')
    ssl_on = config['server'].getboolean('ssl_on')
    ssl_key = config['server']['ssl_key']
    ssl_cert = config['server']['ssl_cert']
    scheme = 'https' if ssl_on else 'http'

    host2 = '[{}]'.format(host) if ':' in host else host
    host3 = 'localhost' if is_nullhost(host) else host2
    port2 = '' if (not ssl_on and port == 80) or (ssl_on and port == 443) else ':' + str(port)

    # start server
    print('WebScrapBook server starting up...')
    print('Document Root: {}'.format(os.path.abspath(root)))
    print('Listening on {scheme}://{host}:{port}'.format(
            scheme=scheme, host=host2, port=port))
    print('Hit Ctrl-C to shutdown.')

    WSGIRequestHandler.protocol_version = "HTTP/1.1"
    srv = make_server(
        host=host,
        port=port,
        app=make_app(root, config),
        threaded=True,
        processes=1,
        ssl_context=((ssl_cert, ssl_key) if ssl_cert and ssl_key
                else 'adhoc' if ssl_on else None),
        )
    thread = Thread(target=srv.serve_forever)
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
