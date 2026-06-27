import sqlite3
import hashlib
import os
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

db = sqlite3.connect('arena.db', check_same_thread=False)
db.execute("PRAGMA journal_mode=WAL")
db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        omega INTEGER DEFAULT 500,
        kappa INTEGER DEFAULT 2,
        rating INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        description TEXT,
        difficulty TEXT,
        reward_omega INTEGER DEFAULT 10,
        reward_kappa INTEGER DEFAULT 0,
        answer TEXT
    );
    CREATE TABLE IF NOT EXISTS forum_posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        content TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        message TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
""")

# Тестовые задачи
tasks_list = [
    ('Квантовая механика', 'Чему равна постоянная Планка? (число × 10^-34)', 'hard', 50, 1, '6.626'),
    ('Математика', 'Определитель единичной матрицы 3x3?', 'easy', 10, 0, '1'),
    ('Логика', 'Все A есть B, все B есть C → все A есть C. Это?', 'medium', 20, 0, 'силлогизм'),
    ('Геометрия', 'Сколько измерений в Гильбертовом пространстве?', 'hard', 100, 3, 'бесконечно'),
    ('Физика', 'Волновое уравнение ψ(x,t)? Кто предложил?', 'medium', 30, 1, 'шредингер')
]

count = db.execute('SELECT COUNT(*) as c FROM tasks').fetchone()[0]
if count == 0:
    db.executemany('INSERT INTO tasks (title, description, difficulty, reward_omega, reward_kappa, answer) VALUES (?, ?, ?, ?, ?, ?)', tasks_list)
    db.commit()

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        
        if path == '/' or path == '/register' or path == '/login' or path == '/resources':
            filename = 'public/index.html' if path == '/' else f'public{path}.html'
            try:
                with open(filename, 'rb') as f:
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html; charset=utf-8')
                    self.end_headers()
                    self.wfile.write(f.read())
            except:
                self.send_error(404)
        elif path.startswith('/api/'):
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            if path == '/api/tasks':
                tasks = db.execute('SELECT * FROM tasks ORDER BY id DESC').fetchall()
                result = [{'id': t[0], 'title': t[1], 'description': t[2], 'difficulty': t[3], 'reward_omega': t[4], 'reward_kappa': t[5]} for t in tasks]
                self.wfile.write(json.dumps(result).encode())
            elif path == '/api/forum':
                posts = db.execute('SELECT fp.*, u.username FROM forum_posts fp JOIN users u ON fp.user_id = u.id ORDER BY fp.created_at DESC').fetchall()
                result = [{'id': p[0], 'user_id': p[1], 'content': p[2], 'created_at': p[3], 'username': p[4]} for p in posts]
                self.wfile.write(json.dumps(result).encode())
            else:
                self.wfile.write(b'{}')
        else:
            self.send_error(404)
    
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        body = json.loads(self.rfile.read(content_length))
        path = urlparse(self.path).path
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        
        if path == '/api/register':
            username = body['username']
            password = hashlib.sha256(body['password'].encode()).hexdigest()
            try:
                db.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, password))
                db.commit()
                user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
                self.wfile.write(json.dumps({'token': str(user[0]), 'omega': user[3], 'kappa': user[4]}).encode())
            except:
                self.wfile.write(json.dumps({'error': 'Пользователь существует'}).encode())
        
        elif path == '/api/login':
            username = body['username']
            password = hashlib.sha256(body['password'].encode()).hexdigest()
            user = db.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password)).fetchone()
            if user:
                self.wfile.write(json.dumps({'token': str(user[0]), 'omega': user[3], 'kappa': user[4], 'rating': user[5]}).encode())
            else:
                self.wfile.write(json.dumps({'error': 'Неверный логин или пароль'}).encode())
        
        elif path == '/api/tasks/check':
            task_id = body['taskId']
            answer = body['answer']
            user_id = int(body.get('token', 0))
            task = db.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
            if task and task[6].lower() == answer.lower():
                db.execute('UPDATE users SET omega = omega + ?, kappa = kappa + ?, rating = rating + 10 WHERE id = ?', (task[4], task[5], user_id))
                db.commit()
                user = db.execute('SELECT omega, kappa FROM users WHERE id = ?', (user_id,)).fetchone()
                self.wfile.write(json.dumps({'correct': True, 'omega': user[0], 'kappa': user[1]}).encode())
            else:
                self.wfile.write(json.dumps({'correct': False}).encode())
        
        elif path == '/api/forum':
            user_id = int(body.get('token', 0))
            content = body['content']
            db.execute('INSERT INTO forum_posts (user_id, content) VALUES (?, ?)', (user_id, content))
            db.commit()
            self.wfile.write(json.dumps({'success': True}).encode())
        
        else:
            self.wfile.write(b'{}')

PORT = int(os.environ.get('PORT', 3000))
server = HTTPServer(('0.0.0.0', PORT), Handler)
print(f'🧠 Hilbert Space запущен на порту {PORT}')
server.serve_forever()
