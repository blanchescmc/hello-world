import json
import tempfile
import threading
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import server

class QualificationTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.original_db = server.DB
        server.DB = Path(self.folder.name) / 'test.sqlite3'
        server.initialize()

    def tearDown(self):
        server.DB = self.original_db
        self.folder.cleanup()

    def scan(self, tag, request_id=None):
        return server.check(tag, True, request_id or str(uuid.uuid4()))

    def test_three_successes_then_rejection_for_every_tag(self):
        for tag in server.SERIALS:
            self.assertEqual(server.check(tag)['count'], 0)
            results = [self.scan(tag) for _ in range(4)]
            self.assertEqual([r['eligible'] for r in results], [True, True, True, False])
            self.assertEqual([r['count'] for r in results], [1, 2, 3, 3])

    def test_reading_and_reinitializing_do_not_consume_or_reset(self):
        tag = server.SERIALS[0]
        self.scan(tag)
        server.initialize()
        for _ in range(3):
            self.assertEqual(server.check(tag)['count'], 1)

    def test_repeated_request_is_idempotent(self):
        tag = server.SERIALS[0]
        request_id = str(uuid.uuid4())
        first = self.scan(tag, request_id)
        self.assertEqual(self.scan(tag, request_id), first)
        self.assertEqual(server.check(tag)['count'], 1)
        with self.assertRaises(ValueError):
            self.scan(server.SERIALS[1], request_id)

    def test_concurrent_phones_cannot_exceed_limit(self):
        with ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(self.scan, [server.SERIALS[0]] * 12))
        self.assertEqual(sum(r['recorded'] for r in results), 3)
        self.assertEqual(server.check(server.SERIALS[0])['count'], 3)

    def test_unknown_tag_does_not_consume_approved_tags(self):
        self.assertFalse(self.scan('unknown')['eligible'])
        for tag in server.SERIALS:
            self.assertEqual(server.check(tag)['count'], 0)

    def test_http_routes_and_validation(self):
        http = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        thread = threading.Thread(target=http.serve_forever)
        thread.start()
        base = 'http://127.0.0.1:' + str(http.server_port)
        try:
            for path in ['/', '/styles.css', '/app.js', '/api/check?tag=' + server.SERIALS[0]]:
                with urlopen(base + path) as response:
                    self.assertEqual(response.status, 200)
                    self.assertTrue(response.read())
            for method in ['GET', 'HEAD']:
                with self.assertRaises(HTTPError) as error:
                    urlopen(Request(base + '/server.py', method=method))
                self.assertEqual(error.exception.code, 404)
            data = {'tag': server.SERIALS[0], 'request_id': str(uuid.uuid4())}
            for _ in range(2):
                request = Request(base + '/api/scan', json.dumps(data).encode(), {'Content-Type': 'application/json'})
                with urlopen(request) as response:
                    self.assertEqual(json.load(response)['count'], 1)
            for data in [{}, [], {'tag': 1}, {'tag': server.SERIALS[0], 'request_id': 'bad'}]:
                with self.assertRaises(HTTPError) as error:
                    urlopen(Request(base + '/api/scan', json.dumps(data).encode(), {'Content-Type': 'application/json'}))
                self.assertEqual(error.exception.code, 400)
        finally:
            http.shutdown()
            http.server_close()
            thread.join()

if __name__ == '__main__':
    unittest.main()
