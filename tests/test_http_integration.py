"""End-to-end Python wire tests with fake HTTP backends; no Docker required."""
import json
import sys
import threading
import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import dashboard_generator as dashboard
import load_generator as load


class FakeBackend(BaseHTTPRequestHandler):
    dashboard = None
    calls = []
    item_id = 0

    def log_message(self, *args):
        pass

    def reply(self, code, result):
        data = json.dumps(result).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == '/handlers':
            self.reply(200, [
                {'method': 'GET', 'route': '/health'},
                {'method': 'GET', 'route': '/metrics'},
                {'method': 'GET', 'route': '/handlers'},
                {'method': 'POST', 'route': '/items'},
                {'method': 'GET', 'route': '/items/{id}'},
                {'method': 'PUT', 'route': '/items/{id}'},
            ])
        elif self.path == '/api/datasources/uid/itmo-prometheus':
            self.reply(200, {'uid': 'itmo-prometheus', 'type': 'prometheus'})
        elif self.path == '/api/dashboards/uid/itmo-items-golden-signals':
            self.reply(200, {'dashboard': self.dashboard})
        elif self.path.startswith('/items/'):
            self.reply(404 if self.path.endswith('987654321') else 200, {'id': 1})
        else:
            self.reply(404, {'error': 'unknown'})

    def do_POST(self):
        n = int(self.headers.get('Content-Length', '0'))
        payload = json.loads(self.rfile.read(n) or b'{}')
        if self.path == '/api/dashboards/db':
            self.__class__.dashboard = payload['dashboard']
            self.__class__.calls.append((self.headers.get('Authorization'), payload))
            self.reply(200, {'status': 'success', 'uid': 'itmo-items-golden-signals',
                             'url': '/d/itmo-items-golden-signals'})
        elif self.path == '/items':
            if self.headers.get('X-Demo-Error') == '500':
                self.reply(500, {'error': 'demo'})
            elif payload.get('name') == '':
                self.reply(400, {'error': 'bad request'})
            else:
                self.__class__.item_id += 1
                self.reply(201, {'id': self.__class__.item_id, 'name': payload['name']})
        else:
            self.reply(404, {'error': 'unknown'})

    def do_PUT(self):
        self.reply(200, {'id': 1, 'name': 'new'})


@contextmanager
def server():
    httpd = ThreadingHTTPServer(('127.0.0.1', 0), FakeBackend)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{httpd.server_port}'
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


class HttpIntegrationTest(unittest.TestCase):
    def test_real_urllib_discovery_and_grafana_publish(self):
        FakeBackend.dashboard = None
        FakeBackend.calls = []
        with server() as url:
            handlers = dashboard.discover_handlers([url])
            self.assertEqual(len(handlers), 3)
            db = dashboard.build_dashboard(handlers)
            saved_url = dashboard.publish_dashboard(url, 'admin', 'demo', db)
        self.assertEqual(saved_url, url + '/d/itmo-items-golden-signals')
        self.assertEqual(len(FakeBackend.calls), 1)
        self.assertTrue(FakeBackend.calls[0][0].startswith('Basic '))
        self.assertEqual(len(FakeBackend.calls[0][1]['dashboard']['panels']), 9)

    def test_real_urllib_handles_500_and_404_without_crashing(self):
        with server() as url:
            load1 = load.Load([url, url + '/alternate'])
            status, body = load1.send(url, 'POST', '/items', {'name': 'synthetic'}, synthetic_500=True)
            self.assertEqual(status, 500)
            status, body = load1.send(url, 'GET', '/items/987654321')
            self.assertEqual(status, 404)
            status, body = load1.send(url, 'POST', '/items', {'name': 'hello'})
            self.assertEqual(status, 201)
            self.assertIsInstance(body['id'], int)


if __name__ == '__main__':
    unittest.main()
