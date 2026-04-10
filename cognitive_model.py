"""
cognitive_model.py
Deep cognitive and psychological cycle model for Red Moon Recovery.

Research basis:
- Estrogen enhances verbal fluency, working memory, and serotonin regulation
- Progesterone has calming but attention-reducing and fatigue-promoting effects
- Pre-menstrual estrogen/progesterone drop correlates with increased self-criticism,
  emotional reactivity, and reduced risk tolerance
- Ovulatory testosterone surge increases competitive drive and confidence
- Luteal progesterone increases anxiety sensitivity and reduces working memory capacity
- The follicular phase has the strongest cognitive performance profile for most athletes

Each cognitive dimension is rated 1-10 and has phase-specific baselines,
which are updated over time from the athlete's actual logged data.
"""

import json
import math
from datetime import datetime
from database import get_db


# ── Phase cognitive profiles (research-based defaults) ──

PHASE_COGNITIVE_PROFILES = {
    'menstrual': {
        'label': 'Menstrual',
        'days': '1-5',
        'primary_hormones': 'Estrogen and progesterone at lowest levels. Prostaglandins elevated.',
        'verbal_fluency':       {'baseline': 5, 'range': (3, 7),  'trend': 'Variable — can be sharp or foggy depending on symptom load'},
        'spatial_reasoning':    {'baseline': 5, 'range': (3, 7),  'trend': 'Neutral — neither peak nor trough'},
        'working_memory':       {'baseline': 4, 'range': (2, 6),  'trend': 'Often reduced, especially with significant cramping or fatigue'},
        'emotional_reactivity': {'baseline': 6, 'range': (4, 8),  'trend': 'Can be elevated early in phase, settling by day 3-4'},
        'risk_tolerance':       {'baseline': 4, 'range': (2, 6),  'trend': 'Reduced — conservative decision-making tends to dominate'},
        'creative_thinking':    {'baseline': 6, 'range': (4, 8),  'trend': 'Often surprisingly high — introspective and pattern-recognition strong'},
        'analytical_focus':     {'baseline': 4, 'range': (2, 7),  'trend': 'Varies with pain load — low when symptomatic, moderate when not'},
        'social_confidence':    {'baseline': 4, 'range': (2, 6),  'trend': 'Tends toward withdrawal and inward focus'},
        'competitive_drive':    {'baseline': 3, 'range': (1, 6),  'trend': 'Low — this phase favors recovery, not competition'},
        'self_criticism':       {'baseline': 6, 'range': (4, 9),  'trend': 'Can be elevated, especially about body and performance'},
        'performance_summary': 'Cognitive performance is reduced by symptom load rather than hormones directly. Rest, creative and reflective tasks suit this phase. Avoid high-stakes decisions when symptomatic.',
        'athletic_cognitive_impact': 'Reaction time and fine motor control may be slightly reduced with significant cramping. Decision-making under pressure can be less confident. This is a phase for technical review and mental skills work, not peak output.',
        'coaching_note': 'Athletes may be more receptive to honest feedback and introspective coaching conversations in this phase. Avoid motivational pressure — it often backfires.',
    },
    'follicular': {
        'label': 'Follicular',
        'days': '6-13',
        'primary_hormones': 'Estrogen rising steadily. FSH active. Dopamine and serotonin rising.',
        'verbal_fluency':       {'baseline': 8, 'range': (6, 10), 'trend': 'Peak or near-peak — communication, articulation, and language fast'},
        'spatial_reasoning':    {'baseline': 6, 'range': (5, 8),  'trend': 'Good but not peak — improves through the phase'},
        'working_memory':       {'baseline': 8, 'range': (6, 10), 'trend': 'Strong — estrogen directly enhances hippocampal function'},
        'emotional_reactivity': {'baseline': 4, 'range': (2, 6),  'trend': 'Low to moderate — emotionally stable and resilient'},
        'risk_tolerance':       {'baseline': 7, 'range': (5, 9),  'trend': 'Rising — good phase for trying new strategies'},
        'creative_thinking':    {'baseline': 7, 'range': (5, 9),  'trend': 'Strong — novel thinking and ideation flow easily'},
        'analytical_focus':     {'baseline': 8, 'range': (6, 10), 'trend': 'High — ability to break down complex problems is sharp'},
        'social_confidence':    {'baseline': 7, 'range': (5, 9),  'trend': 'Rising — social engagement feels natural and rewarding'},
        'competitive_drive':    {'baseline': 7, 'range': (5, 9),  'trend': 'Good — motivation and desire to improve are strong'},
        'self_criticism':       {'baseline': 3, 'range': (1, 5),  'trend': 'Low — inner critic is quieter, self-efficacy is higher'},
        'performance_summary': 'Best overall cognitive phase for most athletes. New skills, complex tactical work, and challenging training are all well-supported. Ideal for learning and skill acquisition.',
        'athletic_cognitive_impact': 'Fastest information processing of the cycle. Tactical decision-making, technical coaching cues, and new movement patterns are absorbed most readily. Peak phase for skill development and mental training.',
        'coaching_note': 'Athletes are highly receptive to new training stimuli and technical feedback. Great phase to introduce complexity and challenge. Mental toughness training lands well here.',
    },
    'ovulatory': {
        'label': 'Ovulatory',
        'days': '14-17',
        'primary_hormones': 'Estrogen peaks. LH surge. Brief testosterone spike. Dopamine high.',
        'verbal_fluency':       {'baseline': 9, 'range': (7, 10), 'trend': 'Peak — linguistic confidence and fluency at maximum'},
        'spatial_reasoning':    {'baseline': 7, 'range': (5, 9),  'trend': 'Good — three-dimensional thinking strong'},
        'working_memory':       {'baseline': 8, 'range': (6, 10), 'trend': 'Strong, though can be slightly distracted by social awareness'},
        'emotional_reactivity': {'baseline': 4, 'range': (2, 6),  'trend': 'Low — emotionally warm but not reactive'},
        'risk_tolerance':       {'baseline': 9, 'range': (7, 10), 'trend': 'Peak — testosterone surge drives willingness to take calculated risks'},
        'creative_thinking':    {'baseline': 8, 'range': (6, 10), 'trend': 'High — divergent thinking and ideation peak'},
        'analytical_focus':     {'baseline': 7, 'range': (5, 9),  'trend': 'Good but can be drawn toward big-picture over detail'},
        'social_confidence':    {'baseline': 9, 'range': (7, 10), 'trend': 'Peak — charismatic, expressive, and outwardly confident'},
        'competitive_drive':    {'baseline': 9, 'range': (7, 10), 'trend': 'Peak — testosterone makes this the most competitive window'},
        'self_criticism':       {'baseline': 2, 'range': (1, 4),  'trend': 'Lowest of the cycle — self-belief and perceived competence highest'},
        'performance_summary': 'Peak cognitive-athletic performance window. Confidence, risk tolerance, and competitive drive align perfectly. Ideal for competition, trials, and breaking performance barriers.',
        'athletic_cognitive_impact': 'Maximum reaction time, decision speed, and tactical boldness. Athletes often report feeling "in the zone" or experiencing flow states more easily. Best phase for high-stakes competition and testing limits.',
        'coaching_note': 'Athletes are most responsive to high-challenge training and will push past previous limits. Use this phase for time trials, competitions, and confidence-building challenges. Be aware risk tolerance may lead to overconfidence — warm up remains essential.',
    },
    'luteal_early': {
        'label': 'Luteal (Early)',
        'days': '18-22',
        'primary_hormones': 'Progesterone rising. Estrogen secondary peak then declining.',
        'verbal_fluency':       {'baseline': 6, 'range': (4, 8),  'trend': 'Moderate — slightly slower than ovulatory but still capable'},
        'spatial_reasoning':    {'baseline': 8, 'range': (6, 10), 'trend': 'Peak spatial phase — progesterone shifts thinking toward spatial tasks'},
        'working_memory':       {'baseline': 6, 'range': (4, 8),  'trend': 'Moderate and declining — progesterone subtly reduces working memory'},
        'emotional_reactivity': {'baseline': 5, 'range': (3, 7),  'trend': 'Moderate — calm but more inwardly focused'},
        'risk_tolerance':       {'baseline': 5, 'range': (3, 7),  'trend': 'Moderate — more careful and conservative emerging'},
        'creative_thinking':    {'baseline': 7, 'range': (5, 9),  'trend': 'Strong — progesterone supports lateral and associative thinking'},
        'analytical_focus':     {'baseline': 6, 'range': (4, 8),  'trend': 'Moderate — detail-oriented work still accessible'},
        'social_confidence':    {'baseline': 6, 'range': (4, 8),  'trend': 'Moderate — shifting from outward to inward'},
        'competitive_drive':    {'baseline': 6, 'range': (4, 8),  'trend': 'Moderate — steady rather than aggressive'},
        'self_criticism':       {'baseline': 4, 'range': (2, 6),  'trend': 'Mild — beginning to increase slightly'},
        'performance_summary': 'Solid cognitive phase with a progesterone-driven shift toward endurance, patience, and spatial tasks. Good for technical analysis, race strategy review, and steady consistent work.',
        'athletic_cognitive_impact': 'Spatial reasoning advantage makes this good for navigation, field sports tactics, and performance analysis. Less suited for explosive reactive decision-making than the ovulatory phase.',
        'coaching_note': 'Athletes may prefer structured, predictable training in early luteal. Good for reinforcing technical patterns and race strategy. Avoid high-novelty sessions.',
    },
    'luteal_late': {
        'label': 'Luteal (Late/PMS)',
        'days': '23-28',
        'primary_hormones': 'Progesterone and estrogen both declining. Inflammation rising. Cortisol sensitivity elevated.',
        'verbal_fluency':       {'baseline': 5, 'range': (2, 7),  'trend': 'Variable — word retrieval can feel sluggish'},
        'spatial_reasoning':    {'baseline': 6, 'range': (3, 8),  'trend': 'Still reasonable but declining from early luteal peak'},
        'working_memory':       {'baseline': 4, 'range': (2, 6),  'trend': 'Reduced — brain fog, difficulty holding multiple pieces of information'},
        'emotional_reactivity': {'baseline': 8, 'range': (5, 10), 'trend': 'High — amygdala hyperreactivity, heightened emotional sensitivity'},
        'risk_tolerance':       {'baseline': 3, 'range': (1, 5),  'trend': 'Low — loss aversion dominant, conservative and self-protective'},
        'creative_thinking':    {'baseline': 5, 'range': (2, 8),  'trend': 'Variable — can be either very rich or completely blocked'},
        'analytical_focus':     {'baseline': 4, 'range': (2, 6),  'trend': 'Often impaired — sustained attention is effortful'},
        'social_confidence':    {'baseline': 3, 'range': (1, 6),  'trend': 'Low — social withdrawal, increased sensitivity to criticism'},
        'competitive_drive':    {'baseline': 4, 'range': (2, 6),  'trend': 'Reduced — preserving energy rather than competing'},
        'self_criticism':       {'baseline': 8, 'range': (5, 10), 'trend': 'Peak — inner critic loudest of the entire cycle'},
        'performance_summary': 'Most cognitively challenging phase. The inner critic, emotional reactivity, and reduced working memory create a difficult mental environment for competition. Self-compassion and structure are key.',
        'athletic_cognitive_impact': 'Athletes may perceive their performance as worse than it objectively is due to heightened self-criticism. Decision-making under pressure is less bold. High-stakes competition in this phase requires extra mental preparation and self-regulatory strategies.',
        'coaching_note': 'Athletes are most sensitive to criticism and setbacks in late luteal. Use encouraging, collaborative framing. Expect that athletes may underestimate themselves. Mental toughness cues like process focus and self-compassion scripts are especially valuable here.',
    }
}


def get_cognitive_phase(cycle_day, cycle_length=28):
    if cycle_day <= 5:
        return 'menstrual'
    elif cycle_day <= 13:
        return 'follicular'
    elif cycle_day <= 17:
        return 'ovulatory'
    elif cycle_day <= 22:
        return 'luteal_early'
    else:
        return 'luteal_late'


def get_cognitive_profile(phase):
    return PHASE_COGNITIVE_PROFILES.get(phase, PHASE_COGNITIVE_PROFILES['follicular'])


COGNITIVE_FIELDS = [
    'verbal_fluency', 'spatial_reasoning', 'working_memory',
    'emotional_reactivity', 'risk_tolerance', 'creative_thinking',
    'analytical_focus', 'social_confidence', 'competitive_drive', 'self_criticism'
]

COGNITIVE_LABELS = {
    'verbal_fluency':       'Verbal Fluency',
    'spatial_reasoning':    'Spatial Reasoning',
    'working_memory':       'Working Memory',
    'emotional_reactivity': 'Emotional Reactivity',
    'risk_tolerance':       'Risk Tolerance',
    'creative_thinking':    'Creative Thinking',
    'analytical_focus':     'Analytical Focus',
    'social_confidence':    'Social Confidence',
    'competitive_drive':    'Competitive Drive',
    'self_criticism':       'Self-Criticism',
}

COGNITIVE_DESCRIPTIONS = {
    'verbal_fluency':       'Speed and ease of verbal communication, giving instructions, calling plays',
    'spatial_reasoning':    'Reading the field, visualising movement patterns, navigation tasks',
    'working_memory':       'Holding game plans in mind, multi-step instructions, tactical adjustments',
    'emotional_reactivity': 'Sensitivity to mistakes, referee decisions, crowd pressure (higher = more reactive)',
    'risk_tolerance':       'Willingness to attempt bold moves, try new tactics, take calculated chances',
    'creative_thinking':    'In-game improvisation, problem-solving, finding novel solutions under pressure',
    'analytical_focus':     'Sustained concentration, breaking down film, technical detail work',
    'social_confidence':    'Leadership, team communication, pre-competition presence and composure',
    'competitive_drive':    'Desire to win, push through discomfort, exceed previous performance',
    'self_criticism':       'Internal harsh self-evaluation after mistakes (higher = more self-critical)',
}


def update_cognitive_baselines(user_id):
    """Recalculate per-phase cognitive baselines from the user's actual logged data."""
    conn = get_db()
    entries = conn.execute(
        '''SELECT phase, cycle_day, verbal_fluency, spatial_reasoning, working_memory,
           emotional_reactivity, risk_tolerance, creative_thinking, analytical_focus,
           social_confidence, competitive_drive, self_criticism
           FROM journal_entries
           WHERE user_id = ? AND is_predicted = 0
           AND verbal_fluency IS NOT NULL
           ORDER BY entry_date DESC LIMIT 60''',
        (user_id,)
    ).fetchall()

    phase_data = {}
    for e in entries:
        e = dict(e)
        cog_phase = get_cognitive_phase(e.get('cycle_day') or 14)
        if cog_phase not in phase_data:
            phase_data[cog_phase] = {f: [] for f in COGNITIVE_FIELDS}
        for f in COGNITIVE_FIELDS:
            val = e.get(f)
            if val is not None:
                phase_data[cog_phase][f].append(int(val))

    for phase, data in phase_data.items():
        avgs = {}
        count = 0
        for f in COGNITIVE_FIELDS:
            vals = data[f]
            if vals:
                avgs[f] = sum(vals) / len(vals)
                count = max(count, len(vals))
            else:
                profile = PHASE_COGNITIVE_PROFILES.get(phase, {})
                avgs[f] = profile.get(f, {}).get('baseline', 5)

        existing = conn.execute(
            'SELECT id FROM cognitive_baselines WHERE user_id = ? AND phase = ?',
            (user_id, phase)
        ).fetchone()

        if existing:
            conn.execute(
                '''UPDATE cognitive_baselines SET
                   verbal_fluency=?, spatial_reasoning=?, working_memory=?,
                   emotional_reactivity=?, risk_tolerance=?, creative_thinking=?,
                   analytical_focus=?, social_confidence=?, competitive_drive=?,
                   self_criticism=?, sample_count=?, last_updated=CURRENT_TIMESTAMP
                   WHERE user_id=? AND phase=?''',
                (avgs.get('verbal_fluency'), avgs.get('spatial_reasoning'),
                 avgs.get('working_memory'), avgs.get('emotional_reactivity'),
                 avgs.get('risk_tolerance'), avgs.get('creative_thinking'),
                 avgs.get('analytical_focus'), avgs.get('social_confidence'),
                 avgs.get('competitive_drive'), avgs.get('self_criticism'),
                 count, user_id, phase)
            )
        else:
            conn.execute(
                '''INSERT INTO cognitive_baselines
                   (user_id, phase, verbal_fluency, spatial_reasoning, working_memory,
                   emotional_reactivity, risk_tolerance, creative_thinking, analytical_focus,
                   social_confidence, competitive_drive, self_criticism, sample_count)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (user_id, phase,
                 avgs.get('verbal_fluency'), avgs.get('spatial_reasoning'),
                 avgs.get('working_memory'), avgs.get('emotional_reactivity'),
                 avgs.get('risk_tolerance'), avgs.get('creative_thinking'),
                 avgs.get('analytical_focus'), avgs.get('social_confidence'),
                 avgs.get('competitive_drive'), avgs.get('self_criticism'), count)
            )

    conn.commit()
    conn.close()


def get_cognitive_prediction(user_id, cycle_day):
    """
    Get predicted cognitive values for a given cycle day.
    Uses personal baselines if available, otherwise research defaults.
    """
    cog_phase = get_cognitive_phase(cycle_day)
    profile = PHASE_COGNITIVE_PROFILES.get(cog_phase, PHASE_COGNITIVE_PROFILES['follicular'])

    conn = get_db()
    baseline = conn.execute(
        'SELECT * FROM cognitive_baselines WHERE user_id = ? AND phase = ?',
        (user_id, cog_phase)
    ).fetchone()
    conn.close()

    result = {}
    for f in COGNITIVE_FIELDS:
        if baseline and baseline[f] is not None:
            result[f] = round(float(baseline[f]), 1)
        else:
            result[f] = profile.get(f, {}).get('baseline', 5)

    result['phase'] = cog_phase
    result['source'] = 'personal_baseline' if baseline else 'research_default'
    result['sample_count'] = baseline['sample_count'] if baseline else 0
    return result


def get_performance_impact_summary(cognitive_vals, sport=None):
    """
    Generate a natural language performance impact summary
    based on the cognitive values.
    """
    lines = []

    wm = cognitive_vals.get('working_memory', 5)
    cd = cognitive_vals.get('competitive_drive', 5)
    sc_conf = cognitive_vals.get('social_confidence', 5)
    er = cognitive_vals.get('emotional_reactivity', 5)
    rt = cognitive_vals.get('risk_tolerance', 5)
    scrit = cognitive_vals.get('self_criticism', 5)
    af = cognitive_vals.get('analytical_focus', 5)

    if cd >= 8 and wm >= 7:
        lines.append("High competitive drive with strong working memory — ideal conditions for tactical performance.")
    elif cd >= 8 and wm < 6:
        lines.append("High competitive drive but reduced working memory — focus on automatic patterns rather than complex plays.")
    elif cd < 5:
        lines.append("Competitive drive is lower than usual — structure training to maintain effort through habit rather than motivation.")

    if er >= 7:
        lines.append("Elevated emotional reactivity means mistakes may feel amplified — pre-session process-focus cues are especially helpful today.")
    if scrit >= 7:
        lines.append("Self-criticism is heightened — performance may feel worse than it objectively is. Use objective metrics rather than internal evaluation.")
    if rt >= 8:
        lines.append("Risk tolerance is high — good conditions for attempting bold moves and testing limits.")
    elif rt <= 3:
        lines.append("Risk tolerance is low — conservative, well-rehearsed tactics will feel most natural.")
    if af >= 8:
        lines.append("Strong analytical focus — good day for technical work, film review, and detailed tactical preparation.")
    elif af <= 4:
        lines.append("Analytical focus is reduced — keep instructions simple and rely on rehearsed patterns.")
    if sc_conf >= 8:
        lines.append("Social confidence is high — leadership, communication, and team dynamics will flow well.")
    elif sc_conf <= 3:
        lines.append("Social confidence is lower — solo or low-social training formats may feel more comfortable.")

    if not lines:
        lines.append("Cognitive conditions are moderate across all dimensions — a standard training day is well-suited.")

    return " ".join(lines)
