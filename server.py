"""Thumbnail Lab: local state server. Run: python3 server.py."""
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import json, sqlite3, os
ROOT = Path(__file__).resolve().parent
DB = Path(os.environ.get('THUMBNAIL_LAB_DB', str(ROOT / 'library.sqlite3')))
PORT = int(os.environ.get('THUMBNAIL_LAB_PORT', '8769'))
MAX_BYTES = 80 * 1024 * 1024

def connection():
    db = sqlite3.connect(DB)
    db.execute('CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY CHECK(id=1), version INTEGER, body TEXT)')
    return db

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass
    def respond(self, status, body, content_type='application/json; charset=utf-8'):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(data)
    def allowed(self):
        host = self.headers.get('Host', '')
        return host in (f'localhost:{PORT}', f'127.0.0.1:{PORT}') and self.headers.get('Origin', 'http://' + host) == 'http://' + host
    def do_GET(self):
        if not self.allowed():
            return self.respond(403, {'error': '接続元を確認してください。'})
        if self.path == '/api/state':
            with connection() as db:
                row = db.execute('SELECT version, body FROM state WHERE id=1').fetchone()
            return self.respond(200, {'version': row[0], 'data': json.loads(row[1])} if row else {'version': 0, 'data': {'channels': [], 'active': ''}})
        names = {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css'}
        if self.path not in names:
            return self.respond(404, {'error': '見つかりません。'})
        types = {'/': 'text/html; charset=utf-8', '/app.js': 'text/javascript; charset=utf-8', '/style.css': 'text/css; charset=utf-8'}
        return self.respond(200, (ROOT / 'public' / names[self.path]).read_bytes(), types[self.path])
    def do_POST(self):
        if self.path != '/api/state' or not self.allowed() or self.headers.get('X-Thumbnail-Lab') != '1':
            return self.respond(403, {'error': '保存を許可できません。'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= MAX_BYTES:
                return self.respond(413, {'error': '保存容量の上限（80MB）を超えました。'})
            payload = json.loads(self.rfile.read(size))
            data = payload['data']
            if not isinstance(data, dict) or not isinstance(data.get('channels'), list) or len(data['channels']) > 100:
                raise ValueError()
            encoded = json.dumps(data, ensure_ascii=False)
            with connection() as db:
                db.execute('BEGIN IMMEDIATE')
                row = db.execute('SELECT version FROM state WHERE id=1').fetchone()
                version = row[0] if row else 0
                if payload['version'] != version:
                    return self.respond(409, {'error': '別の画面で更新されました。再読み込みしてから保存してください。'})
                db.execute('INSERT OR REPLACE INTO state VALUES (1, ?, ?)', (version + 1, encoded))
            self.respond(200, {'version': version + 1})
        except (ValueError, KeyError, TypeError):
            self.respond(400, {'error': '保存データの形式が正しくありません。'})
        except Exception:
            self.respond(500, {'error': '保存できませんでした。この端末の空き容量と接続を確認してください。'})

if __name__ == '__main__':
    print(f'Thumbnail Lab: http://127.0.0.1:{PORT}', flush=True)
    HTTPServer(('127.0.0.1', PORT), Handler).serve_forever()
