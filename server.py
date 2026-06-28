import psycopg2
import psycopg2.extras
import psycopg2.errors
import os
import json
import hashlib
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

def get_db():
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        return psycopg2.connect(db_url)
    return psycopg2.connect(
        host=os.environ.get('PGHOST', 'localhost'),
        database=os.environ.get('PGDATABASE', 'hilbert'),
        user=os.environ.get('PGUSER', 'ahror'),
        password=os.environ.get('PGPASSWORD', ''),
        port=os.environ.get('PGPORT', '5432')
    )

def clear_database():
    db = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM messages")
    cur.execute("DELETE FROM forum_posts")
    cur.execute("DELETE FROM tasks")
    cur.execute("DELETE FROM users")
    cur.execute("ALTER SEQUENCE IF EXISTS users_id_seq RESTART WITH 1")
    cur.execute("ALTER SEQUENCE IF EXISTS tasks_id_seq RESTART WITH 1")
    cur.execute("ALTER SEQUENCE IF EXISTS forum_posts_id_seq RESTART WITH 1")
    cur.execute("ALTER SEQUENCE IF EXISTS messages_id_seq RESTART WITH 1")
    db.commit()
    cur.close()
    db.close()

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path

        if path == '/':
            self.send_file('public/index.html', 'text/html')
        elif path == '/register':
            self.send_file('public/register.html', 'text/html')
        elif path == '/login':
            self.send_file('public/login.html', 'text/html')
        elif path == '/app':
            self.send_file('public/app.html', 'text/html')
        elif path == '/back.jpg':
            self.send_file('public/back.jpg', 'image/jpeg')
        else:
            self.send_error(404)

    def send_file(self, filepath, content_type):
        try:
            with open(filepath, 'rb') as f:
                self.send_response(200)
                self.send_header('Content-Type', f'{content_type}; charset=utf-8')
                self.end_headers()
                self.wfile.write(f.read())
        except FileNotFoundError:
            self.send_error(404)

PORT = int(os.environ.get('PORT', 3000))
server = HTTPServer(('0.0.0.0', PORT), Handler)
server.serve_forever()
