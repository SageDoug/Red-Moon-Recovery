const express = require('express');
const session = require('express-session');
const bcrypt = require('bcryptjs');
const Database = require('better-sqlite3');
const path = require('path');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 3000;

// ── Ensure data directory exists ──
if (!fs.existsSync('./data')) fs.mkdirSync('./data');

// ── Database Setup ──
const db = new Database('./data/redmoon.db');

db.exec(`
  CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE NOT NULL,
    email         TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TEXT DEFAULT (datetime('now'))
  );

  CREATE TABLE IF NOT EXISTS profiles (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER UNIQUE NOT NULL,
    name          TEXT,
    age           INTEGER,
    cycle_status  TEXT,
    goals         TEXT,
    sport         TEXT,
    event_date    TEXT,
    desired_phase TEXT,
    cycles_data   TEXT,
    training_load TEXT,
    acl_history   TEXT,
    updated_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
  );

  CREATE TABLE IF NOT EXISTS journal_entries (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER NOT NULL,
    entry_date     TEXT NOT NULL,
    cycle_day      INTEGER,
    phase          TEXT,
    hrv            TEXT,
    sleep_quality  INTEGER,
    sleep_hours    REAL,
    energy         TEXT,
    soreness       TEXT,
    pain_notes     TEXT,
    workout        TEXT,
    rpe            INTEGER,
    motivation     INTEGER,
    perf_notes     TEXT,
    flow           TEXT,
    cramps         TEXT,
    mucus          TEXT,
    digestion      TEXT,
    symptom_time   TEXT,
    mood           TEXT,
    cognitive      TEXT,
    social         TEXT,
    cravings       TEXT,
    hydration      TEXT,
    recovery_steps TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
  );
`);

// ── Middleware ──
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(express.static(path.join(__dirname, 'public')));
app.use(session({
  secret: process.env.SESSION_SECRET || 'redmoon-dev-secret-change-in-production',
  resave: false,
  saveUninitialized: false,
  cookie: { maxAge: 7 * 24 * 60 * 60 * 1000 } // 7 days
}));

// ── Auth Middleware ──
function requireAuth(req, res, next) {
  if (!req.session.userId) return res.status(401).json({ error: 'Not logged in' });
  next();
}

// ══════════════════════════════════════
//  AUTH ROUTES
// ══════════════════════════════════════

app.post('/api/register', (req, res) => {
  const { username, email, password } = req.body;
  if (!username || !email || !password)
    return res.json({ success: false, error: 'All fields are required.' });
  if (password.length < 6)
    return res.json({ success: false, error: 'Password must be at least 6 characters.' });
  try {
    const hash = bcrypt.hashSync(password, 10);
    const result = db.prepare(
      'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)'
    ).run(username.trim().toLowerCase(), email.trim().toLowerCase(), hash);
    req.session.userId = result.lastInsertRowid;
    req.session.username = username.trim();
    res.json({ success: true, username: username.trim() });
  } catch (e) {
    if (e.message.includes('UNIQUE'))
      res.json({ success: false, error: 'Username or email already taken.' });
    else
      res.json({ success: false, error: 'Registration failed. Please try again.' });
  }
});

app.post('/api/login', (req, res) => {
  const { username, password } = req.body;
  if (!username || !password)
    return res.json({ success: false, error: 'Username and password are required.' });
  const user = db.prepare('SELECT * FROM users WHERE username = ?').get(username.trim().toLowerCase());
  if (!user || !bcrypt.compareSync(password, user.password_hash))
    return res.json({ success: false, error: 'Invalid username or password.' });
  req.session.userId = user.id;
  req.session.username = user.username;
  res.json({ success: true, username: user.username });
});

app.post('/api/logout', (req, res) => {
  req.session.destroy();
  res.json({ success: true });
});

app.get('/api/me', (req, res) => {
  if (req.session.userId)
    res.json({ loggedIn: true, username: req.session.username, userId: req.session.userId });
  else
    res.json({ loggedIn: false });
});

// ══════════════════════════════════════
//  PROFILE ROUTES
// ══════════════════════════════════════

app.get('/api/profile', requireAuth, (req, res) => {
  const profile = db.prepare('SELECT * FROM profiles WHERE user_id = ?').get(req.session.userId);
  res.json({ success: true, profile: profile || null });
});

app.post('/api/profile', requireAuth, (req, res) => {
  const { name, age, cycle_status, goals, sport, event_date, desired_phase, cycles_data, training_load, acl_history } = req.body;
  const existing = db.prepare('SELECT id FROM profiles WHERE user_id = ?').get(req.session.userId);
  if (existing) {
    db.prepare(`
      UPDATE profiles SET name=?, age=?, cycle_status=?, goals=?, sport=?,
      event_date=?, desired_phase=?, cycles_data=?, training_load=?, acl_history=?,
      updated_at=datetime('now') WHERE user_id=?
    `).run(name, age, cycle_status, JSON.stringify(goals), sport, event_date, desired_phase, cycles_data, training_load, acl_history, req.session.userId);
  } else {
    db.prepare(`
      INSERT INTO profiles (user_id, name, age, cycle_status, goals, sport, event_date, desired_phase, cycles_data, training_load, acl_history)
      VALUES (?,?,?,?,?,?,?,?,?,?,?)
    `).run(req.session.userId, name, age, cycle_status, JSON.stringify(goals), sport, event_date, desired_phase, cycles_data, training_load, acl_history);
  }
  res.json({ success: true });
});

// ══════════════════════════════════════
//  JOURNAL ROUTES
// ══════════════════════════════════════

app.post('/api/journal', requireAuth, (req, res) => {
  const e = req.body;
  db.prepare(`
    INSERT INTO journal_entries
    (user_id, entry_date, cycle_day, phase, hrv, sleep_quality, sleep_hours, energy,
     soreness, pain_notes, workout, rpe, motivation, perf_notes, flow, cramps, mucus,
     digestion, symptom_time, mood, cognitive, social, cravings, hydration, recovery_steps)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
  `).run(
    req.session.userId,
    e.entry_date, e.cycle_day || null, e.phase, e.hrv,
    e.sleep_quality, e.sleep_hours || null, e.energy, e.soreness, e.pain_notes,
    e.workout, e.rpe, e.motivation, e.perf_notes,
    e.flow, e.cramps, e.mucus, e.digestion, e.symptom_time,
    e.mood, e.cognitive, e.social, e.cravings, e.hydration,
    JSON.stringify(e.recovery_steps || [])
  );
  res.json({ success: true });
});

app.get('/api/journal', requireAuth, (req, res) => {
  const entries = db.prepare(
    'SELECT * FROM journal_entries WHERE user_id = ? ORDER BY entry_date DESC'
  ).all(req.session.userId);
  res.json({ success: true, entries });
});

app.get('/api/journal/:id', requireAuth, (req, res) => {
  const entry = db.prepare(
    'SELECT * FROM journal_entries WHERE id = ? AND user_id = ?'
  ).get(req.params.id, req.session.userId);
  if (!entry) return res.json({ success: false, error: 'Entry not found' });
  res.json({ success: true, entry });
});

app.delete('/api/journal/:id', requireAuth, (req, res) => {
  db.prepare('DELETE FROM journal_entries WHERE id = ? AND user_id = ?')
    .run(req.params.id, req.session.userId);
  res.json({ success: true });
});

// ── Start Server ──
app.listen(PORT, () => {
  console.log(`🌕 Red Moon Recovery running on http://localhost:${PORT}`);
});
