import random
import re
import json
from datetime import datetime, timedelta
from database import get_db


class LunaAI:
    """
    Luna: conversational AI chatbot.
    Handles dialogue, asks follow-up questions about injuries, environment,
    flow, and previous-day changes. Calls the predictor when Claude is available,
    otherwise uses built-in prediction logic.
    """

    PHASE_INFO = {
        'menstrual': {
            'name': 'Menstrual', 'days': '1-5', 'emoji': '🔴',
            'hormones': 'estrogen and progesterone are at their lowest',
            'training': 'Gentle movement only — walking, yoga, light stretching. Keep intensity low and listen to your body carefully.',
            'nutrition': 'Prioritise iron-rich foods (leafy greens, red meat, lentils). Magnesium helps with cramps. Stay well hydrated.',
            'recovery': 'Maximise sleep and rest. Heat packs can ease cramps. High-intensity training should be avoided if symptomatic.',
            'mindset': 'Cognitive speed and pain tolerance may be lower. Treat this as a recovery and reflection phase.',
            'injury_risk': 'moderate — inflammation is naturally elevated during menstruation',
        },
        'follicular': {
            'name': 'Follicular', 'days': '6-13', 'emoji': '🌱',
            'hormones': 'estrogen is rising, boosting mood, energy, and motivation',
            'training': 'Increase intensity. Your body responds well to strength work and new skills. Good time to hit personal records.',
            'nutrition': 'Lean proteins and complex carbs to fuel rising energy. Slightly lower calorie needs than luteal phase.',
            'recovery': 'Fastest recovery of your cycle — you can push harder and bounce back quicker.',
            'mindset': 'Rising serotonin means higher mood and motivation. Great for social training and mental challenges.',
            'injury_risk': 'low to moderate — your most resilient phase overall',
        },
        'ovulatory': {
            'name': 'Ovulatory', 'days': '14-17', 'emoji': '✨',
            'hormones': 'estrogen peaks and LH surges — maximum energy and strength',
            'training': 'Peak performance window. Schedule your hardest sessions and competitions here. Strength, speed, and coordination are at their best.',
            'nutrition': 'Fuel well for high-intensity output. Carbs before sessions, protein after. Stay hydrated.',
            'recovery': 'Warm up thoroughly every time — estrogen peaks increase joint laxity and ACL injury risk significantly.',
            'mindset': 'Peak confidence and social energy. Use this window strategically for your biggest efforts.',
            'injury_risk': 'ELEVATED ACL and ligament risk due to estrogen-related joint laxity — thorough warm-up is essential',
        },
        'luteal': {
            'name': 'Luteal', 'days': '18-28', 'emoji': '🍂',
            'hormones': 'progesterone rises then both hormones drop — PMS symptoms may appear',
            'training': 'Early luteal is still productive. Late luteal (last 5-7 days) calls for lower intensity, steady-state cardio, and mobility work.',
            'nutrition': 'Metabolism is 100-300 cal/day higher. Complex carbs and magnesium help with PMS. Reduce caffeine late in this phase.',
            'recovery': 'Core temperature rises — keep room cool for sleep. Late luteal fatigue is real, plan for it.',
            'mindset': 'Mood more variable. Track which cycle days feel hardest mentally — patterns usually emerge.',
            'injury_risk': 'moderate — fatigue accumulates and increases error-based injury risk in late luteal',
        }
    }

    ENV_EFFECTS = {
        'heat': 'High temperatures increase perceived effort by 5-10% and raise dehydration risk. Your period timing can shift by 1-3 days with significant heat exposure. Cool down thoroughly after sessions and increase electrolyte intake.',
        'cold': 'Cold environments can slightly delay ovulation and affect flow heaviness. Warm up longer before training. Core temperature regulation is harder in the luteal phase.',
        'humidity': 'High humidity amplifies heat stress effects significantly. Reduces cooling efficiency by up to 30%. In the luteal phase when core temp is already elevated, high humidity can worsen sleep and recovery.',
        'altitude': 'Altitude changes can shift period timing by up to a week. Expect 2-3 weeks of adaptation. Increase iron intake. Estrogen and progesterone levels may fluctuate more.',
        'travel': 'Timezone changes and disrupted sleep from travel commonly delay or advance your period by 3-7 days. Track carefully after travel.',
        'stress': 'High psychological stress elevates cortisol which directly suppresses reproductive hormones. This is one of the most common causes of cycle disruption and can delay ovulation by days to weeks.',
    }

    FOLLOW_UP_BANK = {
        'injury': [
            "I want to make sure I factor any physical issues into your predictions. Have you had any injuries recently — even minor ones like tweaks, tightness, or things you have been working around?",
            "Before I give you my read on things, can you tell me about any injuries or pain points you are currently dealing with? Even something that feels minor can affect training load and recovery.",
            "How are your joints and muscles feeling overall? Any areas of concern, old injuries flaring up, or new niggles since your last entry?",
        ],
        'environment': [
            "Environmental conditions can shift your cycle and performance more than most people realise. What is the weather like where you are training — temperature, humidity, anything unusual?",
            "Are there any environmental factors I should factor in? Things like heat, cold, altitude changes, travel, or anything that has disrupted your usual routine?",
            "Has your training environment changed recently — new location, different climate, time zone changes from travel?",
        ],
        'flow': [
            "To help me make better predictions, can you describe your flow over the last couple of days — how heavy has it been, when did it start, and have you noticed anything different from your usual pattern?",
            "I am noticing your period may have started or is approaching. Has your flow been lighter, heavier, or different timing than what you normally experience?",
            "Flow characteristics can tell us a lot. Has your bleeding been consistent with your usual cycle, or are you noticing anything unusual — spotting before expected, heavier than normal, cramping earlier?",
        ],
        'yesterday_check': [
            "Looking back at yesterday's entry, you logged: {summary}. Now that you are a day further in, has anything changed from what you recorded? Sometimes things feel different in hindsight.",
            "Yesterday you noted: {summary}. Looking at today — did that pain ease up, did your energy recover, or did anything shift from what you described?",
            "I want to check in on yesterday. You recorded: {summary}. How does that compare to how you actually feel now — any updates or corrections?",
        ],
        'stress': [
            "Psychological stress is one of the biggest cycle disruptors. On a scale of 1 to 10, how would you rate your overall stress levels this week — from work, life, relationships, anything?",
            "How is your mental load right now outside of training? High life stress can delay ovulation and affect your whole cycle.",
        ],
        'prediction_followup': [
            "Based on what you have shared, I am updating my predictions. Is there anything else you think I should know — lifestyle changes, medication, diet shifts, anything unusual lately?",
            "That context really helps me refine the picture. One more thing — have you noticed any changes in your usual pre-period signs (cramps, mood shifts, breast tenderness) happening earlier or later than expected?",
        ]
    }

    def __init__(self, user_id):
        self.user_id = user_id
        self.profile = self._load_profile()
        self.entries = self._load_entries()
        self.name = (self.profile.get('name') or '').split()[0] if self.profile and self.profile.get('name') else ''

    def _load_profile(self):
        conn = get_db()
        row = conn.execute('SELECT * FROM profiles WHERE user_id = ?', (self.user_id,)).fetchone()
        conn.close()
        return dict(row) if row else {}

    def _load_entries(self):
        conn = get_db()
        rows = conn.execute('SELECT * FROM journal_entries WHERE user_id = ? ORDER BY entry_date DESC LIMIT 21', (self.user_id,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def _detect_phase(self):
        if not self.entries:
            return None
        phase = (self.entries[0].get('phase') or '').lower()
        for key in self.PHASE_INFO:
            if key in phase:
                return key
        return None

    def _yesterday_summary(self):
        if not self.entries:
            return None
        yesterday = self.entries[0]
        parts = []
        if yesterday.get('energy'):
            parts.append("energy: " + str(yesterday['energy']))
        if yesterday.get('sleep_quality'):
            parts.append("sleep " + str(yesterday['sleep_quality']) + "/10")
        if yesterday.get('soreness'):
            parts.append("soreness: " + str(yesterday['soreness']))
        if yesterday.get('mood'):
            parts.append("mood: " + str(yesterday['mood']))
        if yesterday.get('flow') and yesterday['flow'] != 'None':
            parts.append("flow: " + str(yesterday['flow']))
        if yesterday.get('pain_notes'):
            parts.append("pain: " + str(yesterday['pain_notes']))
        if yesterday.get('injuries'):
            parts.append("injuries: " + str(yesterday['injuries']))
        if not parts:
            return None
        return ", ".join(parts)

    def _period_approaching(self):
        if not self.profile or not self.profile.get('last_period_start'):
            return False
        try:
            last = datetime.strptime(self.profile['last_period_start'], '%Y-%m-%d')
            cycle_len = int(self.profile.get('avg_cycle_length') or 28)
            next_period = last + timedelta(days=cycle_len)
            today = datetime.now()
            days_away = (next_period - today).days
            return 0 <= days_away <= 5
        except Exception:
            return False

    def _period_just_started(self):
        if not self.entries:
            return False
        for e in self.entries[:3]:
            if e.get('flow') and e['flow'].lower() not in ['none', '', 'no flow']:
                if e.get('cycle_day') and int(e['cycle_day'] or 99) <= 3:
                    return True
        return False

    def _detect_patterns(self):
        patterns = []
        if len(self.entries) < 3:
            return patterns
        recent = self.entries[:7]
        sleep_vals = [e['sleep_quality'] for e in recent if e.get('sleep_quality')]
        if sleep_vals and sum(sleep_vals) / len(sleep_vals) < 5:
            patterns.append('consistently low sleep quality (average ' + str(round(sum(sleep_vals)/len(sleep_vals), 1)) + '/10)')
        for e in recent:
            if e.get('rpe') and e.get('motivation'):
                if int(e['rpe']) >= 8 and int(e['motivation']) <= 4:
                    patterns.append('training at high effort despite very low motivation — a potential overreach signal')
                    break
        pain_entries = [e for e in recent if e.get('soreness') and 'sharp' in (e.get('soreness') or '').lower()]
        if len(pain_entries) >= 2:
            patterns.append('recurring sharp or specific pain across multiple entries')
        low_energy = [e for e in recent if 'low' in (e.get('energy') or '').lower()]
        if len(low_energy) >= 3:
            patterns.append('persistent low energy across 3 or more recent days')
        injury_entries = [e for e in recent if e.get('injuries') and str(e['injuries']).strip() not in ['', 'none', 'None', 'no']]
        if injury_entries:
            patterns.append('active or recent injuries noted: ' + str(injury_entries[0]['injuries']))
        env_entries = [e for e in recent if e.get('environmental_notes') and str(e['environmental_notes']).strip()]
        if env_entries:
            patterns.append('environmental factors logged: ' + str(env_entries[0]['environmental_notes']))
        stress_vals = [e['stress_level'] for e in recent if e.get('stress_level')]
        if stress_vals and sum(stress_vals)/len(stress_vals) >= 7:
            patterns.append('high average stress levels (' + str(round(sum(stress_vals)/len(stress_vals), 1)) + '/10) which can disrupt cycle timing')
        return patterns

    def _pick_follow_up(self, topic='general'):
        bank = self.FOLLOW_UP_BANK.get(topic, self.FOLLOW_UP_BANK['injury'])
        q = random.choice(bank)
        if '{summary}' in q:
            summary = self._yesterday_summary()
            if summary:
                q = q.replace('{summary}', summary)
            else:
                q = random.choice(self.FOLLOW_UP_BANK['injury'])
        return q

    def _should_ask_yesterday(self):
        if not self.entries or len(self.entries) < 2:
            return False
        yesterday = self.entries[0]
        yesterday_date = yesterday.get('entry_date', '')
        today = datetime.now().strftime('%Y-%m-%d')
        if yesterday_date == today:
            return False
        try:
            entry_dt = datetime.strptime(yesterday_date, '%Y-%m-%d')
            today_dt = datetime.now()
            return (today_dt - entry_dt).days == 1
        except Exception:
            return False

    def respond(self, user_message, history):
        msg = user_message.lower().strip()

        # Always check if we should open with yesterday's check-in
        if self._should_ask_yesterday() and len(history) <= 2:
            return self._respond_yesterday_check()

        # Always check if period is approaching or just started
        if self._period_approaching() and len(history) <= 2:
            return self._respond_period_approaching()

        if self._period_just_started() and len(history) <= 4:
            return self._respond_period_started()

        # Greetings
        if re.search(r'^(hi|hello|hey|hiya|good morning|good evening|good afternoon)[\s!?.]*$', msg):
            return self._respond_greeting()

        # Yesterday changes
        if any(w in msg for w in ['yesterday', 'changed', 'different now', 'update', 'actually']):
            return self._respond_yesterday_update(msg)

        # Injury
        if any(w in msg for w in ['injury', 'injured', 'hurt', 'pain', 'acl', 'knee', 'hip', 'shoulder', 'sore', 'niggle', 'tweak', 'sprain', 'strain', 'tear']):
            return self._respond_injury(msg)

        # Environment
        if any(w in msg for w in ['weather', 'hot', 'cold', 'humid', 'altitude', 'travel', 'heat', 'temperature', 'climate', 'environment']):
            return self._respond_environment(msg)

        # Flow / period
        if any(w in msg for w in ['flow', 'period', 'bleeding', 'spotting', 'heavy', 'light flow', 'cramp', 'menstrual', 'started', 'late', 'early', 'missed']):
            return self._respond_flow(msg)

        # Prediction / forecast
        if any(w in msg for w in ['predict', 'forecast', 'when will', 'next period', 'when is', 'expect', 'future', 'upcoming', 'anticipate']):
            return self._respond_prediction(msg)

        # Phase
        if any(w in msg for w in ['phase', 'cycle day', 'which phase', 'what phase', 'current phase']):
            return self._respond_phase()

        # Training
        if any(w in msg for w in ['train', 'workout', 'exercise', 'lift', 'run', 'cardio', 'strength', 'performance', 'session', 'compete', 'race', 'event']):
            return self._respond_training(msg)

        # Sleep
        if any(w in msg for w in ['sleep', 'tired', 'fatigue', 'exhausted', 'rest', 'insomnia', 'hrv', 'waking']):
            return self._respond_sleep(msg)

        # Mood
        if any(w in msg for w in ['mood', 'anxious', 'anxiety', 'irritable', 'emotional', 'motivation', 'brain fog', 'focus', 'stress', 'overwhelmed', 'depressed', 'sad']):
            return self._respond_mood(msg)

        # Nutrition
        if any(w in msg for w in ['eat', 'food', 'nutrition', 'diet', 'craving', 'hungry', 'calorie', 'protein', 'carb', 'fuel', 'supplement', 'iron', 'magnesium']):
            return self._respond_nutrition(msg)

        # Patterns
        if any(w in msg for w in ['pattern', 'insight', 'trend', 'notice', 'data', 'history']):
            return self._respond_patterns()

        # Recovery
        if any(w in msg for w in ['recover', 'recovery', 'rest day', 'deload', 'stretch', 'mobility', 'foam roll']):
            return self._respond_recovery(msg)

        # Help
        if any(w in msg for w in ['help', 'what can you', 'what do you', 'capabilities', 'topics', 'options']):
            return self._respond_help()

        # Thanks
        if any(w in msg for w in ['thank', 'thanks', 'helpful', 'great', 'awesome', 'perfect']):
            return self._respond_thanks()

        return self._respond_contextual(msg, history)

    def _respond_greeting(self):
        phase = self._detect_phase()
        patterns = self._detect_patterns()
        name_str = self.name + "! " if self.name else "! "

        response = "Hi " + name_str + "Good to hear from you. "

        if phase:
            info = self.PHASE_INFO[phase]
            response += "Based on your last entry you appear to be in your **" + info['name'] + " phase** " + info['emoji'] + " — when " + info['hormones'] + ". "

        if patterns:
            response += "\n\nI have noticed a few things in your recent data:\n"
            for p in patterns[:2]:
                response += "- " + p.capitalize() + "\n"

        response += "\n\n" + self._pick_follow_up('injury')
        return response

    def _respond_yesterday_check(self):
        summary = self._yesterday_summary()
        if not summary:
            return self._respond_greeting()

        yesterday_date = self.entries[0].get('entry_date', 'yesterday')
        response = ("Before anything else, I want to do a quick check-in on your entry from **" + yesterday_date + "**.\n\n"
                   "You logged: " + summary + "\n\n"
                   "Now that you are a day further along — has anything changed from what you recorded? "
                   "Sometimes energy, pain, or flow feel different in hindsight, and those updates really help me give you better predictions.")
        return response

    def _respond_yesterday_update(self, msg):
        response = "Thank you for the update — changes like this are important for tracking patterns accurately. "
        if any(w in msg for w in ['pain', 'hurt', 'injury', 'worse', 'sore']):
            response += "If pain has worsened since your last entry, that is worth noting carefully. Escalating pain across consecutive days — especially in the same location — is a signal to ease off training and potentially get it assessed. "
        if any(w in msg for w in ['better', 'improved', 'good', 'fine']):
            response += "It is great to hear things have improved. Day-to-day recovery is a useful indicator of where you are in your cycle. "
        if any(w in msg for w in ['flow', 'period', 'bleeding']):
            response += "Flow changes between days can indicate whether your cycle is running ahead or behind typical timing. "

        response += ("\n\nI have logged your update mentally. To make it official, head to the **Journal** tab and add today's entry — "
                    "even a quick one helps the prediction engine stay accurate.\n\n"
                    + self._pick_follow_up('environment'))
        return response

    def _respond_period_approaching(self):
        if not self.profile:
            return self._respond_greeting()
        cycle_len = int(self.profile.get('avg_cycle_length') or 28)
        try:
            last = datetime.strptime(self.profile['last_period_start'], '%Y-%m-%d')
            next_p = last + timedelta(days=cycle_len)
            days_away = (next_p - datetime.now()).days
        except Exception:
            days_away = 3

        response = ("Based on your cycle history, your period is predicted to arrive in approximately **" + str(days_away) + " day(s)**. "
                   "This is a good time to prepare.\n\n"
                   "In the days before your period (late Luteal phase), most athletes experience:\n"
                   "- Higher perceived effort for the same workload\n"
                   "- More variable mood and motivation\n"
                   "- Increased carb cravings (your metabolism is genuinely higher)\n"
                   "- Potential sleep disruption from rising core temperature\n\n"
                   "I want to help you plan around this. " + self._pick_follow_up('flow'))
        return response

    def _respond_period_started(self):
        response = ("It looks like your period may have just started based on your recent entries. "
                   "First — how are you feeling right now compared to what you expected?\n\n"
                   "I have a few important questions to help me update your predictions:\n\n"
                   "1. Did your period arrive at the expected time, early, or late?\n"
                   "2. How is the flow — lighter or heavier than your usual?\n"
                   "3. Any cramping or symptoms that feel different from previous cycles?\n\n"
                   "These details help me recalibrate your cycle predictions and give better training recommendations going forward. "
                   + self._pick_follow_up('environment'))
        return response

    def _respond_injury(self, msg):
        phase = self._detect_phase()
        response = "Injuries need to be factored carefully into your training plan and my predictions. "

        if phase == 'ovulatory':
            response += ("\n\n**Important — you appear to be in or near your Ovulatory phase.** "
                        "This is the highest-risk window for ACL and ligament injuries because estrogen peaks and temporarily increases joint laxity. "
                        "Any existing instability or soft-tissue issue is more vulnerable right now. Please be conservative.")

        if any(w in msg for w in ['acl', 'knee', 'ligament']):
            response += ("\n\nFor ACL or knee concerns specifically: female athletes face 2-8x higher ACL injury risk than males, "
                        "and this peaks around ovulation. Focus on hip and glute strengthening, single-leg stability, "
                        "and proper landing mechanics year-round. If this is an acute injury, stop training through it and seek assessment.")

        if any(w in msg for w in ['new', 'just', 'happened', 'today', 'just now']):
            response += ("\n\nFor a new injury, the immediate priorities are: stop loading the area, apply ice for 15-20 minutes, "
                        "elevate if possible, and assess whether you need professional evaluation. "
                        "I will factor this into your calendar and training recommendations.")

            # Add a calendar suggestion for rest
            self._suggest_calendar_event('Rest day — injury management', 3, 'recovery')

        response += ("\n\nPlease log the injury details in today's journal entry under the injuries field so I can track it accurately. "
                    "\n\n" + self._pick_follow_up('environment'))
        return response

    def _respond_environment(self, msg):
        matched_effects = []
        for key, effect in self.ENV_EFFECTS.items():
            if key in msg:
                matched_effects.append(effect)

        if matched_effects:
            response = "Environmental factors have real, measurable effects on both your training and your cycle:\n\n"
            for effect in matched_effects:
                response += "- " + effect + "\n\n"
        else:
            response = ("Environmental conditions affect your cycle more than most people realise. "
                       "Here are the key ones to watch:\n\n"
                       "**Heat/High temperature:** Increases perceived effort, raises dehydration risk, can shift period timing by 1-3 days.\n\n"
                       "**Cold:** Can slightly delay ovulation and affect flow heaviness.\n\n"
                       "**High humidity:** Amplifies heat stress, reduces cooling efficiency significantly.\n\n"
                       "**Altitude changes:** Can shift period timing by up to a week during adaptation.\n\n"
                       "**Travel/Timezone change:** Disrupted sleep and circadian rhythm commonly delays or advances period by 3-7 days.\n\n"
                       "**High stress:** Cortisol suppresses reproductive hormones and is one of the most common cycle disruptors.\n\n")

        response += "Make sure to log environmental factors in your journal entry — I use that data to adjust my cycle timing predictions.\n\n"
        response += self._pick_follow_up('stress')
        return response

    def _respond_flow(self, msg):
        response = ""

        if any(w in msg for w in ['late', 'missed', 'not started', 'overdue', 'delayed']):
            response = ("A late or missed period is very common and can be caused by many factors:\n\n"
                       "- **High stress** (cortisol suppresses GnRH which drives the cycle)\n"
                       "- **Significant training load changes** — both overtraining and sudden under-training can delay ovulation\n"
                       "- **Environmental changes** — heat, altitude, travel, timezone disruption\n"
                       "- **Nutritional changes** — under-eating (even mild energy deficit) is a common cause\n"
                       "- **Illness** — any significant immune response can delay ovulation\n\n"
                       "If your period is more than 7 days late and none of these apply, it is worth consulting a healthcare provider.\n\n")
            response += self._pick_follow_up('stress')

        elif any(w in msg for w in ['early', 'ahead', 'before expected']):
            response = ("An early period can be caused by:\n\n"
                       "- A shorter luteal phase (less than 10-12 days) which may warrant medical attention if recurring\n"
                       "- Significant stress or physical exertion in the second half of your cycle\n"
                       "- Travel or major environmental changes\n"
                       "- Hormonal fluctuations\n\n"
                       "Log the start date in your journal and profile so I can recalibrate your predictions.\n\n")
            response += self._pick_follow_up('environment')

        elif any(w in msg for w in ['heavy', 'heavier', 'lots of', 'a lot']):
            response = ("Heavier than usual flow can be related to several things:\n\n"
                       "- **Stress** — both physical and psychological\n"
                       "- **Nutritional factors** — low iron, vitamin K, or omega-3 imbalance\n"
                       "- **Training load** — very intense training cycles sometimes increase flow\n"
                       "- **Environmental heat** — can affect flow characteristics\n\n"
                       "If heavy flow is significantly impacting your daily life or training, this is worth discussing with a healthcare provider.\n\n")
            response += self._pick_follow_up('injury')

        elif any(w in msg for w in ['light', 'lighter', 'spotting', 'barely']):
            response = ("Lighter than usual flow or spotting can indicate:\n\n"
                       "- High training load (athletic amenorrhea spectrum)\n"
                       "- Relative Energy Deficiency in Sport (RED-S) — very important to rule out if you are training hard\n"
                       "- Natural variation if everything else is normal\n"
                       "- Hormonal contraceptive effects\n\n"
                       "Log the details in your journal. If flow has been consistently getting lighter over several cycles, mention it to your doctor.\n\n")
            response += self._pick_follow_up('stress')

        else:
            response = ("Flow characteristics are one of the most useful signals for cycle health and prediction accuracy. "
                       "To give you better predictions I need to know:\n\n"
                       "1. When exactly did your period start?\n"
                       "2. How does the heaviness compare to your usual?\n"
                       "3. Any change in cramping intensity or timing?\n"
                       "4. Any spotting before the main flow started?\n\n"
                       "The more detail you log in your journal, the more accurately I can predict your next cycle and adjust your training calendar.")

        return response

    def _respond_prediction(self, msg):
        if not self.profile or not self.profile.get('last_period_start'):
            return ("To make accurate predictions I need a bit more data from you. "
                   "Please make sure your **last period start date** is saved in your Profile, "
                   "and keep logging your daily journal entries. "
                   "The more cycles of data I have, the more accurate my predictions become.\n\n"
                   + self._pick_follow_up('flow'))

        try:
            last = datetime.strptime(self.profile['last_period_start'], '%Y-%m-%d')
            cycle_len = int(self.profile.get('avg_cycle_length') or 28)
            next_period = last + timedelta(days=cycle_len)
            days_until = (next_period - datetime.now()).days

            # Estimate adjustments
            patterns = self._detect_patterns()
            adjustments = []
            delay_days = 0

            for p in patterns:
                if 'high average stress' in p:
                    delay_days += 2
                    adjustments.append("high stress levels (possible +1-3 day delay)")
                if 'environmental' in p:
                    delay_days += 1
                    adjustments.append("recent environmental factors (possible +1-2 day shift)")
                if 'low sleep' in p:
                    delay_days += 1
                    adjustments.append("disrupted sleep (minor delay possible)")

            adjusted_date = next_period + timedelta(days=delay_days)

            response = ("**Cycle Prediction Summary**\n\n"
                       "Base prediction (from your average cycle length of " + str(cycle_len) + " days):\n"
                       "Next period: **" + next_period.strftime('%B %d, %Y') + "** (" + str(days_until) + " days from today)\n\n")

            if adjustments:
                response += ("**Adjusted prediction:** " + adjusted_date.strftime('%B %d, %Y') + "\n"
                            "Adjustment factors from your recent data:\n")
                for a in adjustments:
                    response += "- " + a + "\n"
                response += "\n"

            # Phase predictions
            ovulation_est = last + timedelta(days=cycle_len - 14)
            response += ("**Estimated upcoming key dates:**\n"
                        "Ovulation window: around **" + ovulation_est.strftime('%B %d') + "** (±2 days)\n"
                        "Late Luteal (PMS window): " + (next_period - timedelta(days=7)).strftime('%B %d') + " — " + (next_period - timedelta(days=1)).strftime('%B %d') + "\n\n")

            if self.profile.get('event_date'):
                try:
                    event = datetime.strptime(self.profile['event_date'], '%Y-%m-%d')
                    event_cycle_day = ((event - last).days % cycle_len) + 1
                    response += ("**Your upcoming event (" + self.profile['event_date'] + "):**\n"
                                "Predicted cycle day: **" + str(event_cycle_day) + "**\n")
                    if event_cycle_day <= 5:
                        response += "Predicted phase: Menstrual 🔴 — plan for lower energy and higher perceived effort.\n"
                    elif event_cycle_day <= 13:
                        response += "Predicted phase: Follicular 🌱 — rising energy, good performance expected.\n"
                    elif event_cycle_day <= 17:
                        response += "Predicted phase: Ovulatory ✨ — peak performance window, excellent timing!\n"
                    else:
                        response += "Predicted phase: Luteal 🍂 — manageable with proper preparation and fuelling.\n"
                    response += "\n"
                except Exception:
                    pass

            response += ("**Note:** These predictions improve with more data. If you notice your cycle shifting, "
                        "update your last period start date in your Profile and I will recalibrate everything.\n\n"
                        + self._pick_follow_up('prediction_followup'))

        except Exception as e:
            response = ("I ran into an issue generating your prediction. Please make sure your last period start date is "
                       "saved correctly in your Profile (format: YYYY-MM-DD).\n\n" + self._pick_follow_up('flow'))

        return response

    def _respond_phase(self):
        phase = self._detect_phase()
        if not phase:
            return ("I do not have a logged phase for you yet. Make sure to select your current phase when logging your journal entries. "
                   "\n\n" + self._pick_follow_up('flow'))

        info = self.PHASE_INFO[phase]
        latest = self.entries[0]
        cycle_day = latest.get('cycle_day', '?')

        response = ("You appear to be in your **" + info['name'] + " phase** " + info['emoji'] + " (around cycle day " + str(cycle_day) + ").\n\n"
                   "**Hormones:** " + info['hormones'].capitalize() + ".\n\n"
                   "**Training:** " + info['training'] + "\n\n"
                   "**Injury risk:** " + info['injury_risk'].capitalize() + ".\n\n"
                   "**Nutrition:** " + info['nutrition'] + "\n\n"
                   + self._pick_follow_up('injury'))
        return response

    def _respond_training(self, msg):
        phase = self._detect_phase()
        patterns = self._detect_patterns()
        response = ""

        if phase:
            info = self.PHASE_INFO[phase]
            response = "In your **" + info['name'] + " phase** " + info['emoji'] + ":\n\n" + info['training'] + "\n\n"
            if phase == 'ovulatory':
                response += "**ACL warning:** Estrogen peaks now increase joint laxity. Always include a thorough warm-up. \n\n"
        else:
            response = ("Without a logged phase, here is a general cycle-based training guide:\n\n"
                       "🌱 Follicular: High-intensity and strength work.\n"
                       "✨ Ovulatory: Peak performance — races, PRs, hardest sessions.\n"
                       "🍂 Luteal early: Moderate training. Luteal late: Lower intensity, endurance.\n"
                       "🔴 Menstrual: Rest or very light movement.\n\n")

        # Flag overreach pattern
        if patterns:
            for p in patterns:
                if 'high effort' in p and 'low motivation' in p:
                    response += "**Pattern alert:** Your data shows high RPE alongside low motivation. This combination often precedes illness or injury — consider a lighter session today.\n\n"
                if 'injury' in p:
                    response += "**Injury flag:** You have active injuries in your recent entries. Training load should be adjusted accordingly.\n\n"

        response += self._pick_follow_up('environment')
        return response

    def _respond_sleep(self, msg):
        phase = self._detect_phase()
        response = "Sleep quality and your cycle are deeply connected. "

        if phase == 'luteal':
            response += ("In the **Luteal phase**, rising progesterone elevates core body temperature, which disrupts sleep architecture — "
                        "especially in the second half of this phase. This is very common and physiological, not just mental. ")
        elif phase == 'menstrual':
            response += "During menstruation, cramping and discomfort can fragment sleep. Factor this into your training expectations. "
        elif phase == 'follicular':
            response += "The Follicular phase normally brings the best sleep of your cycle. If you are sleeping poorly now, look at external stress, caffeine, or screens. "

        response += ("\n\n**Evidence-based sleep tips:**\n"
                    "- Consistent sleep/wake time even on weekends\n"
                    "- Cool room (especially important in luteal phase)\n"
                    "- No screens 30 minutes before bed\n"
                    "- Limit caffeine after 2pm\n"
                    "- Magnesium glycinate 200-400mg before bed can significantly help\n\n"
                    + self._pick_follow_up('stress'))
        return response

    def _respond_mood(self, msg):
        phase = self._detect_phase()
        response = ""

        if 'stress' in msg or 'overwhelmed' in msg:
            response = ("Stress is one of the most powerful cycle disruptors — elevated cortisol directly suppresses the hormones that drive your cycle. "
                       "High stress can delay ovulation by days to weeks, which pushes everything back. "
                       "This is important for prediction accuracy.\n\n")
            response += self._pick_follow_up('stress')

        elif 'brain fog' in msg or 'focus' in msg:
            response = ("Brain fog is common in late Luteal phase as estrogen and progesterone both drop. "
                       "It usually lifts within 1-2 days of your period starting. "
                       "Staying hydrated, eating regularly, and reducing caffeine paradoxically helps.\n\n")

        elif 'anxious' in msg or 'anxiety' in msg:
            response = ("Cyclical anxiety that worsens in the second half of your cycle is a well-documented phenomenon — "
                       "progesterone metabolites can affect GABA receptors and estrogen drop affects serotonin. "
                       "Tracking which days feel most anxious can help you plan lower-stress commitments during those windows.\n\n")

        elif 'motivat' in msg:
            response = ("Low motivation is one of the hallmark late-Luteal symptoms. "
                       "Rather than pushing through at full intensity, consider whether the bravest training decision today is to back off. "
                       "A well-executed moderate session beats a sloppy hard one.\n\n")

        else:
            response = "Your mood and cycle are closely linked through estrogen and progesterone. Tracking mood daily helps reveal patterns that most people find very useful. \n\n"

        if phase:
            response += "**In your current " + self.PHASE_INFO[phase]['name'] + " phase:** " + self.PHASE_INFO[phase]['mindset'] + "\n\n"

        response += self._pick_follow_up('environment')
        return response

    def _respond_nutrition(self, msg):
        phase = self._detect_phase()
        if phase:
            info = self.PHASE_INFO[phase]
            response = "**Nutrition for your " + info['name'] + " phase:**\n\n" + info['nutrition'] + "\n\n"
        else:
            response = ("Nutritional needs shift meaningfully across your cycle:\n\n"
                       "🔴 Menstrual: Iron-rich foods, magnesium, hydration.\n"
                       "🌱 Follicular: Lean proteins, complex carbs. Lower calorie needs.\n"
                       "✨ Ovulatory: Fuel well for peak output. Carbs before sessions.\n"
                       "🍂 Luteal: 100-300 extra calories/day. Complex carbs reduce cravings. Magnesium helps PMS.\n\n")

        if 'craving' in msg:
            response += "Carb and chocolate cravings before your period are driven by real hormonal shifts — your body needs magnesium and quick energy. Satisfying them with nutrient-dense options works better than fighting them.\n\n"

        response += self._pick_follow_up('injury')
        return response

    def _respond_patterns(self):
        patterns = self._detect_patterns()
        if not patterns:
            if not self.entries:
                return ("I do not have enough data yet to spot patterns. Log your journal entries consistently for 1-2 weeks and I will start identifying trends.\n\n" + self._pick_follow_up('flow'))
            return ("I am not seeing any concerning patterns in your recent data, which is great. Keep logging consistently and I will flag anything that emerges.\n\n" + self._pick_follow_up('injury'))

        response = "Here is what I am seeing across your recent journal entries:\n\n"
        for p in patterns:
            response += "- " + p.capitalize() + "\n"
        response += ("\n\nSome of these may be cycle-phase related rather than problems to fix. "
                    "The key is whether they repeat on the same cycle days each month — that would indicate a predictable pattern to plan around.\n\n"
                    + self._pick_follow_up('environment'))
        return response

    def _respond_recovery(self, msg):
        phase = self._detect_phase()
        response = "Recovery and your cycle interact in important ways. "

        if phase:
            info = self.PHASE_INFO[phase]
            response += "\n\nIn your **" + info['name'] + " phase:** " + info['recovery'] + "\n\n"

        response += ("**Universal recovery principles:**\n"
                    "- Sleep is the most powerful recovery tool — protect it above everything\n"
                    "- Protein within 30-60 minutes post-training accelerates muscle repair\n"
                    "- Active recovery often beats complete rest\n"
                    "- Deload every 4-6 weeks prevents accumulated fatigue\n"
                    "- Heat (sauna, bath) reduces soreness and improves parasympathetic tone\n\n"
                    + self._pick_follow_up('injury'))
        return response

    def _respond_thanks(self):
        options = [
            "Really glad that helped! " + self._pick_follow_up('environment'),
            "Happy to help" + (", " + self.name if self.name else "") + ". " + self._pick_follow_up('injury'),
            "Of course — that is what I am here for. " + self._pick_follow_up('flow'),
        ]
        return random.choice(options)

    def _respond_help(self):
        return ("Here is what I can help with:\n\n"
               "🔴 **Cycle phases** — what each phase means for training and recovery\n"
               "📈 **Predictions** — when your next period is expected, phase forecasting for events\n"
               "⚠️ **Injuries** — how injuries interact with your cycle and training\n"
               "🌡️ **Environmental factors** — how heat, cold, altitude, and travel affect your cycle\n"
               "🩸 **Flow tracking** — what changes in flow might mean\n"
               "😴 **Sleep and recovery** — cycle-specific advice\n"
               "🧠 **Mood and stress** — how to track and prepare for mood patterns\n"
               "🥗 **Nutrition** — phase-specific fuelling\n"
               "📊 **Pattern spotting** — trends in your logged data\n"
               "📅 **Calendar planning** — I can suggest training adjustments based on your predictions\n\n"
               "The more you log in your journal, the more personalised and accurate my responses become. What would you like to explore?")

    def _respond_contextual(self, msg, history):
        # Try to match to the last topic from history
        if history and len(history) > 1:
            for h in reversed(history[:-1]):
                if h['role'] == 'assistant':
                    last = h['content'].lower()
                    if any(w in last for w in ['sleep', 'tired', 'rest']):
                        return self._respond_sleep(msg)
                    if any(w in last for w in ['train', 'workout', 'session']):
                        return self._respond_training(msg)
                    if any(w in last for w in ['eat', 'food', 'nutrition']):
                        return self._respond_nutrition(msg)
                    if any(w in last for w in ['injury', 'pain', 'hurt']):
                        return self._respond_injury(msg)
                    if any(w in last for w in ['period', 'flow', 'phase']):
                        return self._respond_flow(msg)
                    break

        phase = self._detect_phase()
        response = ""
        if phase:
            response = ("That is a great question. To give you the most useful answer, keep in mind you appear to be in your **"
                       + self.PHASE_INFO[phase]['name'] + " phase** — that context shapes what is happening in your body.\n\n")

        response += ("Could you tell me a bit more about what you are trying to figure out? "
                    "I want to make sure I give you the most relevant advice — is this about training, how you are feeling physically, "
                    "mood, nutrition, your cycle timing, or something else?\n\n"
                    + self._pick_follow_up('injury'))
        return response

    def _suggest_calendar_event(self, title, days_ahead, event_type):
        try:
            conn = get_db()
            date = (datetime.now() + timedelta(days=days_ahead)).strftime('%Y-%m-%d')
            conn.execute('''INSERT INTO calendar_events
                (user_id, created_by, creator_role, title, description, event_date, event_type, is_ai_generated, color)
                VALUES (?,?,?,?,?,?,?,?,?)''',
                (self.user_id, self.user_id, 'ai',
                 title, 'Auto-suggested by Luna based on your journal data',
                 date, event_type, 1,
                 '#8B5CF6'))
            conn.commit()
            conn.close()
        except Exception:
            pass
