"""
Smart Task Management System
Flask + SQLite + WebSockets + Pandas/NumPy
"""

from flask import Flask, request, jsonify, session, render_template, redirect, url_for
from flask_socketio import SocketIO, emit
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from analytics.stats import compute_analytics
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

socketio = SocketIO(app, cors_allowed_origins="*")

DB_PATH = "task_manager.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT UNIQUE NOT NULL,
            email       TEXT UNIQUE NOT NULL,
            password    TEXT NOT NULL,
            created_at  TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title        TEXT NOT NULL,
            description  TEXT,
            priority     TEXT NOT NULL CHECK (priority IN ('low','medium','high')),
            status       TEXT NOT NULL CHECK (status IN ('pending','in_progress','completed')),
            created_at   TEXT DEFAULT (datetime('now')),
            updated_at   TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            if request.is_json:
                return jsonify({"error": "Unauthorized"}), 401
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated


@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login_page"))

@app.route("/register")
def register_page():
    return render_template("register.html")

@app.route("/login")
def login_page():
    return render_template("login.html")

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", username=session.get("username"))


@app.route("/api/auth/register", methods=["POST"])
def register():
    data     = request.get_json()
    username = (data.get("username") or "").strip()
    email    = (data.get("email")    or "").strip()
    password =  data.get("password") or ""
    if not username or not email or not password:
        return jsonify({"error": "All fields are required"}), 400
    hashed = generate_password_hash(password)
    try:
        conn = get_db()
        cur  = conn.execute(
            "INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
            (username, email, hashed)
        )
        conn.commit()
        user_id = cur.lastrowid
        conn.close()
    except sqlite3.IntegrityError:
        return jsonify({"error": "Username or email already exists"}), 409
    return jsonify({"message": "Registered successfully", "user_id": user_id}), 201


@app.route("/api/auth/login", methods=["POST"])
def login():
    data     = request.get_json()
    username = (data.get("username") or "").strip()
    password =  data.get("password") or ""
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    if not user or not check_password_hash(user["password"], password):
        return jsonify({"error": "Invalid credentials"}), 401
    session["user_id"]  = user["id"]
    session["username"] = user["username"]
    return jsonify({"message": "Logged in", "username": user["username"]}), 200


@app.route("/api/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out"}), 200


@app.route("/api/tasks", methods=["GET"])
@login_required
def get_tasks():
    conn  = get_db()
    tasks = conn.execute(
        "SELECT * FROM tasks WHERE user_id = ? ORDER BY created_at DESC",
        (session["user_id"],)
    ).fetchall()
    conn.close()
    return jsonify([dict(t) for t in tasks]), 200


@app.route("/api/tasks", methods=["POST"])
@login_required
def add_task():
    data        = request.get_json()
    title       = (data.get("title")       or "").strip()
    description = (data.get("description") or "").strip()
    priority    = (data.get("priority")    or "medium").strip().lower()
    status      = (data.get("status")      or "pending").strip().lower()
    if not title:
        return jsonify({"error": "Title is required"}), 400
    if priority not in ("low", "medium", "high"):
        return jsonify({"error": "Priority must be low/medium/high"}), 400
    if status not in ("pending", "in_progress", "completed"):
        return jsonify({"error": "Invalid status"}), 400
    conn = get_db()
    cur  = conn.execute(
        "INSERT INTO tasks (user_id, title, description, priority, status) VALUES (?,?,?,?,?)",
        (session["user_id"], title, description, priority, status)
    )
    conn.commit()
    task = dict(conn.execute("SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)).fetchone())
    conn.close()
    socketio.emit("task_added", task, to=f"user_{session['user_id']}")
    return jsonify(task), 201


@app.route("/api/tasks/<int:task_id>", methods=["PUT"])
@login_required
def update_task(task_id):
    data        = request.get_json()
    title       = data.get("title")
    description = data.get("description")
    priority    = data.get("priority")
    status      = data.get("status")
    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM tasks WHERE id = ? AND user_id = ?",
        (task_id, session["user_id"])
    ).fetchone()
    if not existing:
        conn.close()
        return jsonify({"error": "Task not found"}), 404
    conn.execute(
        """UPDATE tasks SET title=?, description=?, priority=?, status=?,
           updated_at=datetime('now') WHERE id=? AND user_id=?""",
        (title, description, priority, status, task_id, session["user_id"])
    )
    conn.commit()
    task = dict(conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone())
    conn.close()
    socketio.emit("task_updated", task, to=f"user_{session['user_id']}")
    return jsonify(task), 200


@app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
@login_required
def delete_task(task_id):
    conn = get_db()
    deleted = conn.execute(
        "DELETE FROM tasks WHERE id=? AND user_id=?",
        (task_id, session["user_id"])
    ).rowcount
    conn.commit()
    conn.close()
    if not deleted:
        return jsonify({"error": "Task not found"}), 404
    socketio.emit("task_deleted", {"id": task_id}, to=f"user_{session['user_id']}")
    return jsonify({"message": "Task deleted"}), 200


@app.route("/api/analytics", methods=["GET"])
@login_required
def analytics():
    conn  = get_db()
    rows  = conn.execute("SELECT * FROM tasks WHERE user_id = ?", (session["user_id"],)).fetchall()
    conn.close()
    stats = compute_analytics([dict(r) for r in rows])
    return jsonify(stats), 200


@socketio.on("connect")
def on_connect():
    if "user_id" in session:
        from flask_socketio import join_room
        join_room(f"user_{session['user_id']}")
        emit("connected", {"message": "Real-time updates active"})

@socketio.on("disconnect")
def on_disconnect():
    pass


if __name__ == "__main__":
    init_db()
    socketio.run(app, debug=True, host="0.0.0.0", port=5000)
