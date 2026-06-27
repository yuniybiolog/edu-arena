const express = require('express');
const http = require('http');
const socketIo = require('socket.io');
const Database = require('better-sqlite3');
const cors = require('cors');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const path = require('path');

const app = express();
const server = http.createServer(app);
const io = socketIo(server, { cors: { origin: "*" } });
const db = new Database('arena.db');

db.exec(`
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
`);

app.use(cors());
app.use(express.json());
app.use(express.static('public'));

const JWT_SECRET = 'hilbert-space-secret-2024';

// Страницы
app.get('/', (req, res) => res.sendFile(path.join(__dirname, 'public', 'index.html')));
app.get('/register', (req, res) => res.sendFile(path.join(__dirname, 'public', 'register.html')));
app.get('/login', (req, res) => res.sendFile(path.join(__dirname, 'public', 'login.html')));
app.get('/resources', (req, res) => res.sendFile(path.join(__dirname, 'public', 'resources.html')));

// API
app.post('/api/register', async (req, res) => {
  const { username, password } = req.body;
  const hashedPassword = await bcrypt.hash(password, 10);
  try {
    db.prepare('INSERT INTO users (username, password) VALUES (?, ?)').run(username, hashedPassword);
    const user = db.prepare('SELECT * FROM users WHERE username = ?').get(username);
    const token = jwt.sign({ id: user.id, username }, JWT_SECRET);
    res.json({ token, omega: user.omega, kappa: user.kappa });
  } catch (e) {
    res.status(400).json({ error: 'Пользователь уже существует' });
  }
});

app.post('/api/login', async (req, res) => {
  const { username, password } = req.body;
  const user = db.prepare('SELECT * FROM users WHERE username = ?').get(username);
  if (user && await bcrypt.compare(password, user.password)) {
    const token = jwt.sign({ id: user.id, username }, JWT_SECRET);
    res.json({ token, omega: user.omega, kappa: user.kappa, rating: user.rating });
  } else {
    res.status(401).json({ error: 'Неверный логин или пароль' });
  }
});

app.get('/api/balance', auth, (req, res) => {
  const user = db.prepare('SELECT omega, kappa, rating FROM users WHERE id = ?').get(req.user.id);
  res.json(user);
});

app.get('/api/tasks', auth, (req, res) => {
  const tasks = db.prepare('SELECT * FROM tasks ORDER BY id DESC').all();
  res.json(tasks);
});

app.post('/api/tasks/check', auth, (req, res) => {
  const { taskId, answer } = req.body;
  const task = db.prepare('SELECT * FROM tasks WHERE id = ?').get(taskId);
  if (task.answer.toLowerCase() === answer.toLowerCase()) {
    db.prepare('UPDATE users SET omega = omega + ?, kappa = kappa + ?, rating = rating + 10 WHERE id = ?')
    .run(task.reward_omega, task.reward_kappa, req.user.id);
    const user = db.prepare('SELECT omega, kappa FROM users WHERE id = ?').get(req.user.id);
    io.emit('notification', { message: `${req.user.username} решил "${task.title}"!` });
    res.json({ correct: true, omega: user.omega, kappa: user.kappa });
  } else {
    res.json({ correct: false });
  }
});

app.get('/api/forum', auth, (req, res) => {
  const posts = db.prepare(`SELECT fp.*, u.username FROM forum_posts fp JOIN users u ON fp.user_id = u.id ORDER BY fp.created_at DESC`).all();
  res.json(posts);
});

app.post('/api/forum', auth, (req, res) => {
  const post = db.prepare('INSERT INTO forum_posts (user_id, content) VALUES (?, ?)').run(req.user.id, req.body.content);
  const newPost = db.prepare('SELECT fp.*, u.username FROM forum_posts fp JOIN users u ON fp.user_id = u.id WHERE fp.id = ?').get(post.lastInsertRowid);
  io.emit('new_post', newPost);
  res.json(newPost);
});

io.on('connection', (socket) => {
  console.log('Пользователь подключился');
  socket.on('chat', (data) => {
    try {
      const user = jwt.verify(data.token, JWT_SECRET);
      db.prepare('INSERT INTO messages (user_id, message) VALUES (?, ?)').run(user.id, data.message);
      io.emit('chat', { username: user.username, message: data.message });
    } catch(e) {}
  });
});

function auth(req, res, next) {
  const token = req.headers.authorization?.split(' ')[1];
  if (!token) return res.status(401).json({ error: 'Нет токена' });
  try { req.user = jwt.verify(token, JWT_SECRET); next(); }
  catch { res.status(401).json({ error: 'Неверный токен' }); }
}

// Тестовые задачи с двумя валютами
const tasks = [
  ['Квантовая механика', 'Чему равна постоянная Планка? (только число × 10^-34)', 'hard', 50, 1, '6.626'],
  ['Математика', 'Определитель единичной матрицы 3x3?', 'easy', 10, 0, '1'],
['Логика', 'Все A есть B, все B есть C → все A есть C. Это?', 'medium', 20, 0, 'силлогизм'],
['Геометрия', 'Сколько измерений в Гильбертовом пространстве?', 'hard', 100, 3, 'бесконечно'],
['Физика', 'Кто предложил волновое уравнение ψ(x,t)?', 'medium', 30, 1, 'шредингер']
];

const count = db.prepare('SELECT COUNT(*) as c FROM tasks').get();
if (count.c === 0) {
  const insert = db.prepare('INSERT INTO tasks (title, description, difficulty, reward_omega, reward_kappa, answer) VALUES (?, ?, ?, ?, ?, ?)');
  tasks.forEach(t => insert.run(...t));
}

const PORT = process.env.PORT || 3000;
server.listen(PORT, () => console.log(`🧠 Hilbert Space: http://localhost:${PORT}`));
