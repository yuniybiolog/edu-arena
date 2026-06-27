const express = require('express');
const http = require('http');
const socketIo = require('socket.io');
const Database = require('better-sqlite3');
const cors = require('cors');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');

const app = express();
const server = http.createServer(app);
const io = socketIo(server, { cors: { origin: "*" } });
const db = new Database('arena.db');

db.exec(`
  CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT,
    coins INTEGER DEFAULT 100,
    rating INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );
  CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    description TEXT,
    difficulty TEXT,
    reward INTEGER,
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
`);

app.use(cors());
app.use(express.json());
app.use(express.static('public'));

const JWT_SECRET = 'arena-secret-2024';

app.post('/register', async (req, res) => {
  const { username, password } = req.body;
  const hashedPassword = await bcrypt.hash(password, 10);
  try {
    db.prepare('INSERT INTO users (username, password) VALUES (?, ?)').run(username, hashedPassword);
    const user = db.prepare('SELECT * FROM users WHERE username = ?').get(username);
    const token = jwt.sign({ id: user.id, username }, JWT_SECRET);
    res.json({ token, coins: 100 });
  } catch (e) {
    res.status(400).json({ error: 'Пользователь уже существует' });
  }
});

app.post('/login', async (req, res) => {
  const { username, password } = req.body;
  const user = db.prepare('SELECT * FROM users WHERE username = ?').get(username);
  if (user && await bcrypt.compare(password, user.password)) {
    const token = jwt.sign({ id: user.id, username }, JWT_SECRET);
    res.json({ token, coins: user.coins, rating: user.rating });
  } else {
    res.status(401).json({ error: 'Неверный логин или пароль' });
  }
});

app.get('/balance', auth, (req, res) => {
  const user = db.prepare('SELECT coins, rating FROM users WHERE id = ?').get(req.user.id);
  res.json(user);
});

app.get('/tasks', auth, (req, res) => {
  const tasks = db.prepare('SELECT * FROM tasks ORDER BY id DESC').all();
  res.json(tasks);
});

app.post('/tasks/check', auth, (req, res) => {
  const { taskId, answer } = req.body;
  const task = db.prepare('SELECT * FROM tasks WHERE id = ?').get(taskId);
  if (task.answer.toLowerCase() === answer.toLowerCase()) {
    db.prepare('UPDATE users SET coins = coins + ?, rating = rating + 10 WHERE id = ?').run(task.reward, req.user.id);
    const user = db.prepare('SELECT coins FROM users WHERE id = ?').get(req.user.id);
    io.emit('notification', { message: `${req.user.username} решил "${task.title}"!` });
    res.json({ correct: true, coins: user.coins });
  } else {
    res.json({ correct: false });
  }
});

app.get('/forum', auth, (req, res) => {
  const posts = db.prepare(`SELECT fp.*, u.username FROM forum_posts fp JOIN users u ON fp.user_id = u.id ORDER BY fp.created_at DESC`).all();
  res.json(posts);
});

app.post('/forum', auth, (req, res) => {
  const post = db.prepare('INSERT INTO forum_posts (user_id, content) VALUES (?, ?)').run(req.user.id, req.body.content);
  const newPost = db.prepare('SELECT fp.*, u.username FROM forum_posts fp JOIN users u ON fp.user_id = u.id WHERE fp.id = ?').get(post.lastInsertRowid);
  io.emit('new_post', newPost);
  res.json(newPost);
});

io.on('connection', (socket) => {
  console.log('Пользователь подключился');
  socket.on('chat', (data) => {
    const user = jwt.verify(data.token, JWT_SECRET);
    db.prepare('INSERT INTO messages (user_id, message) VALUES (?, ?)').run(user.id, data.message);
    io.emit('chat', { username: user.username, message: data.message });
  });
});

function auth(req, res, next) {
  const token = req.headers.authorization?.split(' ')[1];
  if (!token) return res.status(401).json({ error: 'Нет токена' });
  try { req.user = jwt.verify(token, JWT_SECRET); next(); }
  catch { res.status(401).json({ error: 'Неверный токен' }); }
}

const tasks = [
  ['Математика', '2 + 2 * 2 = ?', 'easy', 10, '6'],
  ['Логика', 'Сколько месяцев в году имеют 28 дней?', 'easy', 10, '12'],
  ['География', 'Столица Франции?', 'easy', 10, 'париж']
];

const count = db.prepare('SELECT COUNT(*) as c FROM tasks').get();
if (count.c === 0) {
  const insert = db.prepare('INSERT INTO tasks (title, description, difficulty, reward, answer) VALUES (?, ?, ?, ?, ?)');
  tasks.forEach(t => insert.run(...t));
}

server.listen(3000, () => {
  console.log('🎮 Сервер запущен: http://localhost:3000');
});
