require('dotenv').config();
const express = require('express');
const session = require('express-session');
const bcrypt = require('bcryptjs');
const Database = require('better-sqlite3');
const path = require('path');
const fs = require('fs');
const fetch = require('node-fetch');

const app = express();
const PORT = process.env.PORT || 3000;

if (!fs.existsSync('./data')) fs.mkdirSync('./data');

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
  CREATE TABLE IF NOT EXISTS chat_sessions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL,
    session_name TEXT NOT NULL DEFAULT 'Luna Chat',
    created_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
  );
  CREATE TABLE IF NOT EXISTS chat_messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    role       TEXT NOT NULL,
    content    TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
  );
  CREATE TABLE IF NOT EXISTS chat_insights (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER UNIQUE NOT NULL,
    insights   TEXT,
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
  );
`);

app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(express.static(path.join(__dirname, 'public')));
app.use(session({
  secret: process.env.SESSION_SECRET || 'redmoon-dev-secret',
  resave: false,
  saveUninitialized: false,
  cookie: { maxAge: 7 * 24 * 60 * 60 * 1000 }
}));

function requireAuth(req, res, next) {
  if (!req.session.userId) return res.status(401).json({ error: 'Not logged in' });
  next();
}

// ── AUTH ──
app.post('/api/register', (req, res) => {
  const { username, email, password } = req.body;
  if (!username || !email || !password) return res.json({ success: false, error: 'All fields are required.' });
  if (password.length < 6) return res.json({ success: false, error: 'Password must be at least 6 characters.' });
  try {
    const hash = bcrypt.hashSync(password, 10);
    const result = db.prepare('INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)').run(username.trim().toLowerCase(), email.trim().toLowerCase(), hash);
    req.session.userId = result.lastInsertRowid;
    req.session.username = username.trim();
    res.json({ success: true, username: username.trim() });
  } catch (e) {
    res.json({ success: false, error: e.message.includes('UNIQUE') ? 'Username or email already taken.' : 'Registration failed.' });
  }
});

app.post('/api/login', (req, res) => {
  const { username, password } = req.body;
  if (!username || !password) return res.json({ success: false, error: 'Username and password are required.' });
  const user = db.prepare('SELECT * FROM users WHERE username = ?').get(username.trim().toLowerCase());
  if (!user || !bcrypt.compareSync(password, user.password_hash)) return res.json({ success: false, error: 'Invalid username or password.' });
  req.session.userId = user.id;
  req.session.username = user.username;
  res.json({ success: true, username: user.username });
});

app.post('/api/logout', (req, res) => { req.session.destroy(); res.json({ success: true }); });

app.get('/api/me', (req, res) => {
  if (req.session.userId) res.json({ loggedIn: true, username: req.session.username });
  else res.json({ loggedIn: false });
});

// ── PROFILE ──
app.get('/api/profile', requireAuth, (req, res) => {
  const profile = db.prepare('SELECT * FROM profiles WHERE user_id = ?').get(req.session.userId);
  res.json({ success: true, profile: profile || null });
});

app.post('/api/profile', requireAuth, (req, res) => {
  const { name, age, cycle_status, goals, sport, event_date, desired_phase, cycles_data, training_load, acl_history } = req.body;
  const existing = db.prepare('SELECT id FROM profiles WHERE user_id = ?').get(req.session.userId);
  if (existing) {
    db.prepare(`UPDATE profiles SET name=?,age=?,cycle_status=?,goals=?,sport=?,event_date=?,desired_phase=?,cycles_data=?,training_load=?,acl_history=?,updated_at=datetime('now') WHERE user_id=?`).run(name, age, cycle_status, JSON.stringify(goals), sport, event_date, desired_phase, cycles_data, training_load, acl_history, req.session.userId);
  } else {
    db.prepare(`INSERT INTO profiles (user_id,name,age,cycle_status,goals,sport,event_date,desired_phase,cycles_data,training_load,acl_history) VALUES (?,?,?,?,?,?,?,?,?,?,?)`).run(req.session.userId, name, age, cycle_status, JSON.stringify(goals), sport, event_date, desired_phase, cycles_data, training_load, acl_history);
  }
  res.json({ success: true });
});

// ── JOURNAL ──
app.post('/api/journal', requireAuth, (req, res) => {
  const e = req.body;
  db.prepare(`INSERT INTO journal_entries (user_id,entry_date,cycle_day,phase,hrv,sleep_quality,sleep_hours,energy,soreness,pain_notes,workout,rpe,motivation,perf_notes,flow,cramps,mucus,digestion,symptom_time,mood,cognitive,social,cravings,hydration,recovery_steps) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`).run(req.session.userId, e.entry_date, e.cycle_day||null, e.phase, e.hrv, e.sleep_quality, e.sleep_hours||null, e.energy, e.soreness, e.pain_notes, e.workout, e.rpe, e.motivation, e.perf_notes, e.flow, e.cramps, e.mucus, e.digestion, e.symptom_time, e.mood, e.cognitive, e.social, e.cravings, e.hydration, JSON.stringify(e.recovery_steps||[]));
  res.json({ success: true });
});

app.get('/api/journal', requireAuth, (req, res) => {
  const entries = db.prepare('SELECT * FROM journal_entries WHERE user_id = ? ORDER BY entry_date DESC').all(req.session.userId);
  res.json({ success: true, entries });
});

app.delete('/api/journal/:id', requireAuth, (req, res) => {
  db.prepare('DELETE FROM journal_entries WHERE id = ? AND user_id = ?').run(req.params.id, req.session.userId);
  res.json({ success: true });
});

// ══════════════════════════════════════
//  AI CHAT
// ══════════════════════════════════════

function buildSystemPrompt(userId) {
  const profile = db.prepare('SELECT * FROM profiles WHERE user_id = ?').get(userId);
  const entries = db.prepare('SELECT * FROM journal_entries WHERE user_id = ? ORDER BY entry_date DESC LIMIT 10').all(userId);

  let profileCtx = 'No profile saved yet.';
  if (profile) {
    let goals = [];
    try { goals = JSON.parse(profile.goals || '[]'); } catch(e) {}
    profileCtx = `Name: ${profile.name||'?'} | Age: ${profile.age||'?'} | Cycle status: ${profile.cycle_status||'?'} | Sport: ${profile.sport||'?'} | Goals: ${goals.join(', ')||'none'} | Training load: ${profile.training_load||'?'} | ACL history: ${profile.acl_history||'?'} | Event date: ${profile.event_date||'none'} | Desired phase: ${profile.desired_phase||'?'}`;
  }

  let journalCtx = 'No journal entries yet.';
  if (entries.length > 0) {
    journalCtx = entries.map(e =>
      `[${e.entry_date}] Day ${e.cycle_day||'?'}, ${e.phase||'?'} phase — Sleep: ${e.sleep_quality}/10 (${e.sleep_hours}hrs), Energy: ${e.energy||'?'}, RPE: ${e.rpe}, Motivation: ${e.motivation}, Mood: ${e.mood||'?'}, Flow: ${e.flow||'?'}, Cramps: ${e.cramps||'?'}, Workout: ${e.workout||'?'}, Notes: ${e.perf_notes||'none'}`
    ).join('\n');
  }

  return `You are Luna, the AI guide for Red Moon Recovery — a menstrual cycle tracking app for athletes. You are warm, empathetic, knowledgeable, and evidence-based. You sound like a supportive coach who deeply understands female physiology and sports performance.

YOUR ROLE:
- Have natural, flowing conversations. Ask thoughtful follow-up questions based on what the user shares.
- Reference the user's actual logged data and profile when relevant ("I noticed in your last few entries that...")
- Help users understand the four cycle phases and how they affect training, recovery, mood, energy, and injury risk
- Gather information naturally through conversation and encourage users to log it in their journal
- Give actionable, personalized advice based on their phase, goals, and logged patterns
- Flag concerning patterns gently (e.g. consistently low energy, high RPE with low motivation, recurring pain)
- Topics you cover: cycle phases, nutrition by phase, strength training timing, ACL/injury prevention, sleep, stress, recovery, reverse mapping for events, hormonal health, performance optimization
- Ask ONE good follow-up question per response to keep learning about them
- Keep responses conversational — 2-4 short paragraphs max unless they ask for detail
- If asked for medical diagnosis or medication advice, recommend seeing a healthcare provider while still being helpful

CONVERSATION STYLE:
- Warm and personal. Use the user's name when you know it.
- Reference their actual data when you can
- Celebrate wins. Be encouraging but honest.
- Never be preachy. Don't lecture.
- End most responses with a question to keep the dialogue going

USER PROFILE:
${profileCtx}

RECENT JOURNAL DATA (newest first):
${journalCtx}

Today: ${new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}`;
}

function getOrCreateSession(userId) {
  let sess = db.prepare('SELECT * FROM chat_sessions WHERE user_id = ? ORDER BY created_at DESC LIMIT 1').get(userId);
  if (!sess) {
    const r = db.prepare("INSERT INTO chat_sessions (user_id, session_name) VALUES (?, 'Luna Chat')").run(userId);
    sess = { id: r.lastInsertRowid, session_name: 'Luna Chat' };
  }
  return sess;
}

app.get('/api/chat/history', requireAuth, (req, res) => {
  const sess = getOrCreateSession(req.session.userId);
  const messages = db.prepare('SELECT role, content, created_at FROM chat_messages WHERE session_id = ? ORDER BY created_at ASC').all(sess.id);
  res.json({ success: true, messages, sessionId: sess.id });
});

app.get('/api/chat/sessions', requireAuth, (req, res) => {
  const sessions = db.prepare('SELECT id, session_name, created_at FROM chat_sessions WHERE user_id = ? ORDER BY created_at DESC').all(req.session.userId);
  res.json({ success: true, sessions });
});

app.post('/api/chat/new-session', requireAuth, (req, res) => {
  const name = req.body.name || `Chat — ${new Date().toLocaleDateString()}`;
  const r = db.prepare('INSERT INTO chat_sessions (user_id, session_name) VALUES (?, ?)').run(req.session.userId, name);
  res.json({ success: true, sessionId: r.lastInsertRowid });
});

app.get('/api/chat/session/:id', requireAuth, (req, res) => {
  const sess = db.prepare('SELECT * FROM chat_sessions WHERE id = ? AND user_id = ?').get(req.params.id, req.session.userId);
  if (!sess) return res.json({ success: false, error: 'Not found' });
  const messages = db.prepare('SELECT role, content, created_at FROM chat_messages WHERE session_id = ? ORDER BY created_at ASC').all(req.params.id);
  res.json({ success: true, messages, session: sess });
});

app.delete('/api/chat/session/:id', requireAuth, (req, res) => {
  const sess = db.prepare('SELECT id FROM chat_sessions WHERE id = ? AND user_id = ?').get(req.params.id, req.session.userId);
  if (!sess) return res.json({ success: false, error: 'Not found' });
  db.prepare('DELETE FROM chat_messages WHERE session_id = ?').run(req.params.id);
  db.prepare('DELETE FROM chat_sessions WHERE id = ?').run(req.params.id);
  res.json({ success: true });
});

app.post('/api/chat/send', requireAuth, async (req, res) => {
  const { message, sessionId } = req.body;
  if (!message || !message.trim()) return res.json({ success: false, error: 'Message cannot be empty.' });

  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) return res.json({ success: false, error: 'ANTHROPIC_API_KEY not set. See README for setup instructions.' });

  let sess = sessionId
    ? db.prepare('SELECT * FROM chat_sessions WHERE id = ? AND user_id = ?').get(sessionId, req.session.userId)
    : null;
  if (!sess) sess = getOrCreateSession(req.session.userId);

  // Save user message
  db.prepare('INSERT INTO chat_messages (session_id, user_id, role, content) VALUES (?, ?, ?, ?)').run(sess.id, req.session.userId, 'user', message.trim());

  // Build message history (last 40 messages to stay within context)
  const history = db.prepare('SELECT role, content FROM chat_messages WHERE session_id = ? ORDER BY created_at ASC').all(sess.id);
  const apiMessages = history.map(m => ({ role: m.role, content: m.content }));

  try {
    const response = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': apiKey,
        'anthropic-version': '2023-06-01'
      },
      body: JSON.stringify({
        model: 'claude-sonnet-4-20250514',
        max_tokens: 1024,
        system: buildSystemPrompt(req.session.userId),
        messages: apiMessages
      })
    });

    if (!response.ok) {
      const err = await response.text();
      console.error('Anthropic API error:', err);
      return res.json({ success: false, error: 'AI service error. Please try again.' });
    }

    const data = await response.json();
    const reply = data.content?.[0]?.text || "I'm sorry, I couldn't generate a response. Please try again.";

    // Save assistant reply
    db.prepare('INSERT INTO chat_messages (session_id, user_id, role, content) VALUES (?, ?, ?, ?)').run(sess.id, req.session.userId, 'assistant', reply);

    // Every 6 assistant messages, extract and save insights in background
    const count = db.prepare("SELECT COUNT(*) as c FROM chat_messages WHERE session_id = ? AND role = 'assistant'").get(sess.id).c;
    if (count % 6 === 0) saveInsights(req.session.userId, sess.id, apiKey).catch(e => console.error('Insight error:', e));

    res.json({ success: true, reply, sessionId: sess.id });

  } catch (err) {
    console.error('Chat send error:', err);
    res.json({ success: false, error: 'Could not reach AI. Check API key and connection.' });
  }
});

app.get('/api/chat/insights', requireAuth, (req, res) => {
  const row = db.prepare('SELECT insights FROM chat_insights WHERE user_id = ?').get(req.session.userId);
  res.json({ success: true, insights: row ? JSON.parse(row.insights || '[]') : [] });
});

async function saveInsights(userId, sessionId, apiKey) {
  const msgs = db.prepare('SELECT role, content FROM chat_messages WHERE session_id = ? ORDER BY created_at DESC LIMIT 20').all(sessionId).reverse();
  const prompt = `Extract key health/cycle insights from this conversation as a JSON array. Each item: {"category":"cycle_pattern|performance|recovery|nutrition|injury_risk|mental_health|goal","insight":"specific finding"}. Only meaningful specific insights. Return ONLY valid JSON array, nothing else.\n\nConversation:\n${msgs.map(m=>`${m.role}: ${m.content}`).join('\n')}`;

  try {
    const r = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'x-api-key': apiKey, 'anthropic-version': '2023-06-01' },
      body: JSON.stringify({ model: 'claude-sonnet-4-20250514', max_tokens: 512, messages: [{ role: 'user', content: prompt }] })
    });
    const data = await r.json();
    const text = data.content?.[0]?.text || '[]';
    const insights = JSON.parse(text.replace(/```json|```/g, '').trim());
    const existing = db.prepare('SELECT id FROM chat_insights WHERE user_id = ?').get(userId);
    if (existing) db.prepare("UPDATE chat_insights SET insights=?,updated_at=datetime('now') WHERE user_id=?").run(JSON.stringify(insights), userId);
    else db.prepare('INSERT INTO chat_insights (user_id, insights) VALUES (?, ?)').run(userId, JSON.stringify(insights));
  } catch(e) { console.error('saveInsights failed:', e); }
}

app.listen(PORT, () => {
  console.log(`🌕 Red Moon Recovery running on http://localhost:${PORT}`);
  if (!process.env.ANTHROPIC_API_KEY) {
    console.warn('⚠️  ANTHROPIC_API_KEY not set. AI chat will not work until you add it.');
  }
});
