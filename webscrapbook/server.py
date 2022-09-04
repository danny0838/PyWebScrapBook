"""Server backend of WebScrapBook toolkit.
"""
import os
import webbrowser
from threading import Thread

from werkzeug.serving import WSGIRequestHandler, make_server

from . import Config
from .app import make_app
from .util import is_nullhost


def serve(root, browse=None):
    config = Config()
    config.load(root)

    # set params
    host = config['server']['host'] or '127.0.0.1'
    port = config['server']['port']
    ssl_on = config['server']['ssl_on']
    ssl_key = config['server']['ssl_key'] if ssl_on else None
    ssl_cert = config['server']['ssl_cert'] if ssl_on else None
    scheme = 'https' if ssl_on else 'http'

    if ssl_key:
        ssl_key = os.path.abspath(os.path.join(root, ssl_key))

    if ssl_cert:
        ssl_cert = os.path.abspath(os.path.join(root, ssl_cert))

    host2 = f'[{host}]' if ':' in host else host
    host3 = 'localhost' if is_nullhost(host) else host2
    port2 = '' if (not ssl_on and port == 80) or (ssl_on and port == 443) else ':' + str(port)

    # prepare server
    srv = make_server(
        host=host,
        port=port,
        app=make_app(root, config),
        threaded=True,
        processes=1,
        ssl_context=((ssl_cert, ssl_key) if ssl_cert and ssl_key
                     else 'adhoc' if ssl_on else None),
        request_handler=RequestHandler,
    )

    srv.log('info', 'WebScrapBook server starting up...')
    srv.log('info', f'Document Root: {os.path.abspath(root)}')
    srv.log('info', f'Listening on {scheme}://{host2}:{port}')
    srv.log('info', 'Hit Ctrl-C to shutdown.')

    # launch browser
    if browse is None:
        browse = config['server']['browse']

    if browse:
        index = config['app']['index'].lstrip('/')
        path = ('/' + index) if index else ''
        url = f'{scheme}://{host3}{port2}{path}'
        srv.log('info', f'Launching browser at {url} ...')
        try:
            browser = webbrowser.get(config['browser']['command'] or None)
        except webbrowser.Error as exc:
            srv.log('error', f'Error: {exc}')
        else:
            thread = Thread(target=browser.open, args=[url], daemon=True)
            thread.start()

    # start server
    srv.serve_forever()


class RequestHandler(WSGIRequestHandler):
    protocol_version = 'HTTP/1.1'
