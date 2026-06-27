import os

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
    db.executemany('INSERT INTO tasks (title, description, difficulty, reward_omega, reward_kappa, answer) VALUES (?, ?, ?, ?, ?, ?)', tasks_list)
    db.commit()

# Запуск
PORT = int(os.environ.get('PORT', 3000))
uvicorn.run(socket_app, host='0.0.0.0', port=PORT)