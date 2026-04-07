import os
import json
import uuid
import sqlite3
from datetime import datetime
from functools import wraps
from flask import Flask, request, session, jsonify, send_from_directory
import bcrypt

from database import get_db, init_db
from luna_ai import LunaAI
from predictor import get_prediction

app = Flask(__name__, static_folder='static')
app.secret_key = os.environ.get('SECRET_KEY', 'redmoon-secret-2024')
init_db()


# ── Auth decorator ──

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Not logged in'}), 401
        return f(*args, **kwargs)
    return decorated

def require_role(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'user_id' not in session:
                return jsonify({'error': 'Not logged in'}), 401
            if session.get('role') not in roles:
                return jsonify({'error': 'Access denied'}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


# ── Static ──

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


# ══════════════════════════
#  AUTH
# ══════════════════════════

@app.route('/api/register', methods=['POST'])
def register():
    d = request.json or {}
    username = (d.get('username') or '').strip().lower()
    email = (d.get('email') or '').strip().lower()
    password = d.get('password') or ''
    role = d.get('role') or 'athlete'

    if role not in ('athlete', 'coach', 'trainer'):
        role = 'athlete'
    if not username or not email or not password:
        return jsonify({'success': False, 'error': 'All fields are required.'})
    if len(password) < 6:
        return jsonify({'success': False, 'error': 'Password must be at least 6 characters.'})

    try:
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        conn = get_db()
        cur = conn.execute('INSERT INTO users (username, email, password_hash, role) VALUES (?,?,?,?)',
                           (username, email, pw_hash, role))
        uid = cur.lastrowid
        conn.commit()
        conn.close()
        session['user_id'] = uid
        session['username'] = username
        session['role'] = role
        return jsonify({'success': True, 'username': username, 'role': role})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'error': 'Username or email already taken.'})
    except Exception:
        return jsonify({'success': False, 'error': 'Registration failed.'})


@app.route('/api/login', methods=['POST'])
def login():
    d = request.json or {}
    username = (d.get('username') or '').strip().lower()
    password = d.get('password') or ''

    if not username or not password:
        return jsonify({'success': False, 'error': 'Username and password required.'})

    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()

    if not user or not bcrypt.checkpw(password.encode(), user['password_hash'].encode()):
        return jsonify({'success': False, 'error': 'Invalid username or password.'})

    session['user_id'] = user['id']
    session['username'] = user['username']
    session['role'] = user['role']
    return jsonify({'success': True, 'username': user['username'], 'role': user['role']})


@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})


@app.route('/api/me')
def me():
    if 'user_id' in session:
        return jsonify({'loggedIn': True, 'username': session['username'], 'role': session['role']})
    return jsonify({'loggedIn': False})


# ══════════════════════════
#  TEAMS
# ══════════════════════════

@app.route('/api/teams', methods=['GET'])
@require_auth
def get_my_teams():
    uid = session['user_id']
    conn = get_db()
    if session['role'] == 'coach':
        rows = conn.execute('SELECT * FROM teams WHERE coach_id = ?', (uid,)).fetchall()
    else:
        rows = conn.execute('''SELECT t.* FROM teams t
            JOIN team_members tm ON tm.team_id = t.id
            WHERE tm.user_id = ?''', (uid,)).fetchall()
    result = []
    for r in rows:
        t = dict(r)
        members = conn.execute('''SELECT u.id, u.username, u.role FROM users u
            JOIN team_members tm ON tm.user_id = u.id WHERE tm.team_id = ?''', (r['id'],)).fetchall()
        t['members'] = [dict(m) for m in members]
        coach = conn.execute('SELECT username FROM users WHERE id = ?', (r['coach_id'],)).fetchone()
        t['coach_name'] = coach['username'] if coach else ''
        result.append(t)
    conn.close()
    return jsonify({'success': True, 'teams': result})


@app.route('/api/teams', methods=['POST'])
@require_role('coach')
def create_team():
    d = request.json or {}
    name = (d.get('name') or '').strip()
    if not name:
        return jsonify({'success': False, 'error': 'Team name required.'})

    invite_code = str(uuid.uuid4())[:8].upper()
    conn = get_db()
    cur = conn.execute('INSERT INTO teams (name, coach_id, invite_code) VALUES (?,?,?)',
                       (name, session['user_id'], invite_code))
    team_id = cur.lastrowid
    conn.execute('INSERT INTO team_members (team_id, user_id, role) VALUES (?,?,?)',
                 (team_id, session['user_id'], 'coach'))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'invite_code': invite_code, 'team_id': team_id})


@app.route('/api/teams/join', methods=['POST'])
@require_auth
def join_team():
    d = request.json or {}
    invite_code = (d.get('invite_code') or '').strip().upper()
    if not invite_code:
        return jsonify({'success': False, 'error': 'Invite code required.'})

    conn = get_db()
    team = conn.execute('SELECT * FROM teams WHERE invite_code = ?', (invite_code,)).fetchone()
    if not team:
        conn.close()
        return jsonify({'success': False, 'error': 'Invalid invite code.'})

    existing = conn.execute('SELECT id FROM team_members WHERE team_id = ? AND user_id = ?',
                            (team['id'], session['user_id'])).fetchone()
    if existing:
        conn.close()
        return jsonify({'success': False, 'error': 'You are already on this team.'})

    conn.execute('INSERT INTO team_members (team_id, user_id, role) VALUES (?,?,?)',
                 (team['id'], session['user_id'], session['role']))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'team_name': team['name']})


@app.route('/api/teams/<int:team_id>/invite', methods=['GET'])
@require_role('coach')
def get_invite(team_id):
    conn = get_db()
    team = conn.execute('SELECT * FROM teams WHERE id = ? AND coach_id = ?',
                        (team_id, session['user_id'])).fetchone()
    conn.close()
    if not team:
        return jsonify({'success': False, 'error': 'Not found.'})
    return jsonify({'success': True, 'invite_code': team['invite_code']})


@app.route('/api/teams/<int:team_id>/members', methods=['GET'])
@require_auth
def team_members(team_id):
    conn = get_db()
    # Verify access
    member = conn.execute('SELECT * FROM team_members WHERE team_id = ? AND user_id = ?',
                          (team_id, session['user_id'])).fetchone()
    if not member:
        conn.close()
        return jsonify({'error': 'Access denied'}), 403

    members = conn.execute('''SELECT u.id, u.username, u.role, tm.joined_at
        FROM users u JOIN team_members tm ON tm.user_id = u.id
        WHERE tm.team_id = ?''', (team_id,)).fetchall()
    conn.close()
    return jsonify({'success': True, 'members': [dict(m) for m in members]})


@app.route('/api/teams/<int:team_id>/athlete/<int:athlete_id>/data', methods=['GET'])
@require_role('coach', 'trainer')
def get_athlete_data(team_id, athlete_id):
    conn = get_db()
    # Verify coach/trainer is on the team
    me_member = conn.execute('SELECT * FROM team_members WHERE team_id = ? AND user_id = ?',
                             (team_id, session['user_id'])).fetchone()
    # Verify athlete is on the team
    athlete_member = conn.execute('SELECT * FROM team_members WHERE team_id = ? AND user_id = ?',
                                  (team_id, athlete_id)).fetchone()
    if not me_member or not athlete_member:
        conn.close()
        return jsonify({'error': 'Access denied'}), 403

    entries = conn.execute('SELECT * FROM journal_entries WHERE user_id = ? ORDER BY entry_date DESC LIMIT 30',
                           (athlete_id,)).fetchall()
    profile = conn.execute('SELECT * FROM profiles WHERE user_id = ?', (athlete_id,)).fetchone()
    user = conn.execute('SELECT username, role FROM users WHERE id = ?', (athlete_id,)).fetchone()
    conn.close()

    return jsonify({
        'success': True,
        'athlete': dict(user) if user else {},
        'profile': dict(profile) if profile else {},
        'entries': [dict(e) for e in entries]
    })


# ══════════════════════════
#  PROFILE
# ══════════════════════════

@app.route('/api/profile', methods=['GET'])
@require_auth
def get_profile():
    conn = get_db()
    row = conn.execute('SELECT * FROM profiles WHERE user_id = ?', (session['user_id'],)).fetchone()
    conn.close()
    return jsonify({'success': True, 'profile': dict(row) if row else None})


@app.route('/api/profile', methods=['POST'])
@require_auth
def save_profile():
    b = request.json or {}
    uid = session['user_id']
    goals_json = json.dumps(b.get('goals') or [])
    conn = get_db()
    existing = conn.execute('SELECT id FROM profiles WHERE user_id = ?', (uid,)).fetchone()
    if existing:
        conn.execute('''UPDATE profiles SET name=?,age=?,cycle_status=?,goals=?,sport=?,event_date=?,
            desired_phase=?,cycles_data=?,training_load=?,acl_history=?,avg_cycle_length=?,
            last_period_start=?,updated_at=datetime("now") WHERE user_id=?''',
            (b.get('name'), b.get('age'), b.get('cycle_status'), goals_json, b.get('sport'),
             b.get('event_date'), b.get('desired_phase'), b.get('cycles_data'), b.get('training_load'),
             b.get('acl_history'), b.get('avg_cycle_length') or 28, b.get('last_period_start'), uid))
    else:
        conn.execute('''INSERT INTO profiles (user_id,name,age,cycle_status,goals,sport,event_date,
            desired_phase,cycles_data,training_load,acl_history,avg_cycle_length,last_period_start)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (uid, b.get('name'), b.get('age'), b.get('cycle_status'), goals_json, b.get('sport'),
             b.get('event_date'), b.get('desired_phase'), b.get('cycles_data'), b.get('training_load'),
             b.get('acl_history'), b.get('avg_cycle_length') or 28, b.get('last_period_start')))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ══════════════════════════
#  JOURNAL
# ══════════════════════════

@app.route('/api/journal', methods=['POST'])
@require_auth
def save_journal():
    e = request.json or {}
    uid = session['user_id']
    conn = get_db()
    conn.execute('''INSERT INTO journal_entries (user_id,entry_date,cycle_day,phase,hrv,sleep_quality,
        sleep_hours,energy,soreness,pain_notes,workout,rpe,motivation,perf_notes,flow,cramps,mucus,
        digestion,symptom_time,mood,cognitive,social,cravings,hydration,recovery_steps,
        environmental_temp,environmental_humidity,environmental_notes,injuries,stress_level)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        (uid, e.get('entry_date'), e.get('cycle_day'), e.get('phase'), e.get('hrv'),
         e.get('sleep_quality'), e.get('sleep_hours'), e.get('energy'), e.get('soreness'),
         e.get('pain_notes'), e.get('workout'), e.get('rpe'), e.get('motivation'), e.get('perf_notes'),
         e.get('flow'), e.get('cramps'), e.get('mucus'), e.get('digestion'), e.get('symptom_time'),
         e.get('mood'), e.get('cognitive'), e.get('social'), e.get('cravings'), e.get('hydration'),
         json.dumps(e.get('recovery_steps') or []),
         e.get('environmental_temp'), e.get('environmental_humidity'),
         e.get('environmental_notes'), e.get('injuries'), e.get('stress_level')))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/journal', methods=['GET'])
@require_auth
def get_journal():
    conn = get_db()
    rows = conn.execute('SELECT * FROM journal_entries WHERE user_id = ? ORDER BY entry_date DESC',
                        (session['user_id'],)).fetchall()
    conn.close()
    return jsonify({'success': True, 'entries': [dict(r) for r in rows]})


@app.route('/api/journal/<int:eid>', methods=['DELETE'])
@require_auth
def delete_journal(eid):
    conn = get_db()
    conn.execute('DELETE FROM journal_entries WHERE id = ? AND user_id = ?', (eid, session['user_id']))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ══════════════════════════
#  CALENDAR
# ══════════════════════════

@app.route('/api/calendar', methods=['GET'])
@require_auth
def get_calendar():
    uid = session['user_id']
    month = request.args.get('month')  # YYYY-MM
    conn = get_db()
    if month:
        rows = conn.execute('''SELECT ce.*, u.username as creator_name FROM calendar_events ce
            JOIN users u ON u.id = ce.created_by
            WHERE ce.user_id = ? AND ce.event_date LIKE ?
            ORDER BY ce.event_date ASC''', (uid, month + '%')).fetchall()
    else:
        rows = conn.execute('''SELECT ce.*, u.username as creator_name FROM calendar_events ce
            JOIN users u ON u.id = ce.created_by
            WHERE ce.user_id = ? ORDER BY ce.event_date ASC''', (uid,)).fetchall()
    conn.close()
    return jsonify({'success': True, 'events': [dict(r) for r in rows]})


@app.route('/api/calendar', methods=['POST'])
@require_auth
def add_calendar_event():
    d = request.json or {}
    uid = session['user_id']
    role = session['role']

    # Determine target user
    target_uid = d.get('target_user_id') or uid
    if target_uid != uid:
        # Coach or trainer adding for athlete — verify team membership
        conn = get_db()
        shared = conn.execute('''SELECT tm1.team_id FROM team_members tm1
            JOIN team_members tm2 ON tm1.team_id = tm2.team_id
            WHERE tm1.user_id = ? AND tm2.user_id = ?''', (uid, target_uid)).fetchone()
        conn.close()
        if not shared:
            return jsonify({'success': False, 'error': 'Not on same team.'}), 403

    title = (d.get('title') or '').strip()
    if not title or not d.get('event_date'):
        return jsonify({'success': False, 'error': 'Title and date required.'})

    # Trainers cannot edit athlete's own events
    editable = 1 if role == 'athlete' else 0

    color_map = {
        'athlete': '#C0392B',
        'coach': '#1A6B3C',
        'trainer': '#1A4B8C',
        'ai': '#8B5CF6',
    }

    conn = get_db()
    conn.execute('''INSERT INTO calendar_events
        (user_id, created_by, creator_role, title, description, event_date, event_type, color, is_ai_generated, is_editable_by_athlete)
        VALUES (?,?,?,?,?,?,?,?,?,?)''',
        (target_uid, uid, role, title, d.get('description') or '',
         d.get('event_date'), d.get('event_type') or 'general',
         color_map.get(role, '#C0392B'), 0, editable))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/calendar/<int:eid>', methods=['PUT'])
@require_auth
def update_calendar_event(eid):
    d = request.json or {}
    uid = session['user_id']
    role = session['role']
    conn = get_db()
    event = conn.execute('SELECT * FROM calendar_events WHERE id = ?', (eid,)).fetchone()
    if not event:
        conn.close()
        return jsonify({'success': False, 'error': 'Event not found.'})

    # Access rules
    can_edit = (
        event['created_by'] == uid or
        role in ('coach',) or
        (role == 'athlete' and event['user_id'] == uid and event['is_editable_by_athlete'])
    )
    if not can_edit:
        conn.close()
        return jsonify({'success': False, 'error': 'Cannot edit this event.'})

    conn.execute('''UPDATE calendar_events SET title=?, description=?, event_date=?, event_type=?
        WHERE id = ?''',
        (d.get('title') or event['title'], d.get('description') or event['description'],
         d.get('event_date') or event['event_date'], d.get('event_type') or event['event_type'],
         eid))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/calendar/<int:eid>', methods=['DELETE'])
@require_auth
def delete_calendar_event(eid):
    uid = session['user_id']
    role = session['role']
    conn = get_db()
    event = conn.execute('SELECT * FROM calendar_events WHERE id = ?', (eid,)).fetchone()
    if not event:
        conn.close()
        return jsonify({'success': False, 'error': 'Not found.'})

    can_delete = (event['created_by'] == uid or role == 'coach' or
                  (role == 'athlete' and event['user_id'] == uid and event['is_editable_by_athlete']))
    if not can_delete:
        conn.close()
        return jsonify({'success': False, 'error': 'Cannot delete this event.'})

    conn.execute('DELETE FROM calendar_events WHERE id = ?', (eid,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# Coach: get all athletes on their team with calendar view
@app.route('/api/teams/<int:team_id>/calendar', methods=['GET'])
@require_role('coach', 'trainer')
def team_calendar(team_id):
    conn = get_db()
    me_member = conn.execute('SELECT * FROM team_members WHERE team_id = ? AND user_id = ?',
                             (team_id, session['user_id'])).fetchone()
    if not me_member:
        conn.close()
        return jsonify({'error': 'Access denied'}), 403

    month = request.args.get('month')
    athletes = conn.execute('''SELECT u.id, u.username FROM users u
        JOIN team_members tm ON tm.user_id = u.id
        WHERE tm.team_id = ? AND u.role = "athlete"''', (team_id,)).fetchall()

    result = []
    for a in athletes:
        if month:
            events = conn.execute('''SELECT * FROM calendar_events WHERE user_id = ? AND event_date LIKE ?
                ORDER BY event_date ASC''', (a['id'], month + '%')).fetchall()
        else:
            events = conn.execute('SELECT * FROM calendar_events WHERE user_id = ? ORDER BY event_date ASC',
                                  (a['id'],)).fetchall()
        result.append({
            'athlete_id': a['id'],
            'athlete_name': a['username'],
            'events': [dict(e) for e in events]
        })
    conn.close()
    return jsonify({'success': True, 'athletes': result})


# ══════════════════════════
#  AI CHAT
# ══════════════════════════

def get_or_create_session(user_id):
    conn = get_db()
    row = conn.execute('SELECT * FROM chat_sessions WHERE user_id = ? ORDER BY created_at DESC LIMIT 1',
                       (user_id,)).fetchone()
    if not row:
        cur = conn.execute('INSERT INTO chat_sessions (user_id, session_name) VALUES (?,?)',
                           (user_id, 'Luna Chat'))
        sid = cur.lastrowid
        conn.commit()
        conn.close()
        return {'id': sid, 'session_name': 'Luna Chat'}
    conn.close()
    return dict(row)


@app.route('/api/chat/history')
@require_auth
def chat_history():
    sess = get_or_create_session(session['user_id'])
    conn = get_db()
    messages = conn.execute('SELECT role, content, created_at FROM chat_messages WHERE session_id = ? ORDER BY created_at ASC',
                            (sess['id'],)).fetchall()
    conn.close()
    return jsonify({'success': True, 'messages': [dict(m) for m in messages], 'sessionId': sess['id']})


@app.route('/api/chat/sessions')
@require_auth
def chat_sessions():
    conn = get_db()
    rows = conn.execute('SELECT id, session_name, created_at FROM chat_sessions WHERE user_id = ? ORDER BY created_at DESC',
                        (session['user_id'],)).fetchall()
    conn.close()
    return jsonify({'success': True, 'sessions': [dict(r) for r in rows]})


@app.route('/api/chat/new-session', methods=['POST'])
@require_auth
def new_session():
    name = (request.json or {}).get('name') or ('Chat - ' + datetime.now().strftime('%m/%d/%Y'))
    conn = get_db()
    cur = conn.execute('INSERT INTO chat_sessions (user_id, session_name) VALUES (?,?)',
                       (session['user_id'], name))
    sid = cur.lastrowid
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'sessionId': sid})


@app.route('/api/chat/session/<int:sid>')
@require_auth
def get_session(sid):
    conn = get_db()
    s = conn.execute('SELECT * FROM chat_sessions WHERE id = ? AND user_id = ?',
                     (sid, session['user_id'])).fetchone()
    if not s:
        conn.close()
        return jsonify({'success': False, 'error': 'Not found'})
    msgs = conn.execute('SELECT role, content, created_at FROM chat_messages WHERE session_id = ? ORDER BY created_at ASC',
                        (sid,)).fetchall()
    conn.close()
    return jsonify({'success': True, 'messages': [dict(m) for m in msgs], 'session': dict(s)})


@app.route('/api/chat/session/<int:sid>', methods=['DELETE'])
@require_auth
def delete_session(sid):
    conn = get_db()
    s = conn.execute('SELECT id FROM chat_sessions WHERE id = ? AND user_id = ?',
                     (sid, session['user_id'])).fetchone()
    if not s:
        conn.close()
        return jsonify({'success': False, 'error': 'Not found'})
    conn.execute('DELETE FROM chat_messages WHERE session_id = ?', (sid,))
    conn.execute('DELETE FROM chat_sessions WHERE id = ?', (sid,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/chat/send', methods=['POST'])
@require_auth
def chat_send():
    d = request.json or {}
    message = (d.get('message') or '').strip()
    sid = d.get('sessionId')
    uid = session['user_id']

    if not message:
        return jsonify({'success': False, 'error': 'Message cannot be empty.'})

    conn = get_db()
    if sid:
        sess = conn.execute('SELECT * FROM chat_sessions WHERE id = ? AND user_id = ?', (sid, uid)).fetchone()
    else:
        sess = conn.execute('SELECT * FROM chat_sessions WHERE user_id = ? ORDER BY created_at DESC LIMIT 1', (uid,)).fetchone()

    if not sess:
        cur = conn.execute('INSERT INTO chat_sessions (user_id, session_name) VALUES (?,?)', (uid, 'Luna Chat'))
        sid = cur.lastrowid
        conn.commit()
        sess = conn.execute('SELECT * FROM chat_sessions WHERE id = ?', (sid,)).fetchone()

    sess = dict(sess)
    conn.execute('INSERT INTO chat_messages (session_id, user_id, role, content) VALUES (?,?,?,?)',
                 (sess['id'], uid, 'user', message))
    conn.commit()

    history = [dict(r) for r in conn.execute('SELECT role, content FROM chat_messages WHERE session_id = ? ORDER BY created_at ASC', (sess['id'],)).fetchall()]
    conn.close()

    luna = LunaAI(uid)
    reply = luna.respond(message, history)

    conn = get_db()
    conn.execute('INSERT INTO chat_messages (session_id, user_id, role, content) VALUES (?,?,?,?)',
                 (sess['id'], uid, 'assistant', reply))
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'reply': reply, 'sessionId': sess['id']})


# ══════════════════════════
#  PREDICTIONS
# ══════════════════════════

@app.route('/api/predict', methods=['POST'])
@require_auth
def predict():
    uid = session['user_id']
    result, error, source = get_prediction(uid)
    if result:
        return jsonify({'success': True, 'prediction': result, 'source': source})
    return jsonify({'success': False, 'error': error or 'Prediction failed.'})


@app.route('/api/predictions', methods=['GET'])
@require_auth
def get_predictions():
    conn = get_db()
    rows = conn.execute('SELECT * FROM ai_predictions WHERE user_id = ? ORDER BY created_at DESC LIMIT 5',
                        (session['user_id'],)).fetchall()
    conn.close()
    results = []
    for r in rows:
        item = dict(r)
        try:
            item['prediction_data'] = json.loads(item['prediction_data'])
        except Exception:
            pass
        results.append(item)
    return jsonify({'success': True, 'predictions': results})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    print('Red Moon Recovery starting on port ' + str(port))
    app.run(host='0.0.0.0', port=port, debug=False)
