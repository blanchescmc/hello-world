import json
import os
import sqlite3
import re
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

ROOT = Path(__file__).resolve().parent
DB = Path(os.environ.get('NFC_DB_PATH', '/workspace/nfc-data/counts.sqlite3'))
SERIALS = ('53:D8:75:07:51:00:01', '53:D9:75:07:51:00:01', '53:DA:75:07:51:00:01')
LIMIT = 3

def connect():
    return sqlite3.connect(DB, timeout=10)

def initialize():
    DB.parent.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS tags (serial TEXT PRIMARY KEY, count INTEGER NOT NULL DEFAULT 0)')
        db.executemany('INSERT OR IGNORE INTO tags(serial) VALUES (?)', [(s,) for s in SERIALS])
        db.execute('CREATE TABLE IF NOT EXISTS scans (request_id TEXT PRIMARY KEY, serial TEXT NOT NULL, response TEXT NOT NULL)')

def check(serial, record=False, request_id=None):
    if serial not in SERIALS:
        return {'serial': serial, 'eligible': False, 'count': None, 'reason': 'unknown'}
    with connect() as db:
        if record:
            db.execute('BEGIN IMMEDIATE')
            previous = db.execute('SELECT serial, response FROM scans WHERE request_id=?', (request_id,)).fetchone()
            if previous:
                if previous[0] != serial:
                    raise ValueError('重複的請求編號')
                return json.loads(previous[1])
        count = db.execute('SELECT count FROM tags WHERE serial=?', (serial,)).fetchone()[0]
        allowed = count < LIMIT
        if record and allowed:
            count += 1
            db.execute('UPDATE tags SET count=? WHERE serial=?', (count, serial))
        response = {'serial': serial, 'eligible': allowed, 'count': count, 'remaining': LIMIT-count, 'recorded': record and allowed}
        if record:
            db.execute('INSERT INTO scans VALUES (?, ?, ?)', (request_id, serial, json.dumps(response)))
        return response

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def reply(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path == '/api/check':
            serial = parse_qs(url.query).get('tag', [''])[0].strip().upper()
            self.reply(check(serial))
        elif url.path in ('/', '/index.html', '/styles.css', '/app.js'):
            super().do_GET()
        else:
            self.send_error(404)

    def do_HEAD(self):
        if urlsplit(self.path).path in ('/', '/index.html', '/styles.css', '/app.js'):
            super().do_HEAD()
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path != '/api/scan':
            self.send_error(404)
            return
        # Require JSON and same-origin browser requests; no cross-origin CORS support.
        if self.headers.get('Sec-Fetch-Site') == 'cross-site':
            self.reply({'error': '跨網站請求不允許'}, 403)
            return
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            self.reply({'error': '需要 JSON 請求'}, 415)
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 1024:
                raise ValueError()
            payload = json.loads(self.rfile.read(length))
            serial = payload['tag'].strip().upper()
            request_id = payload['request_id']
            if not isinstance(request_id, str) or not re.fullmatch(r'[A-Za-z0-9-]{16,80}', request_id):
                raise ValueError()
        except (ValueError, KeyError, TypeError, AttributeError):
            self.reply({'error': '請求格式錯誤'}, 400)
            return
        try:
            self.reply(check(serial, record=True, request_id=request_id))
        except ValueError:
            self.reply({'error': '請求編號已用於其他標籤'}, 409)
        except sqlite3.Error:
            self.reply({'error': '資料庫暫時無法使用，請稍後重試'}, 503)

if __name__ == '__main__':
    initialize()
    ThreadingHTTPServer((os.environ.get('NFC_HOST', '127.0.0.1'), int(os.environ.get('PORT', '8001'))), Handler).serve_forever()
