
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

db = get_db()
cur = db.cursor()
cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        omega INTEGER DEFAULT 500,
        kappa INTEGER DEFAULT 2,
        rating INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS tasks (
        id SERIAL PRIMARY KEY,
        title TEXT NOT NULL,
        description TEXT,
        difficulty TEXT DEFAULT 'easy',
        reward_omega INTEGER DEFAULT 10,
        reward_kappa INTEGER DEFAULT 0,
        answer TEXT NOT NULL
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


cur.execute("SELECT COUNT(*) FROM tasks")
if cur.fetchone()[0] == 0:
    tasks = [
        ('Квантовая механика', 'Чему равна постоянная Планка? (число × 10^-34)', 'hard', 50, 1, '6.626'),
        ('Математика', 'Определитель единичной матрицы 3x3?', 'easy', 10, 0, '1'),
        ('Логика', 'Все A есть B, все B есть C → все A есть C. Это?', 'medium', 20, 0, 'силлогизм'),
        ('Геометрия', 'Сколько измерений в Гильбертовом пространстве?', 'hard', 100, 3, 'бесконечно'),
        ('Физика', 'Волновое уравнение ψ(x,t)? Кто предложил?', 'medium', 30, 1, 'шредингер')
    ]
    cur.executemany(
        'INSERT INTO tasks (title, description, difficulty, reward_omega, reward_kappa, answer) VALUES (%s, %s, %s, %s, %s, %s)',
        tasks
    )
    db.commit()
cur.close()
db.close()
print('🗄️ База данных готова')


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path


        if path in ['/', '/register', '/login', '/resources']:
            filename = 'public/index.html' if path == '/' else f'public{path}.html'
            try:
                with open(filename, 'rb') as f:
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html; charset=utf-8')
                    self.end_headers()
                    self.wfile.write(f.read())
            except FileNotFoundError:
                self.send_error(404)


        elif path == '/api/tasks':
            db = get_db()
            cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute('SELECT * FROM tasks ORDER BY id DESC')
            tasks = cur.fetchall()

            for t in tasks:
                for k, v in t.items():
                    if hasattr(v, 'isoformat'):
                        t[k] = v.isoformat()
            cur.close();
            db.close()

            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps(tasks, ensure_ascii=False).encode())


        elif path == '/api/forum':
            db = get_db()
            cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("""
                SELECT fp.id, fp.content, fp.created_at, u.username 
                FROM forum_posts fp 
                JOIN users u ON fp.user_id = u.id 
                ORDER BY fp.created_at DESC 
                LIMIT 50
            """)
            posts = cur.fetchall()
            for p in posts:
                for k, v in p.items():
                    if hasattr(v, 'isoformat'):
                        p[k] = v.isoformat()
            cur.close();
            db.close()

            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps(posts, ensure_ascii=False).encode())


        elif path == '/api/balance':
            token = self.headers.get('Authorization', '').replace('Bearer ', '')
            if not token:
                self.send_error(401)
                return

            db = get_db()
            cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute('SELECT omega, kappa, rating, username FROM users WHERE id = %s', (int(token),))
            user = cur.fetchone()
            cur.close();
            db.close()

            if user:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps(user, ensure_ascii=False).encode())
            else:
                self.send_error(404)

        else:
            self.send_error(404)

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length)) if length > 0 else {}
        path = urlparse(self.path).path


        if path == '/api/register':
            username = body.get('username', '')
            password = hashlib.sha256(body.get('password', '').encode()).hexdigest()

            db = get_db()
            cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            try:
                cur.execute('INSERT INTO users (username, password) VALUES (%s, %s) RETURNING id, omega, kappa',
                            (username, password))
                user = cur.fetchone()
                db.commit()
                response = {'token': str(user['id']), 'omega': user['omega'], 'kappa': user['kappa']}
            except psycopg2.errors.UniqueViolation:
                db.rollback()
                response = {'error': 'Пользователь уже существует'}
            cur.close();
            db.close()

            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode())

        elif path == '/api/login':
            username = body.get('username', '')
            password = hashlib.sha256(body.get('password', '').encode()).hexdigest()

            db = get_db()
            cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute('SELECT id, omega, kappa, rating FROM users WHERE username = %s AND password = %s',
                        (username, password))
            user = cur.fetchone()
            cur.close();
            db.close()

            if user:
                response = {'token': str(user['id']), 'omega': user['omega'],
                            'kappa': user['kappa'], 'rating': user['rating']}
            else:
                response = {'error': 'Неверный логин или пароль'}

            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode())


        elif path == '/api/tasks/check':
            task_id = body.get('taskId')
            answer = body.get('answer', '')
            token = body.get('token', '')

            db = get_db()
            cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute('SELECT * FROM tasks WHERE id = %s', (task_id,))
            task = cur.fetchone()

            if task and task['answer'].strip().lower() == answer.strip().lower():
                cur.execute("""
                    UPDATE users 
                    SET omega = omega + %s, kappa = kappa + %s, rating = rating + 10 
                    WHERE id = %s 
                    RETURNING omega, kappa
                """, (task['reward_omega'], task['reward_kappa'], int(token)))
                user = cur.fetchone()
                db.commit()
                response = {'correct': True, 'omega': user['omega'], 'kappa': user['kappa']}
            else:
                response = {'correct': False}

            cur.close();
            db.close()

            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode())


        elif path == '/api/forum':
            token = body.get('token', '')
            content = body.get('content', '')

            db = get_db()
            cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute('INSERT INTO forum_posts (user_id, content) VALUES (%s, %s) RETURNING id',
                        (int(token), content))
            db.commit()
            cur.close();
            db.close()

            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({'success': True}, ensure_ascii=False).encode())

        else:
            self.send_error(404)
