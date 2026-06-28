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

# Инициализация БД
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

        # Главная страница
        if path == '/':
            try:
                with open('public/index.html', 'rb') as f:
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html; charset=utf-8')
                    self.end_headers()
                    self.wfile.write(f.read())
            except FileNotFoundError:
                self.send_error(404)

        # Картинка back.jpg
        elif path == '/back.jpg':
            try:
                with open('public/back.jpg', 'rb') as f:
                    self.send_response(200)
                    self.send_header('Content-Type', 'image/jpeg')
                    self.end_headers()
                    self.wfile.write(f.read())
            except FileNotFoundError:
                self.send_error(404)

        else:
            self.send_error(404)

PORT = int(os.environ.get('PORT', 3000))
server = HTTPServer(('0.0.0.0', PORT), Handler)
print(f'🧠 UAC запущен на порту {PORT}')
server.serve_forever()
