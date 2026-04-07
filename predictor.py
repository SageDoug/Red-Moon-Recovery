import os
import json
import requests
from datetime import datetime, timedelta
from database import get_db


def build_prompt(user_id):
    conn = get_db()
    profile = conn.execute('SELECT * FROM profiles WHERE user_id = ?', (user_id,)).fetchone()
    entries = conn.execute('SELECT * FROM journal_entries WHERE user_id = ? ORDER BY entry_date DESC LIMIT 30', (user_id,)).fetchall()
    conn.close()

    profile = dict(profile) if profile else {}
    entries = [dict(e) for e in entries]

    goals = []
    try:
        goals = json.loads(profile.get('goals') or '[]')
    except Exception:
        pass

    profile_text = (
        "Name: " + str(profile.get('name') or 'Unknown') + "\n"
        "Age: " + str(profile.get('age') or 'Unknown') + "\n"
        "Cycle status: " + str(profile.get('cycle_status') or 'Unknown') + "\n"
        "Sport: " + str(profile.get('sport') or 'Unknown') + "\n"
        "Average cycle length: " + str(profile.get('avg_cycle_length') or 28) + " days\n"
        "Last period start: " + str(profile.get('last_period_start') or 'Not recorded') + "\n"
        "Training load: " + str(profile.get('training_load') or 'Unknown') + "\n"
        "ACL history: " + str(profile.get('acl_history') or 'Unknown') + "\n"
        "Goals: " + ", ".join(goals) + "\n"
        "Upcoming event: " + str(profile.get('event_date') or 'None') + "\n"
        "Desired phase for event: " + str(profile.get('desired_phase') or 'Not set') + "\n"
    )

    journal_text = ""
    if entries:
        for e in entries[:14]:
            journal_text += (
                "[" + str(e.get('entry_date') or '') + "] "
                "Day " + str(e.get('cycle_day') or '?') + ", " + str(e.get('phase') or '?') + " phase | "
                "Sleep: " + str(e.get('sleep_quality') or '?') + "/10 (" + str(e.get('sleep_hours') or '?') + "hrs) | "
                "Energy: " + str(e.get('energy') or '?') + " | "
                "RPE: " + str(e.get('rpe') or '?') + " | "
                "Motivation: " + str(e.get('motivation') or '?') + " | "
                "Flow: " + str(e.get('flow') or '?') + " | "
                "Cramps: " + str(e.get('cramps') or '?') + " | "
                "Mood: " + str(e.get('mood') or '?') + " | "
                "Stress: " + str(e.get('stress_level') or '?') + "/10 | "
                "Injuries: " + str(e.get('injuries') or 'none') + " | "
                "Env temp: " + str(e.get('environmental_temp') or '?') + " | "
                "Env humidity: " + str(e.get('environmental_humidity') or '?') + " | "
                "Env notes: " + str(e.get('environmental_notes') or 'none') + " | "
                "Workout: " + str(e.get('workout') or '?') + " | "
                "Notes: " + str(e.get('perf_notes') or 'none') + "\n"
            )
    else:
        journal_text = "No journal entries yet."

    today = datetime.now().strftime('%Y-%m-%d')

    prompt = (
        "You are a specialist in female athletic performance and menstrual cycle science. "
        "Analyze the following data and provide detailed evidence-based predictions.\n\n"
        "Today: " + today + "\n\n"
        "ATHLETE PROFILE:\n" + profile_text + "\n"
        "JOURNAL DATA (last 14 entries, newest first):\n" + journal_text + "\n"
        "YOUR TASK:\n"
        "Provide a prediction report as a JSON object with exactly these fields:\n\n"
        '{"next_period_predicted":"YYYY-MM-DD","next_period_confidence":"high|medium|low",'
        '"period_shift_factors":["factor1","factor2"],"ovulation_estimated":"YYYY-MM-DD",'
        '"current_phase":"menstrual|follicular|ovulatory|luteal|unknown","current_phase_day":1,'
        '"event_phase_prediction":"phase name or null","event_cycle_day_prediction":1,'
        '"event_recommendations":"specific advice or null","training_this_week":"specific recommendation",'
        '"injury_flags":["flag1"],"environmental_impact":"assessment",'
        '"pattern_alerts":["alert1"],"nutrition_focus":"recommendation",'
        '"calendar_suggestions":[{"title":"event title","date":"YYYY-MM-DD","type":"rest|training|nutrition|warning|prediction","description":"brief"}],'
        '"summary":"2-3 sentence overall summary"}\n\n'
        "Base predictions on: logged cycle data and phases, environmental factors and their known effects on timing, "
        "training load stress and sleep which can delay ovulation, any injuries noted, flow characteristics, "
        "and nutritional factors. Return ONLY the JSON object with no explanation and no markdown."
    )
    return prompt


def run_claude(user_id):
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        return None, "No ANTHROPIC_API_KEY set."

    prompt = build_prompt(user_id)

    try:
        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'Content-Type': 'application/json',
                'x-api-key': api_key,
                'anthropic-version': '2023-06-01'
            },
            json={
                'model': 'claude-haiku-4-5-20251001',
                'max_tokens': 2000,
                'messages': [{'role': 'user', 'content': prompt}]
            },
            timeout=30
        )

        if not response.ok:
            return None, "Claude API error: " + str(response.status_code)

        data = response.json()
        text = (data.get('content') or [{}])[0].get('text') or ''
        text = text.strip()
        if text.startswith('```'):
            lines = text.split('\n')
            text = '\n'.join(lines[1:])
        if text.endswith('```'):
            text = text.rsplit('```', 1)[0]
        text = text.strip()

        result = json.loads(text)

        conn = get_db()
        conn.execute(
            'INSERT INTO ai_predictions (user_id, prediction_type, prediction_data, predicted_date, confidence) VALUES (?,?,?,?,?)',
            (user_id, 'full_cycle', json.dumps(result), result.get('next_period_predicted'), result.get('next_period_confidence'))
        )
        if result.get('calendar_suggestions'):
            for s in result['calendar_suggestions']:
                try:
                    if s.get('date'):
                        conn.execute(
                            'INSERT INTO calendar_events (user_id, created_by, creator_role, title, description, event_date, event_type, is_ai_generated, color) VALUES (?,?,?,?,?,?,?,?,?)',
                            (user_id, user_id, 'ai', s.get('title', 'AI Suggestion'), s.get('description', ''), s['date'], s.get('type', 'prediction'), 1, '#8B5CF6')
                        )
                except Exception:
                    pass
        conn.commit()
        conn.close()
        return result, None

    except json.JSONDecodeError as e:
        return None, "Could not parse response: " + str(e)
    except requests.exceptions.Timeout:
        return None, "Request timed out."
    except Exception as e:
        return None, "Prediction error: " + str(e)


def run_builtin(user_id):
    conn = get_db()
    profile = conn.execute('SELECT * FROM profiles WHERE user_id = ?', (user_id,)).fetchone()
    entries = conn.execute('SELECT * FROM journal_entries WHERE user_id = ? ORDER BY entry_date DESC LIMIT 14', (user_id,)).fetchall()
    conn.close()

    profile = dict(profile) if profile else {}
    entries = [dict(e) for e in entries]

    if not profile.get('last_period_start'):
        return None, "No last period start date set in profile."

    try:
        last = datetime.strptime(str(profile['last_period_start']), '%Y-%m-%d')
        cycle_len = int(profile.get('avg_cycle_length') or 28)
        today = datetime.now()

        delay = 0
        shift_factors = []
        alerts = []
        injury_flags = []

        recent = entries[:7]
        if recent:
            stress_vals = [e['stress_level'] for e in recent if e.get('stress_level')]
            if stress_vals and sum(stress_vals) / len(stress_vals) >= 7:
                delay += 2
                shift_factors.append("High stress levels - possible 1 to 3 day delay")

            sleep_vals = [e['sleep_quality'] for e in recent if e.get('sleep_quality')]
            if sleep_vals and sum(sleep_vals) / len(sleep_vals) < 5:
                delay += 1
                shift_factors.append("Consistently poor sleep - possible minor delay")
                alerts.append("Chronically low sleep quality affecting recovery and may affect cycle timing")

            for e in recent:
                notes = str(e.get('environmental_notes') or '').strip()
                if notes:
                    shift_factors.append("Environmental factors logged: " + notes)
                    break

            for e in recent:
                injuries = str(e.get('injuries') or '').strip().lower()
                if injuries not in ('', 'none', 'no'):
                    injury_flags.append("Active injury: " + str(e['injuries']))

            rpe_vals = [int(e['rpe']) for e in recent if e.get('rpe')]
            mot_vals = [int(e['motivation']) for e in recent if e.get('motivation')]
            if rpe_vals and mot_vals and len(rpe_vals) == len(mot_vals):
                avg_rpe = sum(rpe_vals) / len(rpe_vals)
                avg_mot = sum(mot_vals) / len(mot_vals)
                if avg_rpe >= 7.5 and avg_mot <= 4:
                    alerts.append("High RPE with low motivation - possible overreaching, consider a recovery day")

        next_period = last + timedelta(days=cycle_len)
        adjusted_period = next_period + timedelta(days=delay)
        ovulation_est = last + timedelta(days=cycle_len - 14)
        days_until = (adjusted_period - today).days
        current_day = ((today - last).days % cycle_len) + 1

        if current_day <= 5:
            current_phase = 'menstrual'
        elif current_day <= 13:
            current_phase = 'follicular'
        elif current_day <= 17:
            current_phase = 'ovulatory'
        else:
            current_phase = 'luteal'

        event_phase = None
        event_day = None
        event_rec = None
        if profile.get('event_date'):
            try:
                event = datetime.strptime(str(profile['event_date']), '%Y-%m-%d')
                event_day = ((event - last).days % cycle_len) + 1
                if event_day <= 5:
                    event_phase = 'Menstrual'
                    event_rec = 'Plan for lower energy and higher perceived effort. Extra nutrition and rest in the days before.'
                elif event_day <= 13:
                    event_phase = 'Follicular'
                    event_rec = 'Rising energy - good performance expected. Train hard in the week before.'
                elif event_day <= 17:
                    event_phase = 'Ovulatory'
                    event_rec = 'Peak performance window - excellent timing! Warm up thoroughly due to elevated ACL risk.'
                else:
                    event_phase = 'Luteal'
                    event_rec = 'Manageable with preparation. Extra carbohydrates, longer warm-up, and prioritise sleep the week before.'
            except Exception:
                pass

        calendar = []
        if 0 <= days_until <= 14:
            calendar.append({
                'title': 'Period predicted to start',
                'date': adjusted_period.strftime('%Y-%m-%d'),
                'type': 'prediction',
                'description': 'Based on your average cycle length' + (' with adjustment factors' if delay else '') + '.'
            })
        if (ovulation_est - today).days >= 0:
            calendar.append({
                'title': 'Estimated ovulation window',
                'date': ovulation_est.strftime('%Y-%m-%d'),
                'type': 'prediction',
                'description': 'Peak performance window. Best time for high-intensity training or competition.'
            })
        if injury_flags:
            calendar.append({
                'title': 'Injury check-in reminder',
                'date': (today + timedelta(days=2)).strftime('%Y-%m-%d'),
                'type': 'warning',
                'description': 'Active injury flagged. Monitor closely and adjust training load.'
            })

        result = {
            'next_period_predicted': adjusted_period.strftime('%Y-%m-%d'),
            'next_period_confidence': 'medium' if delay else 'high',
            'period_shift_factors': shift_factors,
            'ovulation_estimated': ovulation_est.strftime('%Y-%m-%d'),
            'current_phase': current_phase,
            'current_phase_day': current_day,
            'event_phase_prediction': event_phase,
            'event_cycle_day_prediction': event_day,
            'event_recommendations': event_rec,
            'training_this_week': 'Focus on ' + current_phase + '-phase appropriate training. See Luna for specific advice.',
            'injury_flags': injury_flags,
            'environmental_impact': 'Adjustment factors applied based on logged data.' if shift_factors else 'No significant environmental factors logged.',
            'pattern_alerts': alerts,
            'nutrition_focus': 'See Luna for phase-specific nutrition advice.',
            'calendar_suggestions': calendar,
            'summary': ('Predicted next period: ' + adjusted_period.strftime('%B %d') + '. '
                        'Currently in ' + current_phase + ' phase, day ' + str(current_day) + '. '
                        + (str(len(alerts)) + ' pattern alert(s) noted.' if alerts else 'No major pattern alerts.'))
        }

        conn = get_db()
        for s in calendar:
            try:
                if s.get('date'):
                    conn.execute(
                        'INSERT INTO calendar_events (user_id, created_by, creator_role, title, description, event_date, event_type, is_ai_generated, color) VALUES (?,?,?,?,?,?,?,?,?)',
                        (user_id, user_id, 'ai', s['title'], s.get('description', ''), s['date'], s.get('type', 'prediction'), 1, '#8B5CF6')
                    )
            except Exception:
                pass
        conn.commit()
        conn.close()

        return result, None

    except Exception as e:
        return None, str(e)


def get_prediction(user_id):
    result, error = run_claude(user_id)
    if result:
        return result, None, 'claude'
    result, error2 = run_builtin(user_id)
    return result, error2, 'builtin'
