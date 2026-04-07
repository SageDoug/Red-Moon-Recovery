import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'redmoon.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT "athlete",
        created_at TEXT DEFAULT (datetime("now"))
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS teams (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        coach_id INTEGER NOT NULL,
        invite_code TEXT UNIQUE NOT NULL,
        created_at TEXT DEFAULT (datetime("now")),
        FOREIGN KEY (coach_id) REFERENCES users(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS team_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        team_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        role TEXT NOT NULL DEFAULT "athlete",
        joined_at TEXT DEFAULT (datetime("now")),
        UNIQUE(team_id, user_id),
        FOREIGN KEY (team_id) REFERENCES teams(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL,
        name TEXT,
        age INTEGER,
        cycle_status TEXT,
        goals TEXT,
        sport TEXT,
        event_date TEXT,
        desired_phase TEXT,
        cycles_data TEXT,
        training_load TEXT,
        acl_history TEXT,
        avg_cycle_length INTEGER DEFAULT 28,
        last_period_start TEXT,
        updated_at TEXT DEFAULT (datetime("now")),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS journal_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        entry_date TEXT NOT NULL,
        cycle_day INTEGER,
        phase TEXT,
        hrv TEXT,
        sleep_quality INTEGER,
        sleep_hours REAL,
        energy TEXT,
        soreness TEXT,
        pain_notes TEXT,
        workout TEXT,
        rpe INTEGER,
        motivation INTEGER,
        perf_notes TEXT,
        flow TEXT,
        cramps TEXT,
        mucus TEXT,
        digestion TEXT,
        symptom_time TEXT,
        mood TEXT,
        cognitive TEXT,
        social TEXT,
        cravings TEXT,
        hydration TEXT,
        recovery_steps TEXT,
        environmental_temp TEXT,
        environmental_humidity TEXT,
        environmental_notes TEXT,
        injuries TEXT,
        stress_level INTEGER,
        created_at TEXT DEFAULT (datetime("now")),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS calendar_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        created_by INTEGER NOT NULL,
        creator_role TEXT NOT NULL DEFAULT "athlete",
        title TEXT NOT NULL,
        description TEXT,
        event_date TEXT NOT NULL,
        event_type TEXT DEFAULT "general",
        color TEXT DEFAULT "#C0392B",
        is_ai_generated INTEGER DEFAULT 0,
        is_editable_by_athlete INTEGER DEFAULT 1,
        created_at TEXT DEFAULT (datetime("now")),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (created_by) REFERENCES users(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS chat_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        session_name TEXT NOT NULL DEFAULT "Luna Chat",
        created_at TEXT DEFAULT (datetime("now")),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime("now")),
        FOREIGN KEY (session_id) REFERENCES chat_sessions(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS ai_predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        prediction_type TEXT NOT NULL,
        prediction_data TEXT NOT NULL,
        predicted_date TEXT,
        confidence TEXT,
        created_at TEXT DEFAULT (datetime("now")),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    conn.commit()
    conn.close()
