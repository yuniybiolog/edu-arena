import sqlite3
import bcrypt
import jwt
from datetime import datetime, timedelta
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import socketio
import uvicorn

# FastAPI
app = FastAPI()

# Socket.IO
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
socket_app = socketio.ASGIApp(sio, other_app=app)

# База данных
db = sqlite3.connect('arena.db', check_same_thread=False)
db.row_factory = sqlite3.Row
db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        omega INTEGER DEFAULT 500,
        kappa INTEGER DEFAULT 2,
        rating INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
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

JWT_SECRET = 'hilbert-space-secret-2024'


# Вспомогательная функция
def get_user_from_token(request: Request):
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        raise HTTPException(401, 'Нет токена')
    try:
        token = auth.split(' ')[1]
        return jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
    except:
        raise HTTPException(401, 'Неверный токен')


# Статические файлы
app.mount("/static", StaticFiles(directory="public"), name="static")


# Страницы
@app.get("/")
async def index():
    return FileResponse('public/index.html')


@app.get("/register")
async def register_page():
    return FileResponse('public/register.html')


@app.get("/login")
async def login_page():
    return FileResponse('public/login.html')


@app.get("/resources")
async def resources_page():
    return FileResponse('public/resources.html')


# API
@app.post("/api/register")
async def api_register(request: Request):
    data = await request.json()
    username = data['username']
    password = data['password']

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())

    try:
        cursor = db.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed))
        db.commit()
        user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        token = jwt.encode({'id': user['id'], 'username': username}, JWT_SECRET, algorithm='HS256')
        return {'token': token, 'omega': user['omega'], 'kappa': user['kappa']}
    except sqlite3.IntegrityError:
        raise HTTPException(400, 'Пользователь уже существует')


@app.post("/api/login")
async def api_login(request: Request):
    data = await request.json()
    username = data['username']
    password = data['password']

    user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    if user and bcrypt.checkpw(password.encode(), user['password']):
        token = jwt.encode({'id': user['id'], 'username': username}, JWT_SECRET, algorithm='HS256')
        return {'token': token, 'omega': user['omega'], 'kappa': user['kappa'], 'rating': user['rating']}
    raise HTTPException(401, 'Неверный логин или пароль')


@app.get("/api/balance")
async def api_balance(request: Request):
    user_data = get_user_from_token(request)
    user = db.execute('SELECT omega, kappa, rating FROM users WHERE id = ?', (user_data['id'],)).fetchone()
    return {'omega': user['omega'], 'kappa': user['kappa'], 'rating': user['rating']}


@app.get("/api/tasks")
async def api_tasks(request: Request):
    get_user_from_token(request)
    tasks = db.execute('SELECT * FROM tasks ORDER BY id DESC').fetchall()
    return [dict(t) for t in tasks]


@app.post("/api/tasks/check")
async def api_tasks_check(request: Request):
    user_data = get_user_from_token(request)
    data = await request.json()
    task_id = data['taskId']
    answer = data['answer']

    task = db.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
    if not task:
        raise HTTPException(404, 'Задача не найдена')

    if task['answer'].lower() == answer.lower():
        db.execute('UPDATE users SET omega = omega + ?, kappa = kappa + ?, rating = rating + 10 WHERE id = ?',
                   (task['reward_omega'], task['reward_kappa'], user_data['id']))
        db.commit()
        user = db.execute('SELECT omega, kappa FROM users WHERE id = ?', (user_data['id'],)).fetchone()
        await sio.emit('notification', {'message': f"{user_data['username']} решил \"{task['title']}\"!"})
        return {'correct': True, 'omega': user['omega'], 'kappa': user['kappa']}
    return {'correct': False}


@app.get("/api/forum")
async def api_forum(request: Request):
    get_user_from_token(request)
    posts = db.execute('''
        SELECT fp.*, u.username FROM forum_posts fp 
        JOIN users u ON fp.user_id = u.id 
        ORDER BY fp.created_at DESC
    ''').fetchall()
    return [dict(p) for p in posts]


@app.post("/api/forum")
async def api_forum_post(request: Request):
    user_data = get_user_from_token(request)
    data = await request.json()
    cursor = db.execute('INSERT INTO forum_posts (user_id, content) VALUES (?, ?)',
                        (user_data['id'], data['content']))
    db.commit()
    post = db.execute('SELECT fp.*, u.username FROM forum_posts fp JOIN users u ON fp.user_id = u.id WHERE fp.id = ?',
                      (cursor.lastrowid,)).fetchone()
    await sio.emit('new_post', dict(post))
    return dict(post)


# Socket.IO
@sio.event
async def connect(sid, environ):
    print(f'Подключился: {sid}')


@sio.event
async def chat(sid, data):
    try:
        user = jwt.decode(data['token'], JWT_SECRET, algorithms=['HS256'])
        db.execute('INSERT INTO messages (user_id, message) VALUES (?, ?)', (user['id'], data['message']))
        db.commit()
        await sio.emit('chat', {'username': user['username'], 'message': data['message']})
    except:
        pass


@sio.event
async def disconnect(sid):
    print(f'Отключился: {sid}')


# Тестовые задачи
tasks_list = [
    ('Квантовая механика', 'Чему равна постоянная Планка? (только число × 10^-34)', 'hard', 50, 1, '6.626'),
    ('Математика', 'Определитель единичной матрицы 3x3?', 'easy', 10, 0, '1'),
    ('Логика', 'Все A есть B, все B есть C → все A есть C. Это?', 'medium', 20, 0, 'силлогизм'),
    ('Геометрия', 'Сколько измерений в Гильбертовом пространстве?', 'hard', 100, 3, 'бесконечно'),
    ('Физика', 'Кто предложил волновое уравнение ψ(x,t)?', 'medium', 30, 1, 'шредингер')
]

count = db.execute('SELECT COUNT(*) as c FROM tasks').fetchone()
if count['c'] == 0:
    db.executemany(
        'INSERT INTO tasks (title, description, difficulty, reward_omega, reward_kappa, answer) VALUES (?, ?, ?, ?, ?, ?)',
        tasks_list)
    db.commit()

# Запуск
if __name__ == '__main__':
    uvicorn.run(socket_app, host='0.0.0.0', port=3000)