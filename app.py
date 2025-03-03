from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import eventlet
import ssl
from eventlet import wsgi
import sqlite3
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secure-key-here'  # Replace with your actual secure key
socketio = SocketIO(app)

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

def emit_task_update():
    tasks = get_current_tasks()
    socketio.emit('task_update', {'tasks': tasks}, namespace='/')

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
    emit_task_update()
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
        emit_task_update()
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
        emit_task_update()
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
        emit_task_update()
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
        else:
            time_spent = tasks[index]['time_spent']
        c.execute("UPDATE current_tasks SET status = 'completed', time_spent = ? WHERE id = ?",
                  (time_spent, tasks[index]['id']))
        conn.commit()
        conn.close()
        emit_task_update()
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
        emit_task_update()
    return jsonify({'status': 'success'})

@app.route('/delete_task', methods=['POST'])
def delete_task():
    index = int(request.form['index'])
    tasks = get_current_tasks()
    if 0 <= index < len(tasks):
        conn = sqlite3.connect(DB_FILE, timeout=10)
        c = conn.cursor()
        c.execute("DELETE FROM current_tasks WHERE id = ?", (tasks[index]['id'],))
        c.execute("SELECT id, position FROM current_tasks ORDER BY position")
        remaining_tasks = c.fetchall()
        for i, (task_id, _) in enumerate(remaining_tasks):
            c.execute("UPDATE current_tasks SET position = ? WHERE id = ?", (i + 1, task_id))
        conn.commit()
        conn.close()
        emit_task_update()
    return jsonify({'status': 'success'})

@app.route('/edit_task', methods=['POST'])
def edit_task():
    index = int(request.form['index'])
    new_name = request.form['name']
    tasks = get_current_tasks()
    if 0 <= index < len(tasks):
        conn = sqlite3.connect(DB_FILE, timeout=10)
        c = conn.cursor()
        c.execute("UPDATE current_tasks SET name = ? WHERE id = ?", (new_name, tasks[index]['id']))
        conn.commit()
        conn.close()
        emit_task_update()
    return jsonify({'status': 'success'})

@socketio.on('connect', namespace='/')
def handle_connect():
    emit_task_update()

if __name__ == '__main__':
    init_db()
    listener = eventlet.listen(('0.0.0.0', 5000))
    secure_listener = eventlet.wrap_ssl(
        listener,
        certfile='/home/admin/priority_dashboard/ssl/cert.pem',
        keyfile='/home/admin/priority_dashboard/ssl/key.pem',
        server_side=True,
        ssl_version=ssl.PROTOCOL_TLSv1_2
    )
    wsgi.server(secure_listener, app, log_output=False)