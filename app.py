from flask import Flask, render_template, request, jsonify, send_file
import sqlite3
import time
from datetime import datetime, timedelta
import csv
import io

app = Flask(__name__)

DB_FILE = "tasks.db"

def init_db():
    conn = sqlite3.connect(DB_FILE, timeout=10)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS current_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        status TEXT NOT NULL,
        start_time REAL,
        time_spent REAL DEFAULT 0,
        pause_time REAL,
        position INTEGER
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS task_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        name TEXT NOT NULL,
        status TEXT NOT NULL,
        time_spent REAL DEFAULT 0
    )''')
    conn.commit()
    conn.close()

def get_current_tasks():
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, name, status, start_time, time_spent, pause_time, position FROM current_tasks ORDER BY position, id")
    tasks = [dict(row) for row in c.fetchall()]
    conn.close()
    return tasks

def clear_current_tasks():
    conn = sqlite3.connect(DB_FILE, timeout=10)
    c = conn.cursor()
    c.execute("DELETE FROM current_tasks")
    conn.commit()
    conn.close()

@app.route('/')
def dashboard():
    tasks = get_current_tasks()
    return render_template('dashboard.html', tasks=tasks)

@app.route('/control')
def control():
    tasks = get_current_tasks()
    enumerated_tasks = list(enumerate(tasks))
    return render_template('control.html', tasks=enumerated_tasks)

@app.route('/add_task', methods=['POST'])
def add_task():
    task = request.form['task']
    conn = sqlite3.connect(DB_FILE, timeout=10)
    c = conn.cursor()
    c.execute("SELECT MAX(position) FROM current_tasks")
    max_pos = c.fetchone()[0] or 0
    c.execute("INSERT INTO current_tasks (name, status, position) VALUES (?, 'pending', ?)", (task, max_pos + 1))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

@app.route('/start_task', methods=['POST'])
def start_task():
    index = int(request.form['index'])
    tasks = get_current_tasks()
    if 0 <= index < len(tasks) and tasks[index]['status'] == 'pending':
        conn = sqlite3.connect(DB_FILE, timeout=10)
        c = conn.cursor()
        c.execute("UPDATE current_tasks SET status = 'in_progress', start_time = ? WHERE id = ?",
                  (time.time(), tasks[index]['id']))
        conn.commit()
        conn.close()
    return jsonify({'status': 'success'})

@app.route('/pause_task', methods=['POST'])
def pause_task():
    index = int(request.form['index'])
    tasks = get_current_tasks()
    if 0 <= index < len(tasks) and tasks[index]['status'] == 'in_progress':
        conn = sqlite3.connect(DB_FILE, timeout=10)
        c = conn.cursor()
        current_time = time.time()
        time_spent = tasks[index]['time_spent'] + (current_time - tasks[index]['start_time'])
        c.execute("UPDATE current_tasks SET status = 'paused', time_spent = ?, pause_time = ? WHERE id = ?",
                  (time_spent, current_time, tasks[index]['id']))
        conn.commit()
        conn.close()
    return jsonify({'status': 'success'})

@app.route('/resume_task', methods=['POST'])
def resume_task():
    index = int(request.form['index'])
    tasks = get_current_tasks()
    if 0 <= index < len(tasks) and tasks[index]['status'] == 'paused':
        conn = sqlite3.connect(DB_FILE, timeout=10)
        c = conn.cursor()
        c.execute("UPDATE current_tasks SET status = 'in_progress', start_time = ? WHERE id = ?",
                  (time.time(), tasks[index]['id']))
        conn.commit()
        conn.close()
    return jsonify({'status': 'success'})

@app.route('/complete_task', methods=['POST'])
def complete_task():
    index = int(request.form['index'])
    tasks = get_current_tasks()
    if 0 <= index < len(tasks) and tasks[index]['status'] in ['in_progress', 'paused']:
        conn = sqlite3.connect(DB_FILE, timeout=10)
        c = conn.cursor()
        if tasks[index]['status'] == 'in_progress':
            time_spent = tasks[index]['time_spent'] + (time.time() - tasks[index]['start_time'])
        else:  # Paused
            time_spent = tasks[index]['time_spent']
        c.execute("UPDATE current_tasks SET status = 'completed', time_spent = ? WHERE id = ?",
                  (time_spent, tasks[index]['id']))
        conn.commit()
        conn.close()
    return jsonify({'status': 'success'})

@app.route('/move_task', methods=['POST'])
def move_task():
    index = int(request.form['index'])
    direction = request.form['direction']
    tasks = get_current_tasks()
    if 0 <= index < len(tasks):
        conn = sqlite3.connect(DB_FILE, timeout=10)
        c = conn.cursor()
        if direction == 'up' and index > 0:
            c.execute("UPDATE current_tasks SET position = ? WHERE id = ?",
                      (tasks[index - 1]['position'], tasks[index]['id']))
            c.execute("UPDATE current_tasks SET position = ? WHERE id = ?",
                      (tasks[index]['position'], tasks[index - 1]['id']))
        elif direction == 'down' and index < len(tasks) - 1:
            c.execute("UPDATE current_tasks SET position = ? WHERE id = ?",
                      (tasks[index + 1]['position'], tasks[index]['id']))
            c.execute("UPDATE current_tasks SET position = ? WHERE id = ?",
                      (tasks[index]['position'], tasks[index + 1]['id']))
        conn.commit()
        conn.close()
    return jsonify({'status': 'success'})

@app.route('/day_complete', methods=['POST'])
def day_complete():
    tasks = get_current_tasks()
    if tasks:
        conn = sqlite3.connect(DB_FILE, timeout=10)
        c = conn.cursor()
        today = datetime.now().strftime('%Y-%m-%d')
        for task in tasks:
            c.execute("INSERT INTO task_history (date, name, status, time_spent) VALUES (?, ?, ?, ?)",
                      (today, task['name'], task['status'], task['time_spent']))
        conn.commit()
        conn.close()
        clear_current_tasks()
    return jsonify({'status': 'success'})

@app.route('/download_logs/<string:range_type>')
def download_logs(range_type):
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    if range_type == 'last7':
        seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        c.execute("SELECT date, name, status, time_spent FROM task_history WHERE date >= ?", (seven_days_ago,))
        filename = "task_history_last7days.csv"
    elif range_type == 'all':
        c.execute("SELECT date, name, status, time_spent FROM task_history")
        filename = "task_history_all.csv"
    else:
        return "Invalid range", 400
    tasks = [dict(row) for row in c.fetchall()]
    conn.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Task Name', 'Status', 'Time Spent (min)'])
    for task in tasks:
        writer.writerow([task['date'], task['name'], task['status'], (task['time_spent'] / 60) if task['time_spent'] else 0])
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=filename
    )

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=False)
