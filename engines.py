"""
engines.py
Python bridge that calls the Java CycleEngine and C++ PatternAnalyzer
via subprocess. Falls back gracefully if the binaries are not compiled yet.
"""
import os
import json
import subprocess
import sqlite3
from database import get_db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JAVA_DIR = os.path.join(BASE_DIR, 'java')
CPP_DIR  = os.path.join(BASE_DIR, 'cpp')
CPP_BIN  = os.path.join(CPP_DIR, 'pattern_analyzer')


# ── C++ Pattern Analyzer ──

def run_cpp_analyzer(user_id):
    """
    Pass journal entries as JSON to the C++ pattern analyzer.
    Returns dict with patterns, warnings, recommendations, averages.
    """
    if not os.path.isfile(CPP_BIN):
        return None, "C++ analyzer not compiled yet. Run: cd cpp && g++ -o pattern_analyzer pattern_analyzer.cpp -std=c++17"

    conn = get_db()
    entries = conn.execute(
        'SELECT * FROM journal_entries WHERE user_id = ? ORDER BY entry_date DESC LIMIT 14',
        (user_id,)
    ).fetchall()
    conn.close()

    entries_list = [dict(e) for e in entries]
    payload = json.dumps({"entries": entries_list})

    try:
        result = subprocess.run(
            [CPP_BIN],
            input=payload,
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            return None, "C++ analyzer error: " + result.stderr
        data = json.loads(result.stdout)
        return data, None
    except subprocess.TimeoutExpired:
        return None, "C++ analyzer timed out"
    except json.JSONDecodeError as e:
        return None, "C++ output parse error: " + str(e)
    except Exception as e:
        return None, "C++ engine error: " + str(e)


# ── Java Cycle Engine ──

def run_java_engine(user_id):
    """
    Pass profile data as arguments to the Java CycleEngine.
    Returns dict with period prediction, phase info, event prediction.
    """
    java_class = os.path.join(JAVA_DIR, 'CycleEngine.class')
    if not os.path.isfile(java_class):
        return None, "Java engine not compiled yet. Run: cd java && javac CycleEngine.java"

    conn = get_db()
    profile = conn.execute('SELECT * FROM profiles WHERE user_id = ?', (user_id,)).fetchone()
    entries = conn.execute(
        'SELECT stress_level, sleep_quality, environmental_notes, training_load FROM journal_entries WHERE user_id = ? ORDER BY entry_date DESC LIMIT 7',
        (user_id,)
    ).fetchall()
    conn.close()

    if not profile or not profile['last_period_start']:
        return None, "No last period start date in profile."

    profile = dict(profile)
    entries = [dict(e) for e in entries]

    # Calculate averages for Java engine args
    stress_vals = [e['stress_level'] for e in entries if e.get('stress_level')]
    sleep_vals  = [e['sleep_quality'] for e in entries if e.get('sleep_quality')]
    avg_stress  = sum(stress_vals) / len(stress_vals) if stress_vals else 3.0
    avg_sleep   = sum(sleep_vals)  / len(sleep_vals)  if sleep_vals  else 7.0

    has_env = any(
        str(e.get('environmental_notes') or '').strip()
        for e in entries
    )
    loads = [str(e.get('training_load') or '') for e in entries]
    high_load = any('heavy' in l.lower() for l in loads) or avg_stress > 8

    cycle_len = int(profile.get('avg_cycle_length') or 28)
    last_period = str(profile['last_period_start'])
    event_date = str(profile.get('event_date') or '')

    args = [
        'java', '-cp', JAVA_DIR, 'CycleEngine',
        last_period,
        str(cycle_len),
        str(round(avg_stress, 2)),
        str(round(avg_sleep, 2)),
        str(has_env).lower(),
        str(high_load).lower(),
    ]
    if event_date and event_date != 'None':
        args.append(event_date)

    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=15
        )
        if result.returncode != 0:
            return None, "Java engine error: " + result.stderr
        # Strip JAVA_TOOL_OPTIONS lines which go to stderr
        stdout = result.stdout.strip()
        data = json.loads(stdout)
        return data, None
    except subprocess.TimeoutExpired:
        return None, "Java engine timed out"
    except json.JSONDecodeError as e:
        return None, "Java output parse error: " + str(e) + " | output: " + result.stdout[:200]
    except Exception as e:
        return None, "Java engine error: " + str(e)


# ── Combined prediction pipeline ──

def get_full_analysis(user_id):
    """
    Runs both engines, merges results, saves calendar events.
    Returns (java_result, cpp_result, errors).
    """
    java_result, java_err = run_java_engine(user_id)
    cpp_result,  cpp_err  = run_cpp_analyzer(user_id)

    errors = []
    if java_err:
        errors.append("Java engine: " + java_err)
    if cpp_err:
        errors.append("C++ engine: " + cpp_err)

    # Save calendar suggestions from Java if available
    if java_result:
        _save_prediction_calendar(user_id, java_result, cpp_result)

    return java_result, cpp_result, errors


def _save_prediction_calendar(user_id, java_result, cpp_result):
    """Save auto-generated calendar events from predictions."""
    conn = get_db()
    events_to_add = []

    if java_result.get('next_period_predicted'):
        events_to_add.append({
            'title': 'Period predicted to start',
            'date': java_result['next_period_predicted'],
            'type': 'prediction',
            'desc': 'Predicted by Java CycleEngine based on your cycle data.'
        })

    if java_result.get('ovulation_estimated'):
        events_to_add.append({
            'title': 'Estimated ovulation window',
            'date': java_result['ovulation_estimated'],
            'type': 'prediction',
            'desc': 'Peak performance window. Best time for high-intensity training.'
        })

    if cpp_result and cpp_result.get('has_injury'):
        from datetime import datetime, timedelta
        check_date = (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')
        events_to_add.append({
            'title': 'Injury check-in reminder',
            'date': check_date,
            'type': 'warning',
            'desc': 'Active injury detected by pattern analyzer. Monitor closely.'
        })

    for ev in events_to_add:
        try:
            if ev.get('date') and ev['date'] != 'None':
                conn.execute(
                    'INSERT INTO calendar_events (user_id, created_by, creator_role, title, description, event_date, event_type, is_ai_generated, color) VALUES (?,?,?,?,?,?,?,?,?)',
                    (user_id, user_id, 'ai', ev['title'], ev['desc'], ev['date'], ev['type'], 1, '#8B5CF6')
                )
        except Exception:
            pass

    conn.commit()
    conn.close()
