"""
auto_journal.py
Auto-Journal Engine for Red Moon Recovery.

After an athlete has logged enough data (MIN_ENTRIES_FOR_AUTO = 28),
this engine generates predicted daily journal entries automatically.
The athlete only needs to log DEVIATIONS from the prediction.

How it works:
1. For each day of the next 2 weeks, calculate cycle day and phase
2. Look up the athlete's personal averages for that phase from their history
3. Generate a predicted journal entry and calendar event
4. Mark entries as is_predicted=1 so the UI knows to show them differently
5. When athlete confirms or edits, is_confirmed=1 and deviation is logged
"""

import json
from datetime import datetime, timedelta
from database import get_db
from cognitive_model import (
    get_cognitive_phase, get_cognitive_prediction,
    PHASE_COGNITIVE_PROFILES, COGNITIVE_FIELDS, get_performance_impact_summary
)

MIN_ENTRIES_FOR_AUTO = 28  # ~1 cycle of daily data


def has_enough_data(user_id):
    """Check if the user has enough history for auto-journaling."""
    conn = get_db()
    count = conn.execute(
        'SELECT COUNT(*) as cnt FROM journal_entries WHERE user_id = ? AND is_predicted = 0',
        (user_id,)
    ).fetchone()['cnt']
    conn.close()
    return count >= MIN_ENTRIES_FOR_AUTO


def get_data_count(user_id):
    conn = get_db()
    count = conn.execute(
        'SELECT COUNT(*) as cnt FROM journal_entries WHERE user_id = ? AND is_predicted = 0',
        (user_id,)
    ).fetchone()['cnt']
    conn.close()
    return count


def get_phase_averages(user_id, phase):
    """Calculate average values for a given phase from real (non-predicted) entries."""
    conn = get_db()
    entries = conn.execute(
        '''SELECT sleep_quality, sleep_hours, energy, soreness, flow, cramps,
           mood, cognitive, rpe, motivation, stress_level, hydration
           FROM journal_entries
           WHERE user_id = ? AND is_predicted = 0
           AND phase LIKE ?
           ORDER BY entry_date DESC LIMIT 20''',
        (user_id, '%' + phase.split('_')[0] + '%')
    ).fetchall()
    conn.close()

    if not entries:
        return None

    entries = [dict(e) for e in entries]

    def avg_num(field):
        vals = [e[field] for e in entries if e.get(field) is not None]
        return round(sum(vals) / len(vals)) if vals else None

    def most_common(field):
        vals = [str(e[field]) for e in entries if e.get(field)]
        if not vals:
            return None
        return max(set(vals), key=vals.count)

    return {
        'sleep_quality':  avg_num('sleep_quality'),
        'sleep_hours':    round(sum(e['sleep_hours'] for e in entries if e.get('sleep_hours')) /
                                max(1, len([e for e in entries if e.get('sleep_hours')])), 1),
        'energy':         most_common('energy'),
        'soreness':       most_common('soreness'),
        'flow':           most_common('flow'),
        'cramps':         most_common('cramps'),
        'mood':           most_common('mood'),
        'cognitive':      most_common('cognitive'),
        'rpe':            avg_num('rpe'),
        'motivation':     avg_num('motivation'),
        'stress_level':   avg_num('stress_level'),
        'hydration':      most_common('hydration'),
    }


def generate_phase_description(phase, cycle_day, averages, cognitive_vals):
    """Generate a human-readable prediction summary for a day."""
    profile = PHASE_COGNITIVE_PROFILES.get(phase, PHASE_COGNITIVE_PROFILES.get('follicular'))
    phase_name = profile.get('label', phase.replace('_', ' ').title())

    parts = []
    parts.append("Predicted day " + str(cycle_day) + " (" + phase_name + " phase).")

    if averages:
        if averages.get('energy'):
            parts.append("Energy: " + str(averages['energy']) + ".")
        if averages.get('sleep_quality'):
            parts.append("Sleep quality typically " + str(averages['sleep_quality']) + "/10.")
        if averages.get('motivation'):
            parts.append("Motivation typically " + str(averages['motivation']) + "/10.")

    cog_sum = get_performance_impact_summary(cognitive_vals)
    if cog_sum:
        parts.append(cog_sum)

    return " ".join(parts)


def create_predicted_entry(user_id, target_date, cycle_day, phase):
    """
    Create a predicted journal entry for a future date.
    Uses phase averages + cognitive model.
    Does not overwrite existing real entries.
    """
    conn = get_db()

    # Do not create if a real entry already exists for this date
    existing = conn.execute(
        'SELECT id, is_predicted FROM journal_entries WHERE user_id = ? AND entry_date = ?',
        (user_id, target_date)
    ).fetchone()
    if existing and not existing['is_predicted']:
        conn.close()
        return None  # Real entry exists, skip

    averages = get_phase_averages(user_id, phase)
    cognitive_vals = get_cognitive_prediction(user_id, cycle_day)

    if existing and existing['is_predicted']:
        # Update existing prediction
        conn.execute(
            '''UPDATE journal_entries SET
               cycle_day=?, phase=?,
               sleep_quality=?, sleep_hours=?, energy=?, soreness=?,
               flow=?, cramps=?, mood=?, cognitive=?,
               rpe=?, motivation=?, stress_level=?, hydration=?,
               verbal_fluency=?, spatial_reasoning=?, working_memory=?,
               emotional_reactivity=?, risk_tolerance=?, creative_thinking=?,
               analytical_focus=?, social_confidence=?, competitive_drive=?,
               self_criticism=?, performance_impact=?
               WHERE user_id=? AND entry_date=? AND is_predicted=1''',
            (cycle_day, phase,
             averages.get('sleep_quality') if averages else None,
             averages.get('sleep_hours') if averages else None,
             averages.get('energy') if averages else None,
             averages.get('soreness') if averages else None,
             averages.get('flow') if averages else None,
             averages.get('cramps') if averages else None,
             averages.get('mood') if averages else None,
             averages.get('cognitive') if averages else None,
             averages.get('rpe') if averages else None,
             averages.get('motivation') if averages else None,
             averages.get('stress_level') if averages else None,
             averages.get('hydration') if averages else None,
             cognitive_vals.get('verbal_fluency'),
             cognitive_vals.get('spatial_reasoning'),
             cognitive_vals.get('working_memory'),
             cognitive_vals.get('emotional_reactivity'),
             cognitive_vals.get('risk_tolerance'),
             cognitive_vals.get('creative_thinking'),
             cognitive_vals.get('analytical_focus'),
             cognitive_vals.get('social_confidence'),
             cognitive_vals.get('competitive_drive'),
             cognitive_vals.get('self_criticism'),
             get_performance_impact_summary(cognitive_vals),
             user_id, target_date)
        )
        conn.commit()
        conn.close()
        return existing['id']

    # Insert new predicted entry
    conn.execute(
        '''INSERT INTO journal_entries
           (user_id, entry_date, is_predicted, is_confirmed, cycle_day, phase,
            sleep_quality, sleep_hours, energy, soreness, flow, cramps,
            mood, cognitive, rpe, motivation, stress_level, hydration,
            verbal_fluency, spatial_reasoning, working_memory, emotional_reactivity,
            risk_tolerance, creative_thinking, analytical_focus, social_confidence,
            competitive_drive, self_criticism, performance_impact)
           VALUES (?,?,1,0,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        (user_id, target_date, cycle_day, phase,
         averages.get('sleep_quality') if averages else None,
         averages.get('sleep_hours') if averages else None,
         averages.get('energy') if averages else None,
         averages.get('soreness') if averages else None,
         averages.get('flow') if averages else None,
         averages.get('cramps') if averages else None,
         averages.get('mood') if averages else None,
         averages.get('cognitive') if averages else None,
         averages.get('rpe') if averages else None,
         averages.get('motivation') if averages else None,
         averages.get('stress_level') if averages else None,
         averages.get('hydration') if averages else None,
         cognitive_vals.get('verbal_fluency'),
         cognitive_vals.get('spatial_reasoning'),
         cognitive_vals.get('working_memory'),
         cognitive_vals.get('emotional_reactivity'),
         cognitive_vals.get('risk_tolerance'),
         cognitive_vals.get('creative_thinking'),
         cognitive_vals.get('analytical_focus'),
         cognitive_vals.get('social_confidence'),
         cognitive_vals.get('competitive_drive'),
         cognitive_vals.get('self_criticism'),
         get_performance_impact_summary(cognitive_vals))
    )
    conn.commit()

    entry_id = conn.execute(
        'SELECT id FROM journal_entries WHERE user_id=? AND entry_date=?',
        (user_id, target_date)
    ).fetchone()['id']
    conn.close()
    return entry_id


def create_calendar_event_for_prediction(user_id, target_date, cycle_day, phase, cognitive_vals, averages):
    """Create a calendar event summarising the predicted day."""
    profile = PHASE_COGNITIVE_PROFILES.get(phase, {})
    phase_name = profile.get('label', phase.replace('_', ' ').title())
    cd = cognitive_vals.get('competitive_drive', 5)
    wm = cognitive_vals.get('working_memory', 5)

    if cd >= 8:
        intensity = "High intensity recommended"
    elif cd >= 6:
        intensity = "Moderate training day"
    else:
        intensity = "Recovery or light training recommended"

    title = phase_name + " - Day " + str(cycle_day) + " | " + intensity
    desc_parts = []
    if averages:
        if averages.get('energy'):
            desc_parts.append("Predicted energy: " + str(averages['energy']))
        if averages.get('motivation'):
            desc_parts.append("Motivation: ~" + str(averages['motivation']) + "/10")
    desc_parts.append("Competitive drive: " + str(round(cd, 1)) + "/10")
    desc_parts.append("Working memory: " + str(round(wm, 1)) + "/10")
    desc_parts.append(profile.get('athletic_cognitive_impact', ''))

    description = " | ".join(d for d in desc_parts if d)

    # Phase color coding
    phase_colors = {
        'menstrual':    '#E74C3C',
        'follicular':   '#F39C12',
        'ovulatory':    '#27AE60',
        'luteal_early': '#8E44AD',
        'luteal_late':  '#C0392B',
    }
    color = phase_colors.get(phase, '#8B5CF6')

    conn = get_db()
    # Remove old auto-journal calendar event for this date if any
    conn.execute(
        'DELETE FROM calendar_events WHERE user_id=? AND event_date=? AND is_auto_journal=1',
        (user_id, target_date)
    )
    conn.execute(
        '''INSERT INTO calendar_events
           (user_id, created_by, creator_role, title, description, event_date,
            event_type, color, is_ai_generated, is_auto_journal, is_editable_by_athlete)
           VALUES (?,?,?,?,?,?,?,?,1,1,1)''',
        (user_id, user_id, 'ai', title, description, target_date,
         'auto_journal', color)
    )
    conn.commit()
    conn.close()


def run_auto_journal(user_id, days_ahead=14):
    """
    Main entry point — generates predictions for the next N days.
    Returns a summary of what was generated.
    """
    if not has_enough_data(user_id):
        count = get_data_count(user_id)
        return {
            'enabled': False,
            'message': 'Auto-journal activates after ' + str(MIN_ENTRIES_FOR_AUTO) + ' logged entries. You have ' + str(count) + ' so far.',
            'entries_needed': MIN_ENTRIES_FOR_AUTO - count,
            'generated': 0
        }

    conn = get_db()
    profile = conn.execute('SELECT * FROM profiles WHERE user_id=?', (user_id,)).fetchone()
    conn.close()

    if not profile or not profile['last_period_start']:
        return {
            'enabled': False,
            'message': 'Set your last period start date in Profile to enable auto-journaling.',
            'generated': 0
        }

    profile = dict(profile)
    try:
        last_period = datetime.strptime(str(profile['last_period_start']), '%Y-%m-%d')
    except Exception:
        return {'enabled': False, 'message': 'Invalid last period start date.', 'generated': 0}

    cycle_len = int(profile.get('avg_cycle_length') or 28)
    today = datetime.now()
    generated = 0

    for i in range(days_ahead):
        target = today + timedelta(days=i)
        target_str = target.strftime('%Y-%m-%d')
        days_since = (target - last_period).days
        cycle_day = (days_since % cycle_len) + 1
        phase = get_cognitive_phase(cycle_day, cycle_len)
        cognitive_vals = get_cognitive_prediction(user_id, cycle_day)
        averages = get_phase_averages(user_id, phase)

        entry_id = create_predicted_entry(user_id, target_str, cycle_day, phase)
        if entry_id:
            create_calendar_event_for_prediction(user_id, target_str, cycle_day, phase, cognitive_vals, averages)
            generated += 1

    return {
        'enabled': True,
        'generated': generated,
        'message': 'Generated ' + str(generated) + ' predicted days.',
        'days_ahead': days_ahead
    }


def log_deviation(user_id, entry_date, field_name, predicted_value, actual_value, note=''):
    """Log when an athlete changes a predicted value."""
    conn = get_db()
    conn.execute(
        '''INSERT INTO deviation_logs (user_id, entry_date, field_name, predicted_value, actual_value, deviation_note)
           VALUES (?,?,?,?,?,?)''',
        (user_id, entry_date, field_name, str(predicted_value), str(actual_value), note)
    )
    # Update the journal entry with the actual value
    conn.execute(
        'UPDATE journal_entries SET is_confirmed=1 WHERE user_id=? AND entry_date=? AND is_predicted=1',
        (user_id, entry_date)
    )
    conn.commit()
    conn.close()


def confirm_predicted_entry(user_id, entry_date):
    """Mark a predicted entry as confirmed (no changes needed)."""
    conn = get_db()
    conn.execute(
        'UPDATE journal_entries SET is_confirmed=1 WHERE user_id=? AND entry_date=? AND is_predicted=1',
        (user_id, entry_date)
    )
    conn.commit()
    conn.close()


def get_deviation_history(user_id, limit=30):
    """Get deviation history to show what the athlete changed vs predictions."""
    conn = get_db()
    rows = conn.execute(
        '''SELECT * FROM deviation_logs WHERE user_id=?
           ORDER BY created_at DESC LIMIT ?''',
        (user_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
