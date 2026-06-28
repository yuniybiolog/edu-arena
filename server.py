import psycopg2
import psycopg2.extras
import psycopg2.errors
import os
import json
import hashlib
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI', 'https://hilbert-space.onrender.com/oauth/google/callback')

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

db = get_db()
cur = db.cursor()
cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password TEXT,
        name TEXT,
        email TEXT UNIQUE,
        age INTEGER,
        omega INTEGER DEFAULT 500,
        kappa INTEGER DEFAULT 2,
        rating INTEGER DEFAULT 0,
        google_id TEXT UNIQUE,
        avatar_url TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS forum_posts (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS messages (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        message TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
""")
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
        elif path == '/oauth/google/callback':
            self.handle_google_callback()
        else:
            self.send_error(404)

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length)) if length > 0 else {}
        path = urlparse(self.path).path

        if path == '/api/register':
            username = body.get('username', '')
            password = hashlib.sha256(body.get('password', '').encode()).hexdigest()
            name = body.get('name', username)
            email = body.get('email', '')
            age = body.get('age')

            db = get_db()
            cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            try:
                cur.execute('INSERT INTO users (username, password, name, email, age) VALUES (%s, %s, %s, %s, %s) RETURNING id, omega, kappa',
                            (username, password, name, email, age))
                user = cur.fetchone()
                db.commit()
                self.send_json({'token': str(user['id']), 'omega': user['omega'], 'kappa': user['kappa']})
            except psycopg2.errors.UniqueViolation:
                db.rollback()
                self.send_json({'error': 'Пользователь уже существует'})
            cur.close(); db.close()

        elif path == '/api/login':
            username = body.get('username', '')
            password = hashlib.sha256(body.get('password', '').encode()).hexdigest()

            db = get_db()
            cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute('SELECT id, omega, kappa, rating FROM users WHERE username = %s AND password = %s',
                        (username, password))
            user = cur.fetchone()
            cur.close(); db.close()

            if user:
                self.send_json({'token': str(user['id']), 'omega': user['omega'], 'kappa': user['kappa'], 'rating': user['rating']})
            else:
                self.send_json({'error': 'Неверный логин или пароль'})

        else:
            self.send_error(404)

    def handle_google_callback(self):
        query = parse_qs(urlparse(self.path).query)
        code = query.get('code', [None])[0]

        if not code:
            self.send_error(400)
            return

        token_res = requests.post('https://oauth2.googleapis.com/token', data={
            'code': code,
            'client_id': GOOGLE_CLIENT_ID,
            'client_secret': GOOGLE_CLIENT_SECRET,
            'redirect_uri': GOOGLE_REDIRECT_URI,
            'grant_type': 'authorization_code'
        })
        token_data = token_res.json()
        access_token = token_data.get('access_token')

        if not access_token:
            self.send_error(400)
            return

        user_res = requests.get('https://www.googleapis.com/oauth2/v2/userinfo', headers={
            'Authorization': f'Bearer {access_token}'
        })
        google_user = user_res.json()

        google_id = google_user.get('id')
        email = google_user.get('email')
        name = google_user.get('name')
        avatar = google_user.get('picture')

        db = get_db()
        cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute('SELECT * FROM users WHERE google_id = %s OR email = %s', (google_id, email))
        user = cur.fetchone()

        if not user:
            username = email.split('@')[0]
            cur.execute("""
                INSERT INTO users (username, name, email, google_id, avatar_url)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (username) DO UPDATE SET username = %s || '_' || substr(md5(random()::text), 1, 5)
                RETURNING id, omega, kappa
            """, (username, name, email, google_id, avatar, username))
            user = cur.fetchone()
            db.commit()

        cur.close(); db.close()

        self.send_response(302)
        self.send_header('Location', f'/app?token={user["id"]}')
        self.end_headers()

    def send_file(self, filepath, content_type):
        try:
            with open(filepath, 'rb') as f:
                self.send_response(200)
                self.send_header('Content-Type', f'{content_type}; charset=utf-8')
                self.end_headers()
                self.wfile.write(f.read())
        except FileNotFoundError:
            self.send_error(404)

    def send_json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, default=str).encode())

PORT = int(os.environ.get('PORT', 3000))
server = HTTPServer(('0.0.0.0', PORT), Handler)
server.serve_forever()
