var express = require('express');
var session = require('express-session');
var bcrypt = require('bcryptjs');
var Database = require('better-sqlite3');
var path = require('path');
var fs = require('fs');
var fetch = require('node-fetch');

var app = express();
var PORT = process.env.PORT || 3000;

// Create data folder if it does not exist
if (!fs.existsSync('./data')) {
  fs.mkdirSync('./data');
}

// Open database
var db = new Database('./data/redmoon.db');

// Create tables using separate statements to avoid template literal issues
db.exec('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, created_at TEXT DEFAULT (datetime("now")))');

db.exec('CREATE TABLE IF NOT EXISTS profiles (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER UNIQUE NOT NULL, name TEXT, age INTEGER, cycle_status TEXT, goals TEXT, sport TEXT, event_date TEXT, desired_phase TEXT, cycles_data TEXT, training_load TEXT, acl_history TEXT, updated_at TEXT DEFAULT (datetime("now")), FOREIGN KEY (user_id) REFERENCES users(id))');

db.exec('CREATE TABLE IF NOT EXISTS journal_entries (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, entry_date TEXT NOT NULL, cycle_day INTEGER, phase TEXT, hrv TEXT, sleep_quality INTEGER, sleep_hours REAL, energy TEXT, soreness TEXT, pain_notes TEXT, workout TEXT, rpe INTEGER, motivation INTEGER, perf_notes TEXT, flow TEXT, cramps TEXT, mucus TEXT, digestion TEXT, symptom_time TEXT, mood TEXT, cognitive TEXT, social TEXT, cravings TEXT, hydration TEXT, recovery_steps TEXT, created_at TEXT DEFAULT (datetime("now")), FOREIGN KEY (user_id) REFERENCES users(id))');

db.exec('CREATE TABLE IF NOT EXISTS chat_sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, session_name TEXT NOT NULL DEFAULT "Luna Chat", created_at TEXT DEFAULT (datetime("now")), FOREIGN KEY (user_id) REFERENCES users(id))');

db.exec('CREATE TABLE IF NOT EXISTS chat_messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER NOT NULL, user_id INTEGER NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT DEFAULT (datetime("now")), FOREIGN KEY (session_id) REFERENCES chat_sessions(id), FOREIGN KEY (user_id) REFERENCES users(id))');

db.exec('CREATE TABLE IF NOT EXISTS chat_insights (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER UNIQUE NOT NULL, insights TEXT, updated_at TEXT DEFAULT (datetime("now")), FOREIGN KEY (user_id) REFERENCES users(id))');

// Middleware
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(express.static(__dirname, 'public'));
app.use(session({
  secret: process.env.SESSION_SECRET || 'redmoon-secret-key',
  resave: false,
  saveUninitialized: false,
  cookie: { maxAge: 7 * 24 * 60 * 60 * 1000 }
}));

function requireAuth(req, res, next) {
  if (!req.session.userId) {
    return res.status(401).json({ error: 'Not logged in' });
  }
  next();
}

// ── AUTH ──

app.post('/api/register', function(req, res) {
  var username = req.body.username;
  var email = req.body.email;
  var password = req.body.password;

  if (!username || !email || !password) {
    return res.json({ success: false, error: 'All fields are required.' });
  }
  if (password.length < 6) {
    return res.json({ success: false, error: 'Password must be at least 6 characters.' });
  }
  try {
    var hash = bcrypt.hashSync(password, 10);
    var result = db.prepare('INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)').run(username.trim().toLowerCase(), email.trim().toLowerCase(), hash);
    req.session.userId = result.lastInsertRowid;
    req.session.username = username.trim();
    res.json({ success: true, username: username.trim() });
  } catch (e) {
    if (e.message.indexOf('UNIQUE') !== -1) {
      res.json({ success: false, error: 'Username or email already taken.' });
    } else {
      res.json({ success: false, error: 'Registration failed. Please try again.' });
    }
  }
});

app.post('/api/login', function(req, res) {
  var username = req.body.username;
  var password = req.body.password;

  if (!username || !password) {
    return res.json({ success: false, error: 'Username and password are required.' });
  }
  var user = db.prepare('SELECT * FROM users WHERE username = ?').get(username.trim().toLowerCase());
  if (!user || !bcrypt.compareSync(password, user.password_hash)) {
    return res.json({ success: false, error: 'Invalid username or password.' });
  }
  req.session.userId = user.id;
  req.session.username = user.username;
  res.json({ success: true, username: user.username });
});

app.post('/api/logout', function(req, res) {
  req.session.destroy();
  res.json({ success: true });
});

app.get('/api/me', function(req, res) {
  if (req.session.userId) {
    res.json({ loggedIn: true, username: req.session.username });
  } else {
    res.json({ loggedIn: false });
  }
});

// ── PROFILE ──

app.get('/api/profile', requireAuth, function(req, res) {
  var profile = db.prepare('SELECT * FROM profiles WHERE user_id = ?').get(req.session.userId);
  res.json({ success: true, profile: profile || null });
});

app.post('/api/profile', requireAuth, function(req, res) {
  var b = req.body;
  var existing = db.prepare('SELECT id FROM profiles WHERE user_id = ?').get(req.session.userId);
  if (existing) {
    db.prepare('UPDATE profiles SET name=?, age=?, cycle_status=?, goals=?, sport=?, event_date=?, desired_phase=?, cycles_data=?, training_load=?, acl_history=?, updated_at=datetime("now") WHERE user_id=?').run(b.name, b.age, b.cycle_status, JSON.stringify(b.goals), b.sport, b.event_date, b.desired_phase, b.cycles_data, b.training_load, b.acl_history, req.session.userId);
  } else {
    db.prepare('INSERT INTO profiles (user_id, name, age, cycle_status, goals, sport, event_date, desired_phase, cycles_data, training_load, acl_history) VALUES (?,?,?,?,?,?,?,?,?,?,?)').run(req.session.userId, b.name, b.age, b.cycle_status, JSON.stringify(b.goals), b.sport, b.event_date, b.desired_phase, b.cycles_data, b.training_load, b.acl_history);
  }
  res.json({ success: true });
});

// ── JOURNAL ──

app.post('/api/journal', requireAuth, function(req, res) {
  var e = req.body;
  db.prepare('INSERT INTO journal_entries (user_id, entry_date, cycle_day, phase, hrv, sleep_quality, sleep_hours, energy, soreness, pain_notes, workout, rpe, motivation, perf_notes, flow, cramps, mucus, digestion, symptom_time, mood, cognitive, social, cravings, hydration, recovery_steps) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)').run(req.session.userId, e.entry_date, e.cycle_day || null, e.phase, e.hrv, e.sleep_quality, e.sleep_hours || null, e.energy, e.soreness, e.pain_notes, e.workout, e.rpe, e.motivation, e.perf_notes, e.flow, e.cramps, e.mucus, e.digestion, e.symptom_time, e.mood, e.cognitive, e.social, e.cravings, e.hydration, JSON.stringify(e.recovery_steps || []));
  res.json({ success: true });
});

app.get('/api/journal', requireAuth, function(req, res) {
  var entries = db.prepare('SELECT * FROM journal_entries WHERE user_id = ? ORDER BY entry_date DESC').all(req.session.userId);
  res.json({ success: true, entries: entries });
});

app.delete('/api/journal/:id', requireAuth, function(req, res) {
  db.prepare('DELETE FROM journal_entries WHERE id = ? AND user_id = ?').run(req.params.id, req.session.userId);
  res.json({ success: true });
});

// ── AI CHAT - GEMINI ──

function buildSystemPrompt(userId) {
  var profile = db.prepare('SELECT * FROM profiles WHERE user_id = ?').get(userId);
  var entries = db.prepare('SELECT * FROM journal_entries WHERE user_id = ? ORDER BY entry_date DESC LIMIT 10').all(userId);

  var profileCtx = 'No profile saved yet.';
  if (profile) {
    var goals = [];
    try { goals = JSON.parse(profile.goals || '[]'); } catch(err) {}
    profileCtx = 'Name: ' + (profile.name || '?') + ' | Age: ' + (profile.age || '?') + ' | Cycle status: ' + (profile.cycle_status || '?') + ' | Sport: ' + (profile.sport || '?') + ' | Goals: ' + (goals.join(', ') || 'none') + ' | Training load: ' + (profile.training_load || '?') + ' | ACL history: ' + (profile.acl_history || '?') + ' | Event date: ' + (profile.event_date || 'none') + ' | Desired phase: ' + (profile.desired_phase || '?');
  }

  var journalCtx = 'No journal entries yet.';
  if (entries.length > 0) {
    journalCtx = entries.map(function(e) {
      return '[' + e.entry_date + '] Day ' + (e.cycle_day || '?') + ', ' + (e.phase || '?') + ' phase - Sleep: ' + e.sleep_quality + '/10 (' + (e.sleep_hours || '?') + 'hrs), Energy: ' + (e.energy || '?') + ', RPE: ' + e.rpe + ', Motivation: ' + e.motivation + ', Mood: ' + (e.mood || '?') + ', Flow: ' + (e.flow || '?') + ', Cramps: ' + (e.cramps || '?') + ', Workout: ' + (e.workout || '?') + ', Notes: ' + (e.perf_notes || 'none');
    }).join('\n');
  }

  var today = new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });

  return 'You are Luna, the AI guide for Red Moon Recovery, a menstrual cycle tracking app for athletes. You are warm, empathetic, knowledgeable, and evidence-based. You speak like a supportive coach who deeply understands female physiology and sports performance.\n\nYOUR ROLE:\n- Have natural flowing conversations. Ask thoughtful follow-up questions based on what the user shares.\n- Reference the users actual logged data and profile when relevant.\n- Help users understand the four cycle phases (Menstrual, Follicular, Ovulatory, Luteal) and how they affect training, recovery, mood, energy, and injury risk.\n- Give actionable personalized advice based on their phase, goals, and logged patterns.\n- Flag concerning patterns gently such as consistently low energy, high RPE with low motivation, or recurring pain.\n- Topics you cover: cycle phases, nutrition by phase, strength training timing, ACL injury prevention, sleep, stress, recovery, reverse mapping for events, hormonal health, performance optimization.\n- Ask ONE good follow-up question per response.\n- Keep responses conversational, 2 to 4 short paragraphs max unless they ask for more detail.\n- If asked about medical diagnosis or medication recommend seeing a healthcare provider.\n\nCONVERSATION STYLE:\n- Warm and personal. Use the users name when you know it.\n- Reference their actual journal data when you can.\n- Celebrate wins and be encouraging but honest.\n- End most responses with a question to keep the dialogue going.\n\nUSER PROFILE:\n' + profileCtx + '\n\nRECENT JOURNAL DATA:\n' + journalCtx + '\n\nToday: ' + today;
}

function callGemini(apiKey, systemPrompt, messages, maxTokens) {
  var url = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=' + apiKey;

  var contents = messages.map(function(m) {
    return {
      role: m.role === 'assistant' ? 'model' : 'user',
      parts: [{ text: m.content }]
    };
  });

  var body = {
    contents: contents,
    generationConfig: { maxOutputTokens: maxTokens || 1024, temperature: 0.85 }
  };

  if (systemPrompt) {
    body.system_instruction = { parts: [{ text: systemPrompt }] };
  }

  return fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  }).then(function(response) {
    if (!response.ok) {
      return response.text().then(function(errText) {
        console.error('Gemini API error:', response.status, errText);
        throw new Error('Gemini API error: ' + response.status);
      });
    }
    return response.json();
  }).then(function(data) {
    var text = data.candidates && data.candidates[0] && data.candidates[0].content && data.candidates[0].content.parts && data.candidates[0].content.parts[0] && data.candidates[0].content.parts[0].text;
    if (!text) throw new Error('Empty response from Gemini');
    return text;
  });
}

function getOrCreateSession(userId) {
  var sess = db.prepare('SELECT * FROM chat_sessions WHERE user_id = ? ORDER BY created_at DESC LIMIT 1').get(userId);
  if (!sess) {
    var r = db.prepare('INSERT INTO chat_sessions (user_id, session_name) VALUES (?, ?)').run(userId, 'Luna Chat');
    sess = { id: r.lastInsertRowid, session_name: 'Luna Chat' };
  }
  return sess;
}

app.get('/api/chat/history', requireAuth, function(req, res) {
  var sess = getOrCreateSession(req.session.userId);
  var messages = db.prepare('SELECT role, content, created_at FROM chat_messages WHERE session_id = ? ORDER BY created_at ASC').all(sess.id);
  res.json({ success: true, messages: messages, sessionId: sess.id });
});

app.get('/api/chat/sessions', requireAuth, function(req, res) {
  var sessions = db.prepare('SELECT id, session_name, created_at FROM chat_sessions WHERE user_id = ? ORDER BY created_at DESC').all(req.session.userId);
  res.json({ success: true, sessions: sessions });
});

app.post('/api/chat/new-session', requireAuth, function(req, res) {
  var name = req.body.name || ('Chat - ' + new Date().toLocaleDateString());
  var r = db.prepare('INSERT INTO chat_sessions (user_id, session_name) VALUES (?, ?)').run(req.session.userId, name);
  res.json({ success: true, sessionId: r.lastInsertRowid });
});

app.get('/api/chat/session/:id', requireAuth, function(req, res) {
  var sess = db.prepare('SELECT * FROM chat_sessions WHERE id = ? AND user_id = ?').get(req.params.id, req.session.userId);
  if (!sess) return res.json({ success: false, error: 'Not found' });
  var messages = db.prepare('SELECT role, content, created_at FROM chat_messages WHERE session_id = ? ORDER BY created_at ASC').all(req.params.id);
  res.json({ success: true, messages: messages, session: sess });
});

app.delete('/api/chat/session/:id', requireAuth, function(req, res) {
  var sess = db.prepare('SELECT id FROM chat_sessions WHERE id = ? AND user_id = ?').get(req.params.id, req.session.userId);
  if (!sess) return res.json({ success: false, error: 'Not found' });
  db.prepare('DELETE FROM chat_messages WHERE session_id = ?').run(req.params.id);
  db.prepare('DELETE FROM chat_sessions WHERE id = ?').run(req.params.id);
  res.json({ success: true });
});

app.post('/api/chat/send', requireAuth, function(req, res) {
  var message = req.body.message;
  var sessionId = req.body.sessionId;

  if (!message || !message.trim()) {
    return res.json({ success: false, error: 'Message cannot be empty.' });
  }

  var apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) {
    return res.json({ success: false, error: 'GEMINI_API_KEY is not set. Get a free key at https://aistudio.google.com and add it as a Codespace secret named GEMINI_API_KEY.' });
  }

  var sess = null;
  if (sessionId) {
    sess = db.prepare('SELECT * FROM chat_sessions WHERE id = ? AND user_id = ?').get(sessionId, req.session.userId);
  }
  if (!sess) sess = getOrCreateSession(req.session.userId);

  db.prepare('INSERT INTO chat_messages (session_id, user_id, role, content) VALUES (?, ?, ?, ?)').run(sess.id, req.session.userId, 'user', message.trim());

  var history = db.prepare('SELECT role, content FROM chat_messages WHERE session_id = ? ORDER BY created_at ASC').all(sess.id);
  var systemPrompt = buildSystemPrompt(req.session.userId);

  callGemini(apiKey, systemPrompt, history, 1024).then(function(reply) {
    db.prepare('INSERT INTO chat_messages (session_id, user_id, role, content) VALUES (?, ?, ?, ?)').run(sess.id, req.session.userId, 'assistant', reply);

    var count = db.prepare('SELECT COUNT(*) as c FROM chat_messages WHERE session_id = ? AND role = ?').get(sess.id, 'assistant').c;
    if (count % 6 === 0) {
      saveInsights(req.session.userId, sess.id, apiKey);
    }

    res.json({ success: true, reply: reply, sessionId: sess.id });
  }).catch(function(err) {
    console.error('Chat error:', err.message);
    res.json({ success: false, error: 'AI service error. Please check your GEMINI_API_KEY is correct and try again.' });
  });
});

app.get('/api/chat/insights', requireAuth, function(req, res) {
  var row = db.prepare('SELECT insights FROM chat_insights WHERE user_id = ?').get(req.session.userId);
  res.json({ success: true, insights: row ? JSON.parse(row.insights || '[]') : [] });
});

function saveInsights(userId, sessionId, apiKey) {
  var msgs = db.prepare('SELECT role, content FROM chat_messages WHERE session_id = ? ORDER BY created_at DESC LIMIT 20').all(sessionId).reverse();
  var conversation = msgs.map(function(m) { return m.role + ': ' + m.content; }).join('\n');
  var prompt = 'Extract key health and cycle insights from this conversation as a JSON array. Each item must have category and insight string fields. Categories: cycle_pattern, performance, recovery, nutrition, injury_risk, mental_health, goal. Return ONLY a valid JSON array, no explanation, no markdown.\n\nConversation:\n' + conversation;

  callGemini(apiKey, '', [{ role: 'user', content: prompt }], 512).then(function(text) {
    var clean = text.replace(/```json/g, '').replace(/```/g, '').trim();
    var insights = JSON.parse(clean);
    var existing = db.prepare('SELECT id FROM chat_insights WHERE user_id = ?').get(userId);
    if (existing) {
      db.prepare('UPDATE chat_insights SET insights=?, updated_at=datetime("now") WHERE user_id=?').run(JSON.stringify(insights), userId);
    } else {
      db.prepare('INSERT INTO chat_insights (user_id, insights) VALUES (?, ?)').run(userId, JSON.stringify(insights));
    }
  }).catch(function(e) {
    console.error('saveInsights failed:', e.message);
  });
}

// Start server
app.listen(PORT, function() {
  console.log('Red Moon Recovery running on http://localhost:' + PORT);
  if (!process.env.GEMINI_API_KEY) {
    console.log('WARNING: GEMINI_API_KEY is not set. Get a free key at https://aistudio.google.com');
  }
});
