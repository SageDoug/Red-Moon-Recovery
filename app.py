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
from engines import get_full_analysis, run_java_engine, run_cpp_analyzer
from auto_journal import (
    run_auto_journal, has_enough_data, get_data_count,
    log_deviation, confirm_predicted_entry, get_deviation_history
)
from cognitive_model import (
    get_cognitive_prediction, update_cognitive_baselines,
    get_performance_impact_summary, PHASE_COGNITIVE_PROFILES,
    COGNITIVE_FIELDS, COGNITIVE_LABELS, COGNITIVE_DESCRIPTIONS,
    get_cognitive_phase
)

app = Flask(__name__, static_folder='static')
app.secret_key = os.environ.get('SECRET_KEY', 'redmoon-2024-secret')

init_db()
print("Red Moon Recovery server starting...")


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


@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


# ── AUTH ──

@app.route('/api/register', methods=['POST'])
def register():
    d = request.json or {}
    username = str(d.get('username') or '').strip().lower()
    email    = str(d.get('email')    or '').strip().lower()
    password = str(d.get('password') or '')
    role     = str(d.get('role')     or 'athlete')
    if role not in ('athlete', 'coach', 'trainer'):
        role = 'athlete'
    if not username or not email or not password:
        return jsonify({'success': False, 'error': 'All fields are required.'})
    if len(password) < 6:
        return jsonify({'success': False, 'error': 'Password must be at least 6 characters.'})
    try:
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        conn = get_db()
        cur = conn.execute(
            'INSERT INTO users (username, email, password_hash, role) VALUES (?,?,?,?)',
            (username, email, pw_hash, role)
        )
        uid = cur.lastrowid
        conn.commit()
        conn.close()
        session['user_id'] = uid
        session['username'] = username
        session['role'] = role
        return jsonify({'success': True, 'username': username, 'role': role})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'error': 'Username or email already taken.'})
    except Exception as e:
        return jsonify({'success': False, 'error': 'Registration failed: ' + str(e)})


@app.route('/api/login', methods=['POST'])
def login():
    d = request.json or {}
    username = str(d.get('username') or '').strip().lower()
    password = str(d.get('password') or '')
    if not username or not password:
        return jsonify({'success': False, 'error': 'Username and password required.'})
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
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


# ── TEAMS ──

@app.route('/api/teams', methods=['GET'])
@require_auth
def get_teams():
    uid = session['user_id']
    conn = get_db()
    if session['role'] == 'coach':
        rows = conn.execute('SELECT * FROM teams WHERE coach_id=?', (uid,)).fetchall()
    else:
        rows = conn.execute(
            'SELECT t.* FROM teams t JOIN team_members tm ON tm.team_id=t.id WHERE tm.user_id=?', (uid,)
        ).fetchall()
    result = []
    for r in rows:
        t = dict(r)
        members = conn.execute(
            'SELECT u.id, u.username, u.role FROM users u JOIN team_members tm ON tm.user_id=u.id WHERE tm.team_id=?',
            (r['id'],)
        ).fetchall()
        t['members'] = [dict(m) for m in members]
        coach = conn.execute('SELECT username FROM users WHERE id=?', (r['coach_id'],)).fetchone()
        t['coach_name'] = coach['username'] if coach else ''
        result.append(t)
    conn.close()
    return jsonify({'success': True, 'teams': result})


@app.route('/api/teams', methods=['POST'])
@require_role('coach')
def create_team():
    d = request.json or {}
    name = str(d.get('name') or '').strip()
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
    code = str(d.get('invite_code') or '').strip().upper()
    if not code:
        return jsonify({'success': False, 'error': 'Invite code required.'})
    conn = get_db()
    team = conn.execute('SELECT * FROM teams WHERE invite_code=?', (code,)).fetchone()
    if not team:
        conn.close()
        return jsonify({'success': False, 'error': 'Invalid invite code.'})
    existing = conn.execute('SELECT id FROM team_members WHERE team_id=? AND user_id=?',
                            (team['id'], session['user_id'])).fetchone()
    if existing:
        conn.close()
        return jsonify({'success': False, 'error': 'Already on this team.'})
    conn.execute('INSERT INTO team_members (team_id, user_id, role) VALUES (?,?,?)',
                 (team['id'], session['user_id'], session['role']))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'team_name': team['name']})


@app.route('/api/teams/<int:team_id>/athlete/<int:athlete_id>/data', methods=['GET'])
@require_role('coach', 'trainer')
def athlete_data(team_id, athlete_id):
    conn = get_db()
    me_m = conn.execute('SELECT * FROM team_members WHERE team_id=? AND user_id=?',
                        (team_id, session['user_id'])).fetchone()
    at_m = conn.execute('SELECT * FROM team_members WHERE team_id=? AND user_id=?',
                        (team_id, athlete_id)).fetchone()
    if not me_m or not at_m:
        conn.close()
        return jsonify({'error': 'Access denied'}), 403
    entries = conn.execute(
        'SELECT * FROM journal_entries WHERE user_id=? ORDER BY entry_date DESC LIMIT 30',
        (athlete_id,)
    ).fetchall()
    profile = conn.execute('SELECT * FROM profiles WHERE user_id=?', (athlete_id,)).fetchone()
    user = conn.execute('SELECT username, role FROM users WHERE id=?', (athlete_id,)).fetchone()
    conn.close()
    return jsonify({
        'success': True,
        'athlete': dict(user) if user else {},
        'profile': dict(profile) if profile else {},
        'entries': [dict(e) for e in entries]
    })


# ── PROFILE ──

@app.route('/api/profile', methods=['GET'])
@require_auth
def get_profile():
    conn = get_db()
    row = conn.execute('SELECT * FROM profiles WHERE user_id=?', (session['user_id'],)).fetchone()
    conn.close()
    return jsonify({'success': True, 'profile': dict(row) if row else None})


@app.route('/api/profile', methods=['POST'])
@require_auth
def save_profile():
    b = request.json or {}
    uid = session['user_id']
    goals_json = json.dumps(b.get('goals') or [])
    conn = get_db()
    existing = conn.execute('SELECT id FROM profiles WHERE user_id=?', (uid,)).fetchone()
    if existing:
        conn.execute(
            '''UPDATE profiles SET name=?,age=?,cycle_status=?,goals=?,sport=?,event_date=?,
               desired_phase=?,cycles_data=?,training_load=?,acl_history=?,avg_cycle_length=?,
               last_period_start=?,auto_journal_enabled=?,updated_at=CURRENT_TIMESTAMP WHERE user_id=?''',
            (b.get('name'), b.get('age'), b.get('cycle_status'), goals_json, b.get('sport'),
             b.get('event_date'), b.get('desired_phase'), b.get('cycles_data'), b.get('training_load'),
             b.get('acl_history'), b.get('avg_cycle_length') or 28, b.get('last_period_start'),
             1 if b.get('auto_journal_enabled') else 0, uid)
        )
    else:
        conn.execute(
            '''INSERT INTO profiles (user_id,name,age,cycle_status,goals,sport,event_date,
               desired_phase,cycles_data,training_load,acl_history,avg_cycle_length,last_period_start,auto_journal_enabled)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (uid, b.get('name'), b.get('age'), b.get('cycle_status'), goals_json, b.get('sport'),
             b.get('event_date'), b.get('desired_phase'), b.get('cycles_data'), b.get('training_load'),
             b.get('acl_history'), b.get('avg_cycle_length') or 28, b.get('last_period_start'),
             1 if b.get('auto_journal_enabled') else 0)
        )
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ── JOURNAL ──

@app.route('/api/journal', methods=['POST'])
@require_auth
def save_journal():
    e = request.json or {}
    uid = session['user_id']
    conn = get_db()

    # If updating a predicted entry, log deviations
    existing = conn.execute(
        'SELECT * FROM journal_entries WHERE user_id=? AND entry_date=?',
        (uid, e.get('entry_date'))
    ).fetchone()

    if existing and existing['is_predicted']:
        existing = dict(existing)
        for field in ['energy', 'sleep_quality', 'mood', 'flow', 'rpe', 'motivation', 'stress_level']:
            pred_val = existing.get(field)
            actual_val = e.get(field)
            if actual_val is not None and str(actual_val) != str(pred_val):
                log_deviation(uid, e.get('entry_date'), field, pred_val, actual_val)
        # Update the predicted entry with real values
        conn.execute(
            '''UPDATE journal_entries SET
               is_predicted=0, is_confirmed=1,
               cycle_day=?, phase=?, hrv=?, sleep_quality=?, sleep_hours=?,
               energy=?, soreness=?, pain_notes=?, workout=?, rpe=?, motivation=?,
               perf_notes=?, flow=?, cramps=?, mucus=?, digestion=?, symptom_time=?,
               mood=?, cognitive=?, social=?, cravings=?, hydration=?, recovery_steps=?,
               environmental_temp=?, environmental_humidity=?, environmental_notes=?,
               injuries=?, stress_level=?,
               verbal_fluency=?, spatial_reasoning=?, working_memory=?,
               emotional_reactivity=?, risk_tolerance=?, creative_thinking=?,
               analytical_focus=?, social_confidence=?, competitive_drive=?,
               self_criticism=?, cognitive_notes=?, performance_impact=?
               WHERE user_id=? AND entry_date=?''',
            (e.get('cycle_day'), e.get('phase'), e.get('hrv'),
             e.get('sleep_quality'), e.get('sleep_hours'), e.get('energy'), e.get('soreness'),
             e.get('pain_notes'), e.get('workout'), e.get('rpe'), e.get('motivation'),
             e.get('perf_notes'), e.get('flow'), e.get('cramps'), e.get('mucus'),
             e.get('digestion'), e.get('symptom_time'), e.get('mood'), e.get('cognitive'),
             e.get('social'), e.get('cravings'), e.get('hydration'),
             json.dumps(e.get('recovery_steps') or []),
             e.get('environmental_temp'), e.get('environmental_humidity'),
             e.get('environmental_notes'), e.get('injuries'), e.get('stress_level'),
             e.get('verbal_fluency'), e.get('spatial_reasoning'), e.get('working_memory'),
             e.get('emotional_reactivity'), e.get('risk_tolerance'), e.get('creative_thinking'),
             e.get('analytical_focus'), e.get('social_confidence'), e.get('competitive_drive'),
             e.get('self_criticism'), e.get('cognitive_notes'), e.get('performance_impact'),
             uid, e.get('entry_date'))
        )
    else:
        conn.execute(
            '''INSERT INTO journal_entries
               (user_id,entry_date,cycle_day,phase,hrv,sleep_quality,sleep_hours,energy,soreness,
                pain_notes,workout,rpe,motivation,perf_notes,flow,cramps,mucus,digestion,symptom_time,
                mood,cognitive,social,cravings,hydration,recovery_steps,environmental_temp,
                environmental_humidity,environmental_notes,injuries,stress_level,
                verbal_fluency,spatial_reasoning,working_memory,emotional_reactivity,risk_tolerance,
                creative_thinking,analytical_focus,social_confidence,competitive_drive,
                self_criticism,cognitive_notes,performance_impact)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (uid, e.get('entry_date'), e.get('cycle_day'), e.get('phase'), e.get('hrv'),
             e.get('sleep_quality'), e.get('sleep_hours'), e.get('energy'), e.get('soreness'),
             e.get('pain_notes'), e.get('workout'), e.get('rpe'), e.get('motivation'), e.get('perf_notes'),
             e.get('flow'), e.get('cramps'), e.get('mucus'), e.get('digestion'), e.get('symptom_time'),
             e.get('mood'), e.get('cognitive'), e.get('social'), e.get('cravings'), e.get('hydration'),
             json.dumps(e.get('recovery_steps') or []),
             e.get('environmental_temp'), e.get('environmental_humidity'), e.get('environmental_notes'),
             e.get('injuries'), e.get('stress_level'),
             e.get('verbal_fluency'), e.get('spatial_reasoning'), e.get('working_memory'),
             e.get('emotional_reactivity'), e.get('risk_tolerance'), e.get('creative_thinking'),
             e.get('analytical_focus'), e.get('social_confidence'), e.get('competitive_drive'),
             e.get('self_criticism'), e.get('cognitive_notes'), e.get('performance_impact'))
        )

    conn.commit()
    conn.close()

    # Update cognitive baselines after saving real data
    try:
        update_cognitive_baselines(uid)
    except Exception:
        pass

    # Run auto-journal to refresh future predictions
    try:
        conn2 = get_db()
        prof = conn2.execute('SELECT auto_journal_enabled FROM profiles WHERE user_id=?', (uid,)).fetchone()
        conn2.close()
        if prof and prof['auto_journal_enabled']:
            run_auto_journal(uid)
    except Exception:
        pass

    return jsonify({'success': True})


@app.route('/api/journal', methods=['GET'])
@require_auth
def get_journal():
    include_predicted = request.args.get('include_predicted', 'true') == 'true'
    conn = get_db()
    if include_predicted:
        rows = conn.execute(
            'SELECT * FROM journal_entries WHERE user_id=? ORDER BY entry_date DESC',
            (session['user_id'],)
        ).fetchall()
    else:
        rows = conn.execute(
            'SELECT * FROM journal_entries WHERE user_id=? AND is_predicted=0 ORDER BY entry_date DESC',
            (session['user_id'],)
        ).fetchall()
    conn.close()
    return jsonify({'success': True, 'entries': [dict(r) for r in rows]})


@app.route('/api/journal/today', methods=['GET'])
@require_auth
def get_today_entry():
    today = datetime.now().strftime('%Y-%m-%d')
    conn = get_db()
    row = conn.execute(
        'SELECT * FROM journal_entries WHERE user_id=? AND entry_date=?',
        (session['user_id'], today)
    ).fetchone()
    conn.close()
    return jsonify({'success': True, 'entry': dict(row) if row else None, 'date': today})


@app.route('/api/journal/<int:eid>', methods=['DELETE'])
@require_auth
def delete_journal(eid):
    conn = get_db()
    conn.execute('DELETE FROM journal_entries WHERE id=? AND user_id=?', (eid, session['user_id']))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/journal/confirm/<entry_date>', methods=['POST'])
@require_auth
def confirm_journal(entry_date):
    confirm_predicted_entry(session['user_id'], entry_date)
    return jsonify({'success': True})


# ── AUTO-JOURNAL ──

@app.route('/api/auto-journal/status', methods=['GET'])
@require_auth
def auto_journal_status():
    uid = session['user_id']
    count = get_data_count(uid)
    ready = has_enough_data(uid)
    conn = get_db()
    prof = conn.execute('SELECT auto_journal_enabled FROM profiles WHERE user_id=?', (uid,)).fetchone()
    conn.close()
    enabled = prof and prof['auto_journal_enabled']
    return jsonify({
        'success': True,
        'entries_logged': count,
        'entries_needed': max(0, 28 - count),
        'ready': ready,
        'enabled': bool(enabled),
        'progress_pct': min(100, int((count / 28) * 100))
    })


@app.route('/api/auto-journal/run', methods=['POST'])
@require_auth
def run_auto():
    result = run_auto_journal(session['user_id'])
    return jsonify({'success': True, 'result': result})


@app.route('/api/auto-journal/deviations', methods=['GET'])
@require_auth
def get_deviations():
    devs = get_deviation_history(session['user_id'])
    return jsonify({'success': True, 'deviations': devs})


# ── COGNITIVE ──

@app.route('/api/cognitive/profiles', methods=['GET'])
@require_auth
def cognitive_profiles():
    return jsonify({
        'success': True,
        'profiles': PHASE_COGNITIVE_PROFILES,
        'fields': COGNITIVE_FIELDS,
        'labels': COGNITIVE_LABELS,
        'descriptions': COGNITIVE_DESCRIPTIONS
    })


@app.route('/api/cognitive/prediction', methods=['GET'])
@require_auth
def cognitive_prediction():
    uid = session['user_id']
    cycle_day = request.args.get('cycle_day', type=int)
    if not cycle_day:
        conn = get_db()
        latest = conn.execute(
            'SELECT cycle_day FROM journal_entries WHERE user_id=? AND is_predicted=0 AND cycle_day IS NOT NULL ORDER BY entry_date DESC LIMIT 1',
            (uid,)
        ).fetchone()
        profile = conn.execute('SELECT last_period_start, avg_cycle_length FROM profiles WHERE user_id=?', (uid,)).fetchone()
        conn.close()
        if latest:
            cycle_day = latest['cycle_day']
        elif profile and profile['last_period_start']:
            from datetime import datetime
            try:
                last = datetime.strptime(str(profile['last_period_start']), '%Y-%m-%d')
                cycle_len = int(profile['avg_cycle_length'] or 28)
                cycle_day = ((datetime.now() - last).days % cycle_len) + 1
            except Exception:
                cycle_day = 14
        else:
            cycle_day = 14

    vals = get_cognitive_prediction(uid, cycle_day)
    phase = get_cognitive_phase(cycle_day)
    profile_info = PHASE_COGNITIVE_PROFILES.get(phase, {})
    impact = get_performance_impact_summary(vals)

    return jsonify({
        'success': True,
        'cycle_day': cycle_day,
        'phase': phase,
        'cognitive_values': vals,
        'performance_impact': impact,
        'phase_profile': {
            'label': profile_info.get('label'),
            'primary_hormones': profile_info.get('primary_hormones'),
            'performance_summary': profile_info.get('performance_summary'),
            'athletic_cognitive_impact': profile_info.get('athletic_cognitive_impact'),
            'coaching_note': profile_info.get('coaching_note'),
        }
    })


@app.route('/api/cognitive/baselines', methods=['GET'])
@require_auth
def get_baselines():
    uid = session['user_id']
    conn = get_db()
    rows = conn.execute('SELECT * FROM cognitive_baselines WHERE user_id=?', (uid,)).fetchall()
    conn.close()
    return jsonify({'success': True, 'baselines': [dict(r) for r in rows]})


@app.route('/api/cognitive/update-baselines', methods=['POST'])
@require_auth
def update_baselines():
    try:
        update_cognitive_baselines(session['user_id'])
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ── CALENDAR ──

@app.route('/api/calendar', methods=['GET'])
@require_auth
def get_calendar():
    uid = session['user_id']
    month = request.args.get('month')
    conn = get_db()
    if month:
        rows = conn.execute(
            'SELECT ce.*, u.username as creator_name FROM calendar_events ce JOIN users u ON u.id=ce.created_by WHERE ce.user_id=? AND ce.event_date LIKE ? ORDER BY ce.event_date ASC',
            (uid, month + '%')
        ).fetchall()
    else:
        rows = conn.execute(
            'SELECT ce.*, u.username as creator_name FROM calendar_events ce JOIN users u ON u.id=ce.created_by WHERE ce.user_id=? ORDER BY ce.event_date ASC',
            (uid,)
        ).fetchall()
    conn.close()
    return jsonify({'success': True, 'events': [dict(r) for r in rows]})


@app.route('/api/calendar', methods=['POST'])
@require_auth
def add_calendar_event():
    d = request.json or {}
    uid = session['user_id']
    role = session['role']
    target_uid = d.get('target_user_id') or uid
    if int(target_uid) != uid:
        conn = get_db()
        shared = conn.execute(
            'SELECT tm1.team_id FROM team_members tm1 JOIN team_members tm2 ON tm1.team_id=tm2.team_id WHERE tm1.user_id=? AND tm2.user_id=?',
            (uid, target_uid)
        ).fetchone()
        conn.close()
        if not shared:
            return jsonify({'success': False, 'error': 'Not on same team.'}), 403
    title = str(d.get('title') or '').strip()
    if not title or not d.get('event_date'):
        return jsonify({'success': False, 'error': 'Title and date required.'})
    editable = 1 if role == 'athlete' else 0
    color_map = {'athlete': '#C0392B', 'coach': '#1A6B3C', 'trainer': '#1A4B8C', 'ai': '#8B5CF6'}
    conn = get_db()
    conn.execute(
        'INSERT INTO calendar_events (user_id,created_by,creator_role,title,description,event_date,event_type,color,is_ai_generated,is_editable_by_athlete) VALUES (?,?,?,?,?,?,?,?,?,?)',
        (target_uid, uid, role, title, d.get('description') or '', d.get('event_date'),
         d.get('event_type') or 'general', color_map.get(role, '#C0392B'), 0, editable)
    )
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
    event = conn.execute('SELECT * FROM calendar_events WHERE id=?', (eid,)).fetchone()
    if not event:
        conn.close()
        return jsonify({'success': False, 'error': 'Not found.'})
    can_edit = (event['created_by'] == uid or role == 'coach' or
                (role == 'athlete' and event['user_id'] == uid and event['is_editable_by_athlete']))
    if not can_edit:
        conn.close()
        return jsonify({'success': False, 'error': 'Cannot edit this event.'})
    conn.execute(
        'UPDATE calendar_events SET title=?,description=?,event_date=?,event_type=? WHERE id=?',
        (d.get('title') or event['title'], d.get('description') or event['description'],
         d.get('event_date') or event['event_date'], d.get('event_type') or event['event_type'], eid)
    )
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/calendar/<int:eid>', methods=['DELETE'])
@require_auth
def delete_calendar_event(eid):
    uid = session['user_id']
    role = session['role']
    conn = get_db()
    event = conn.execute('SELECT * FROM calendar_events WHERE id=?', (eid,)).fetchone()
    if not event:
        conn.close()
        return jsonify({'success': False, 'error': 'Not found.'})
    can_delete = (event['created_by'] == uid or role == 'coach' or
                  (role == 'athlete' and event['user_id'] == uid and event['is_editable_by_athlete']))
    if not can_delete:
        conn.close()
        return jsonify({'success': False, 'error': 'Cannot delete.'})
    conn.execute('DELETE FROM calendar_events WHERE id=?', (eid,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ── CHAT ──

def get_or_create_session(user_id):
    conn = get_db()
    row = conn.execute('SELECT * FROM chat_sessions WHERE user_id=? ORDER BY created_at DESC LIMIT 1', (user_id,)).fetchone()
    if not row:
        cur = conn.execute('INSERT INTO chat_sessions (user_id, session_name) VALUES (?,?)', (user_id, 'Luna Chat'))
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
    messages = conn.execute(
        'SELECT role, content, created_at FROM chat_messages WHERE session_id=? ORDER BY created_at ASC',
        (sess['id'],)
    ).fetchall()
    conn.close()
    return jsonify({'success': True, 'messages': [dict(m) for m in messages], 'sessionId': sess['id']})


@app.route('/api/chat/sessions')
@require_auth
def chat_sessions():
    conn = get_db()
    rows = conn.execute(
        'SELECT id, session_name, created_at FROM chat_sessions WHERE user_id=? ORDER BY created_at DESC',
        (session['user_id'],)
    ).fetchall()
    conn.close()
    return jsonify({'success': True, 'sessions': [dict(r) for r in rows]})


@app.route('/api/chat/new-session', methods=['POST'])
@require_auth
def new_session():
    name = str((request.json or {}).get('name') or ('Chat - ' + datetime.now().strftime('%m/%d/%Y')))
    conn = get_db()
    cur = conn.execute('INSERT INTO chat_sessions (user_id, session_name) VALUES (?,?)', (session['user_id'], name))
    sid = cur.lastrowid
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'sessionId': sid})


@app.route('/api/chat/session/<int:sid>')
@require_auth
def get_session(sid):
    conn = get_db()
    s = conn.execute('SELECT * FROM chat_sessions WHERE id=? AND user_id=?', (sid, session['user_id'])).fetchone()
    if not s:
        conn.close()
        return jsonify({'success': False, 'error': 'Not found'})
    msgs = conn.execute(
        'SELECT role, content, created_at FROM chat_messages WHERE session_id=? ORDER BY created_at ASC', (sid,)
    ).fetchall()
    conn.close()
    return jsonify({'success': True, 'messages': [dict(m) for m in msgs], 'session': dict(s)})


@app.route('/api/chat/session/<int:sid>', methods=['DELETE'])
@require_auth
def delete_session(sid):
    conn = get_db()
    s = conn.execute('SELECT id FROM chat_sessions WHERE id=? AND user_id=?', (sid, session['user_id'])).fetchone()
    if not s:
        conn.close()
        return jsonify({'success': False, 'error': 'Not found'})
    conn.execute('DELETE FROM chat_messages WHERE session_id=?', (sid,))
    conn.execute('DELETE FROM chat_sessions WHERE id=?', (sid,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/chat/send', methods=['POST'])
@require_auth
def chat_send():
    d = request.json or {}
    message = str(d.get('message') or '').strip()
    sid = d.get('sessionId')
    uid = session['user_id']
    if not message:
        return jsonify({'success': False, 'error': 'Message cannot be empty.'})
    conn = get_db()
    if sid:
        sess = conn.execute('SELECT * FROM chat_sessions WHERE id=? AND user_id=?', (sid, uid)).fetchone()
    else:
        sess = conn.execute('SELECT * FROM chat_sessions WHERE user_id=? ORDER BY created_at DESC LIMIT 1', (uid,)).fetchone()
    if not sess:
        cur = conn.execute('INSERT INTO chat_sessions (user_id, session_name) VALUES (?,?)', (uid, 'Luna Chat'))
        conn.commit()
        sess = conn.execute('SELECT * FROM chat_sessions WHERE id=?', (cur.lastrowid,)).fetchone()
    sess = dict(sess)
    conn.execute('INSERT INTO chat_messages (session_id, user_id, role, content) VALUES (?,?,?,?)',
                 (sess['id'], uid, 'user', message))
    conn.commit()
    history = [dict(r) for r in conn.execute(
        'SELECT role, content FROM chat_messages WHERE session_id=? ORDER BY created_at ASC', (sess['id'],)
    ).fetchall()]
    conn.close()
    try:
        luna = LunaAI(uid)
        reply = luna.respond(message, history)
    except Exception as e:
        reply = "I had trouble processing that. Please try again. (" + str(e) + ")"
    conn = get_db()
    conn.execute('INSERT INTO chat_messages (session_id, user_id, role, content) VALUES (?,?,?,?)',
                 (sess['id'], uid, 'assistant', reply))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'reply': reply, 'sessionId': sess['id']})


# ── PREDICTIONS ──

@app.route('/api/predict', methods=['POST'])
@require_auth
def predict():
    uid = session['user_id']
    try:
        java_result, cpp_result, errors = get_full_analysis(uid)
        return jsonify({'success': True, 'java_prediction': java_result, 'cpp_analysis': cpp_result,
                        'errors': errors, 'source': 'java+cpp'})
    except Exception as e:
        return jsonify({'success': False, 'error': 'Analysis error: ' + str(e)})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    print("Starting on port " + str(port))
    app.run(host='0.0.0.0', port=port, debug=False)
