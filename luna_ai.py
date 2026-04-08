import random
import re
import json
from datetime import datetime, timedelta
from database import get_db


class LunaAI:

    PHASE_INFO = {
        'menstrual': {
            'name': 'Menstrual', 'days': '1-5', 'emoji': 'Red circle',
            'hormones': 'estrogen and progesterone are at their lowest',
            'training': 'Gentle movement only such as walking, yoga, and light stretching. Keep intensity low and listen to your body carefully.',
            'nutrition': 'Prioritise iron-rich foods like leafy greens, red meat, and lentils. Magnesium helps with cramps. Stay well hydrated.',
            'recovery': 'Maximise sleep and rest. Heat packs can ease cramps. Avoid high-intensity training if symptomatic.',
            'mindset': 'Cognitive speed and pain tolerance may be lower. Treat this as a recovery and reflection phase.',
            'injury_risk': 'moderate - inflammation is naturally elevated during menstruation',
        },
        'follicular': {
            'name': 'Follicular', 'days': '6-13', 'emoji': 'Green circle',
            'hormones': 'estrogen is rising which boosts mood, energy, and motivation',
            'training': 'Increase intensity. Your body responds well to strength work and new skills. Good time to hit personal records.',
            'nutrition': 'Lean proteins and complex carbs to fuel rising energy. Slightly lower calorie needs than luteal phase.',
            'recovery': 'Fastest recovery of your cycle. You can push harder and bounce back quicker.',
            'mindset': 'Rising serotonin means higher mood and motivation. Great for social training and mental challenges.',
            'injury_risk': 'low to moderate - your most resilient phase overall',
        },
        'ovulatory': {
            'name': 'Ovulatory', 'days': '14-17', 'emoji': 'Star',
            'hormones': 'estrogen peaks and LH surges giving you maximum energy and strength',
            'training': 'Peak performance window. Schedule your hardest sessions and competitions here. Strength, speed, and coordination are at their best.',
            'nutrition': 'Fuel well for high-intensity output. Carbs before sessions, protein after. Stay hydrated.',
            'recovery': 'Warm up thoroughly every time. Estrogen peaks increase joint laxity and ACL injury risk significantly.',
            'mindset': 'Peak confidence and social energy. Use this window strategically for your biggest efforts.',
            'injury_risk': 'ELEVATED ACL and ligament risk due to estrogen-related joint laxity - thorough warm-up is essential',
        },
        'luteal': {
            'name': 'Luteal', 'days': '18-28', 'emoji': 'Leaf',
            'hormones': 'progesterone rises then both hormones drop and PMS symptoms may appear',
            'training': 'Early luteal is still productive. Late luteal calls for lower intensity, steady-state cardio, and mobility work.',
            'nutrition': 'Metabolism is 100 to 300 cal per day higher. Complex carbs and magnesium help with PMS. Reduce caffeine late in this phase.',
            'recovery': 'Core temperature rises so keep room cool for sleep. Late luteal fatigue is real so plan for it.',
            'mindset': 'Mood more variable. Track which cycle days feel hardest mentally and patterns usually emerge.',
            'injury_risk': 'moderate - fatigue accumulates and increases error-based injury risk in late luteal',
        }
    }

    ENV_EFFECTS = {
        'heat': 'High temperatures increase perceived effort by 5 to 10 percent and raise dehydration risk. Your period timing can shift by 1 to 3 days with significant heat exposure. Cool down thoroughly after sessions and increase electrolyte intake.',
        'cold': 'Cold environments can slightly delay ovulation and affect flow heaviness. Warm up longer before training. Core temperature regulation is harder in the luteal phase.',
        'humid': 'High humidity amplifies heat stress effects significantly. Reduces cooling efficiency by up to 30 percent. In the luteal phase when core temp is already elevated, high humidity can worsen sleep and recovery.',
        'altitude': 'Altitude changes can shift period timing by up to a week. Expect 2 to 3 weeks of adaptation. Increase iron intake. Estrogen and progesterone levels may fluctuate more.',
        'travel': 'Timezone changes and disrupted sleep from travel commonly delay or advance your period by 3 to 7 days. Track carefully after travel.',
        'stress': 'High psychological stress elevates cortisol which directly suppresses reproductive hormones. This is one of the most common causes of cycle disruption and can delay ovulation by days to weeks.',
    }

    FOLLOW_UP_QUESTIONS = {
        'injury': [
            "Before I give you my full read, can you tell me about any injuries or pain you are currently dealing with? Even something minor like tightness or an old niggle can affect training load and recovery.",
            "I want to make sure I factor in any physical issues. Have you had any injuries recently, even small ones you have been working around?",
            "How are your joints and muscles feeling overall? Any areas of concern, old injuries flaring up, or new tweaks since your last entry?",
        ],
        'environment': [
            "Environmental conditions can shift your cycle more than most people realise. What is the weather like where you are training, and have there been any big changes like travel or extreme temperatures?",
            "Are there any environmental factors I should know about? Things like heat, cold, altitude changes, travel, or anything that has disrupted your usual routine?",
            "Has your training environment changed recently, such as a new location, different climate, or time zone changes from travel?",
        ],
        'flow': [
            "To help me make better predictions, can you describe your flow over the last couple of days? How heavy has it been, when did it start, and have you noticed anything different from your usual pattern?",
            "I am noticing your period may have started or is approaching. Has your flow been lighter, heavier, or different timing than what you normally experience?",
            "Flow characteristics can tell us a lot. Has your bleeding been consistent with your usual cycle, or are you noticing anything unusual?",
        ],
        'yesterday': [
            "Looking back at yesterday you logged: {summary}. Now that you are a day further in, has anything changed from what you recorded?",
            "Yesterday you noted: {summary}. Looking at today, did that pain ease up, did your energy recover, or did anything shift?",
            "I want to check in on yesterday. You recorded: {summary}. How does that compare to how you actually feel now?",
        ],
        'stress': [
            "Psychological stress is one of the biggest cycle disruptors. On a scale of 1 to 10, how would you rate your overall stress levels this week?",
            "How is your mental load right now outside of training? High life stress can delay ovulation and affect your whole cycle.",
        ],
        'general': [
            "What has been feeling best about your training lately?",
            "Is there a specific goal or event you are working toward right now?",
            "What part of your cycle do you find most challenging to train through?",
        ]
    }

    def __init__(self, user_id):
        self.user_id = user_id
        self.profile = self._load_profile()
        self.entries = self._load_entries()
        self.name = ''
        if self.profile and self.profile.get('name'):
            parts = str(self.profile['name']).split()
            if parts:
                self.name = parts[0]

    def _load_profile(self):
        try:
            conn = get_db()
            row = conn.execute('SELECT * FROM profiles WHERE user_id = ?', (self.user_id,)).fetchone()
            conn.close()
            return dict(row) if row else {}
        except Exception:
            return {}

    def _load_entries(self):
        try:
            conn = get_db()
            rows = conn.execute('SELECT * FROM journal_entries WHERE user_id = ? ORDER BY entry_date DESC LIMIT 21', (self.user_id,)).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception:
            return []

    def _detect_phase(self):
        if not self.entries:
            return None
        phase = str(self.entries[0].get('phase') or '').lower()
        for key in self.PHASE_INFO:
            if key in phase:
                return key
        return None

    def _yesterday_summary(self):
        if not self.entries:
            return None
        e = self.entries[0]
        parts = []
        if e.get('energy'):
            parts.append("energy: " + str(e['energy']))
        if e.get('sleep_quality'):
            parts.append("sleep " + str(e['sleep_quality']) + "/10")
        if e.get('soreness'):
            parts.append("soreness: " + str(e['soreness']))
        if e.get('mood'):
            parts.append("mood: " + str(e['mood']))
        if e.get('flow') and str(e['flow']).lower() not in ('none', ''):
            parts.append("flow: " + str(e['flow']))
        if e.get('pain_notes'):
            parts.append("pain: " + str(e['pain_notes']))
        if e.get('injuries') and str(e['injuries']).strip() not in ('', 'none', 'no'):
            parts.append("injuries: " + str(e['injuries']))
        if not parts:
            return None
        return ", ".join(parts)

    def _should_ask_yesterday(self):
        if not self.entries or len(self.entries) < 2:
            return False
        e = self.entries[0]
        yesterday_date = str(e.get('entry_date') or '')
        today = datetime.now().strftime('%Y-%m-%d')
        if yesterday_date == today:
            return False
        try:
            entry_dt = datetime.strptime(yesterday_date, '%Y-%m-%d')
            return (datetime.now() - entry_dt).days == 1
        except Exception:
            return False

    def _period_approaching(self):
        if not self.profile or not self.profile.get('last_period_start'):
            return False
        try:
            last = datetime.strptime(str(self.profile['last_period_start']), '%Y-%m-%d')
            cycle_len = int(self.profile.get('avg_cycle_length') or 28)
            next_period = last + timedelta(days=cycle_len)
            days_away = (next_period - datetime.now()).days
            return 0 <= days_away <= 5
        except Exception:
            return False

    def _period_just_started(self):
        if not self.entries:
            return False
        for e in self.entries[:3]:
            flow = str(e.get('flow') or '').lower()
            if flow and flow not in ('none', 'no flow', ''):
                cycle_day = e.get('cycle_day')
                if cycle_day and int(cycle_day) <= 3:
                    return True
        return False

    def _detect_patterns(self):
        patterns = []
        if len(self.entries) < 3:
            return patterns
        recent = self.entries[:7]
        sleep_vals = [e['sleep_quality'] for e in recent if e.get('sleep_quality')]
        if sleep_vals and sum(sleep_vals) / len(sleep_vals) < 5:
            patterns.append('consistently low sleep quality (average ' + str(round(sum(sleep_vals) / len(sleep_vals), 1)) + '/10)')
        for e in recent:
            if e.get('rpe') and e.get('motivation'):
                if int(e['rpe']) >= 8 and int(e['motivation']) <= 4:
                    patterns.append('training at high effort despite very low motivation - possible overreach signal')
                    break
        pain_entries = [e for e in recent if 'sharp' in str(e.get('soreness') or '').lower()]
        if len(pain_entries) >= 2:
            patterns.append('recurring sharp or specific pain across multiple entries')
        low_energy = [e for e in recent if 'low' in str(e.get('energy') or '').lower()]
        if len(low_energy) >= 3:
            patterns.append('persistent low energy across 3 or more recent days')
        injury_entries = [e for e in recent if str(e.get('injuries') or '').strip().lower() not in ('', 'none', 'no')]
        if injury_entries:
            patterns.append('active injuries noted: ' + str(injury_entries[0]['injuries']))
        env_entries = [e for e in recent if str(e.get('environmental_notes') or '').strip()]
        if env_entries:
            patterns.append('environmental factors logged: ' + str(env_entries[0]['environmental_notes']))
        stress_vals = [e['stress_level'] for e in recent if e.get('stress_level')]
        if stress_vals and sum(stress_vals) / len(stress_vals) >= 7:
            patterns.append('high average stress (' + str(round(sum(stress_vals) / len(stress_vals), 1)) + '/10) which can disrupt cycle timing')
        return patterns

    def _pick_follow_up(self, topic='general'):
        bank = self.FOLLOW_UP_QUESTIONS.get(topic, self.FOLLOW_UP_QUESTIONS['general'])
        q = random.choice(bank)
        if '{summary}' in q:
            summary = self._yesterday_summary()
            if summary:
                q = q.replace('{summary}', summary)
            else:
                q = random.choice(self.FOLLOW_UP_QUESTIONS['injury'])
        return q

    def respond(self, user_message, history):
        msg = user_message.lower().strip()

        # Check yesterday first on opening messages
        if self._should_ask_yesterday() and len(history) <= 2:
            return self._respond_yesterday_check()

        if self._period_approaching() and len(history) <= 2:
            return self._respond_period_approaching()

        if self._period_just_started() and len(history) <= 4:
            return self._respond_period_started()

        if re.search(r'^(hi|hello|hey|hiya|good morning|good evening|good afternoon)[\s!?.]*$', msg):
            return self._respond_greeting()

        if any(w in msg for w in ['yesterday', 'changed', 'different now', 'update', 'actually']):
            return self._respond_yesterday_update(msg)

        if any(w in msg for w in ['injury', 'injured', 'hurt', 'pain', 'acl', 'knee', 'hip', 'shoulder', 'sore', 'niggle', 'tweak', 'sprain', 'strain']):
            return self._respond_injury(msg)

        if any(w in msg for w in ['weather', 'hot', 'cold', 'humid', 'altitude', 'travel', 'heat', 'temperature', 'climate', 'environment']):
            return self._respond_environment(msg)

        if any(w in msg for w in ['flow', 'period', 'bleeding', 'spotting', 'heavy', 'light flow', 'cramp', 'menstrual', 'started', 'late', 'early', 'missed']):
            return self._respond_flow(msg)

        if any(w in msg for w in ['predict', 'forecast', 'when will', 'next period', 'when is', 'expect', 'future', 'upcoming']):
            return self._respond_prediction(msg)

        if any(w in msg for w in ['phase', 'cycle day', 'which phase', 'what phase', 'current phase']):
            return self._respond_phase()

        if any(w in msg for w in ['train', 'workout', 'exercise', 'lift', 'run', 'cardio', 'strength', 'performance', 'session', 'compete', 'race', 'event']):
            return self._respond_training(msg)

        if any(w in msg for w in ['sleep', 'tired', 'fatigue', 'exhausted', 'rest', 'insomnia', 'hrv', 'waking']):
            return self._respond_sleep(msg)

        if any(w in msg for w in ['mood', 'anxious', 'anxiety', 'irritable', 'emotional', 'motivation', 'brain fog', 'focus', 'stress', 'overwhelmed', 'depressed']):
            return self._respond_mood(msg)

        if any(w in msg for w in ['eat', 'food', 'nutrition', 'diet', 'craving', 'hungry', 'calorie', 'protein', 'carb', 'fuel']):
            return self._respond_nutrition(msg)

        if any(w in msg for w in ['pattern', 'insight', 'trend', 'notice', 'data', 'history']):
            return self._respond_patterns()

        if any(w in msg for w in ['recover', 'recovery', 'rest day', 'deload', 'stretch', 'mobility']):
            return self._respond_recovery(msg)

        if any(w in msg for w in ['help', 'what can you', 'what do you', 'capabilities', 'topics']):
            return self._respond_help()

        if any(w in msg for w in ['thank', 'thanks', 'helpful', 'great', 'awesome', 'perfect']):
            return self._respond_thanks()

        return self._respond_contextual(msg, history)

    def _respond_greeting(self):
        phase = self._detect_phase()
        patterns = self._detect_patterns()
        name_str = (self.name + "! ") if self.name else "! "
        response = "Hi " + name_str + "Good to hear from you. "
        if phase:
            info = self.PHASE_INFO[phase]
            response += "Based on your last entry you appear to be in your " + info['name'] + " phase " + info['emoji'] + " where " + info['hormones'] + ". "
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
        yesterday_date = str(self.entries[0].get('entry_date', 'yesterday'))
        return ("Before anything else, I want to do a quick check-in on your entry from " + yesterday_date + ".\n\n"
                "You logged: " + summary + "\n\n"
                "Now that you are a day further along, has anything changed from what you recorded? "
                "Sometimes energy, pain, or flow feel different in hindsight, and those updates really help me give you better predictions.")

    def _respond_yesterday_update(self, msg):
        response = "Thank you for the update. Changes like this are important for tracking patterns accurately. "
        if any(w in msg for w in ['pain', 'hurt', 'injury', 'worse', 'sore']):
            response += "If pain has worsened since your last entry, that is worth noting carefully. Escalating pain across consecutive days is a signal to ease off training and potentially get it assessed. "
        if any(w in msg for w in ['better', 'improved', 'good', 'fine']):
            response += "It is great to hear things have improved. Day-to-day recovery is a useful indicator of where you are in your cycle. "
        if any(w in msg for w in ['flow', 'period', 'bleeding']):
            response += "Flow changes between days can indicate whether your cycle is running ahead or behind typical timing. "
        response += "\n\nHead to the Journal tab and add today's entry to make it official. Even a quick one helps the prediction engine stay accurate.\n\n"
        response += self._pick_follow_up('environment')
        return response

    def _respond_period_approaching(self):
        if not self.profile:
            return self._respond_greeting()
        cycle_len = int(self.profile.get('avg_cycle_length') or 28)
        try:
            last = datetime.strptime(str(self.profile['last_period_start']), '%Y-%m-%d')
            next_p = last + timedelta(days=cycle_len)
            days_away = (next_p - datetime.now()).days
        except Exception:
            days_away = 3
        response = ("Based on your cycle history, your period is predicted to arrive in approximately " + str(days_away) + " day(s). "
                    "This is a good time to prepare.\n\n"
                    "In the days before your period, most athletes experience higher perceived effort, more variable mood, "
                    "increased carb cravings, and potential sleep disruption from rising core temperature.\n\n"
                    "I want to help you plan around this. " + self._pick_follow_up('flow'))
        return response

    def _respond_period_started(self):
        return ("It looks like your period may have just started based on your recent entries. "
                "First, how are you feeling right now compared to what you expected?\n\n"
                "I have a few questions to help me update your predictions:\n\n"
                "1. Did your period arrive at the expected time, early, or late?\n"
                "2. How is the flow compared to your usual?\n"
                "3. Any cramping or symptoms that feel different from previous cycles?\n\n"
                "These details help me recalibrate your predictions and give better training recommendations. "
                + self._pick_follow_up('environment'))

    def _respond_injury(self, msg):
        phase = self._detect_phase()
        response = "Injuries need to be factored carefully into your training plan and my predictions. "
        if phase == 'ovulatory':
            response += ("\n\nImportant note: you appear to be in or near your Ovulatory phase. "
                         "This is the highest-risk window for ACL and ligament injuries because estrogen peaks and temporarily increases joint laxity. "
                         "Any existing instability is more vulnerable right now. Please be conservative.")
        if any(w in msg for w in ['acl', 'knee', 'ligament']):
            response += ("\n\nFor ACL or knee concerns: female athletes face 2 to 8 times higher ACL injury risk than males, "
                         "and this risk peaks around ovulation. Focus on hip and glute strengthening, single-leg stability, "
                         "and proper landing technique year-round.")
        if any(w in msg for w in ['new', 'just', 'happened', 'today']):
            response += ("\n\nFor a new injury the immediate priorities are: stop loading the area, apply ice for 15 to 20 minutes, "
                         "elevate if possible, and assess whether you need professional evaluation. "
                         "I will factor this into your training recommendations.")
        response += "\n\nPlease log the injury details in today's journal entry under the injuries field so I can track it accurately.\n\n"
        response += self._pick_follow_up('environment')
        return response

    def _respond_environment(self, msg):
        matched = []
        for key, effect in self.ENV_EFFECTS.items():
            if key in msg:
                matched.append(effect)
        if matched:
            response = "Environmental factors have real, measurable effects on both your training and your cycle:\n\n"
            for effect in matched:
                response += "- " + effect + "\n\n"
        else:
            response = ("Environmental conditions affect your cycle more than most people realise. "
                        "Heat can shift period timing by 1 to 3 days. Cold can slightly delay ovulation. "
                        "High humidity amplifies heat stress significantly. Altitude changes can shift timing by up to a week. "
                        "Travel and timezone disruption commonly delays or advances periods by 3 to 7 days. "
                        "And high stress is one of the most common cycle disruptors, suppressing reproductive hormones directly.\n\n")
        response += "Make sure to log environmental factors in your journal entry. I use that data to adjust my cycle timing predictions.\n\n"
        response += self._pick_follow_up('stress')
        return response

    def _respond_flow(self, msg):
        if any(w in msg for w in ['late', 'missed', 'not started', 'overdue', 'delayed']):
            response = ("A late or missed period is very common and can be caused by: high stress (cortisol suppresses the cycle), "
                        "significant training load changes, environmental changes like heat or altitude, "
                        "nutritional changes or under-eating, or illness.\n\n"
                        "If your period is more than 7 days late and none of these apply, it is worth consulting a healthcare provider.\n\n")
            response += self._pick_follow_up('stress')
        elif any(w in msg for w in ['early', 'ahead', 'before expected']):
            response = ("An early period can be caused by a shorter luteal phase, significant stress or exertion in the second half of your cycle, "
                        "travel or major environmental changes, or hormonal fluctuations.\n\n"
                        "Log the start date in your profile so I can recalibrate your predictions.\n\n")
            response += self._pick_follow_up('environment')
        elif any(w in msg for w in ['heavy', 'heavier']):
            response = ("Heavier than usual flow can be related to stress, nutritional factors like low iron or omega-3 imbalance, "
                        "high training load, or environmental heat. If heavy flow is significantly impacting your daily life or training, "
                        "this is worth discussing with a healthcare provider.\n\n")
            response += self._pick_follow_up('injury')
        elif any(w in msg for w in ['light', 'lighter', 'spotting', 'barely']):
            response = ("Lighter than usual flow or spotting can indicate high training load, Relative Energy Deficiency in Sport (RED-S), "
                        "or natural variation. If flow has been consistently getting lighter over several cycles, mention it to your doctor.\n\n")
            response += self._pick_follow_up('stress')
        else:
            response = ("Flow characteristics are one of the most useful signals for cycle health. To give you better predictions I need to know:\n\n"
                        "1. When exactly did your period start?\n"
                        "2. How does the heaviness compare to your usual?\n"
                        "3. Any change in cramping intensity or timing?\n"
                        "4. Any spotting before the main flow started?\n\n"
                        "The more detail you log in your journal, the more accurately I can predict your next cycle.")
        return response

    def _respond_prediction(self, msg):
        if not self.profile or not self.profile.get('last_period_start'):
            return ("To make accurate predictions I need your last period start date saved in your Profile. "
                    "Head to the Profile tab and save that information, then use the Predict tab for a full forecast.\n\n"
                    + self._pick_follow_up('flow'))
        try:
            last = datetime.strptime(str(self.profile['last_period_start']), '%Y-%m-%d')
            cycle_len = int(self.profile.get('avg_cycle_length') or 28)
            next_period = last + timedelta(days=cycle_len)
            days_until = (next_period - datetime.now()).days
            ovulation_est = last + timedelta(days=cycle_len - 14)
            patterns = self._detect_patterns()
            delay_days = 0
            adjustments = []
            for p in patterns:
                if 'high average stress' in p:
                    delay_days += 2
                    adjustments.append("high stress levels - possible 1 to 3 day delay")
                if 'environmental' in p:
                    delay_days += 1
                    adjustments.append("recent environmental factors - possible 1 to 2 day shift")
                if 'low sleep' in p:
                    delay_days += 1
                    adjustments.append("disrupted sleep - minor delay possible")
            adjusted = next_period + timedelta(days=delay_days)
            response = ("My current prediction for your next period: " + next_period.strftime('%B %d, %Y') + " (in " + str(days_until) + " days).\n\n")
            if adjustments:
                response += "Adjusted to " + adjusted.strftime('%B %d') + " based on:\n"
                for a in adjustments:
                    response += "- " + a + "\n"
                response += "\n"
            response += "Estimated ovulation window: around " + ovulation_est.strftime('%B %d') + " plus or minus 2 days.\n\n"
            if self.profile.get('event_date'):
                try:
                    event = datetime.strptime(str(self.profile['event_date']), '%Y-%m-%d')
                    event_day = ((event - last).days % cycle_len) + 1
                    response += "Your upcoming event (" + str(self.profile['event_date']) + "): predicted cycle day " + str(event_day) + ".\n\n"
                except Exception:
                    pass
            response += "For a full detailed report go to the Predict tab.\n\n"
            response += self._pick_follow_up('prediction_followup' if len(self.FOLLOW_UP_QUESTIONS.get('prediction_followup', [])) else 'flow')
        except Exception:
            response = ("I ran into an issue generating your prediction. Please make sure your last period start date is "
                        "saved correctly in your Profile.\n\n" + self._pick_follow_up('flow'))
        return response

    def _respond_phase(self):
        phase = self._detect_phase()
        if not phase:
            return ("I do not have a logged phase for you yet. Make sure to select your current phase when logging journal entries.\n\n"
                    + self._pick_follow_up('flow'))
        info = self.PHASE_INFO[phase]
        latest = self.entries[0]
        cycle_day = latest.get('cycle_day', '?')
        return ("You appear to be in your " + info['name'] + " phase (around cycle day " + str(cycle_day) + ").\n\n"
                "Hormones: " + info['hormones'].capitalize() + ".\n\n"
                "Training: " + info['training'] + "\n\n"
                "Injury risk: " + info['injury_risk'].capitalize() + ".\n\n"
                "Nutrition: " + info['nutrition'] + "\n\n"
                + self._pick_follow_up('injury'))

    def _respond_training(self, msg):
        phase = self._detect_phase()
        patterns = self._detect_patterns()
        response = ""
        if phase:
            info = self.PHASE_INFO[phase]
            response = "In your " + info['name'] + " phase:\n\n" + info['training'] + "\n\n"
            if phase == 'ovulatory':
                response += "ACL warning: estrogen peaks now increase joint laxity. Always warm up thoroughly.\n\n"
        else:
            response = ("Here is a general cycle-based training guide:\n\n"
                        "Follicular: high-intensity and strength work.\n"
                        "Ovulatory: peak performance, races, and hardest sessions.\n"
                        "Luteal early: moderate training. Luteal late: lower intensity and endurance.\n"
                        "Menstrual: rest or very light movement.\n\n")
        for p in patterns:
            if 'high effort' in p and 'low motivation' in p:
                response += "Pattern alert: your data shows high RPE alongside low motivation. Consider a lighter session today.\n\n"
            if 'injury' in p:
                response += "Injury flag: you have active injuries in your recent entries. Adjust training load accordingly.\n\n"
        response += self._pick_follow_up('environment')
        return response

    def _respond_sleep(self, msg):
        phase = self._detect_phase()
        response = "Sleep quality and your cycle are deeply connected. "
        if phase == 'luteal':
            response += "In the Luteal phase, rising progesterone elevates core body temperature and disrupts sleep architecture. This is physiological and very common. "
        elif phase == 'menstrual':
            response += "During menstruation, cramping and discomfort can fragment sleep. Factor this into your training expectations. "
        elif phase == 'follicular':
            response += "The Follicular phase normally brings the best sleep of your cycle. If you are sleeping poorly now, look at external stress, caffeine, or screens. "
        response += ("\n\nEvidence-based sleep tips:\n"
                     "- Consistent sleep and wake time even on weekends\n"
                     "- Cool room, especially important in luteal phase\n"
                     "- No screens 30 minutes before bed\n"
                     "- Limit caffeine after 2pm\n"
                     "- Magnesium glycinate 200 to 400mg before bed can significantly help\n\n"
                     + self._pick_follow_up('stress'))
        return response

    def _respond_mood(self, msg):
        phase = self._detect_phase()
        response = ""
        if 'stress' in msg or 'overwhelmed' in msg:
            response = ("Stress is one of the most powerful cycle disruptors. Elevated cortisol directly suppresses the hormones that drive your cycle. "
                        "High stress can delay ovulation by days to weeks.\n\n")
            response += self._pick_follow_up('stress')
        elif 'brain fog' in msg or 'focus' in msg:
            response = ("Brain fog is common in late Luteal phase as estrogen and progesterone both drop. "
                        "It usually lifts within 1 to 2 days of your period starting. "
                        "Staying hydrated, eating regularly, and reducing caffeine paradoxically helps.\n\n")
        elif 'anxious' in msg or 'anxiety' in msg:
            response = ("Cyclical anxiety that worsens in the second half of your cycle is well documented. "
                        "Progesterone metabolites can affect GABA receptors and estrogen drop affects serotonin. "
                        "Tracking which days feel most anxious can help you plan better.\n\n")
        elif 'motivat' in msg:
            response = ("Low motivation is one of the hallmark late-Luteal symptoms. "
                        "A well-executed moderate session beats a sloppy hard one. Consider whether the bravest choice today is to back off.\n\n")
        else:
            response = "Your mood and cycle are closely linked through estrogen and progesterone. Tracking mood daily helps reveal patterns. \n\n"
        if phase:
            response += "In your current " + self.PHASE_INFO[phase]['name'] + " phase: " + self.PHASE_INFO[phase]['mindset'] + "\n\n"
        response += self._pick_follow_up('environment')
        return response

    def _respond_nutrition(self, msg):
        phase = self._detect_phase()
        if phase:
            info = self.PHASE_INFO[phase]
            response = "Nutrition for your " + info['name'] + " phase:\n\n" + info['nutrition'] + "\n\n"
        else:
            response = ("Menstrual: iron-rich foods, magnesium, hydration.\n"
                        "Follicular: lean proteins, complex carbs, lower calorie needs.\n"
                        "Ovulatory: fuel well for peak output, carbs before sessions.\n"
                        "Luteal: 100 to 300 extra calories per day, complex carbs, magnesium for PMS.\n\n")
        if 'craving' in msg:
            response += "Carb and chocolate cravings before your period are driven by real hormonal shifts. Your body needs magnesium and quick energy. Satisfying cravings with nutrient-dense options works better than fighting them.\n\n"
        response += self._pick_follow_up('injury')
        return response

    def _respond_patterns(self):
        patterns = self._detect_patterns()
        if not patterns:
            if not self.entries:
                return ("I do not have enough data yet to spot patterns. Log your journal entries consistently for 1 to 2 weeks and I will start identifying trends.\n\n"
                        + self._pick_follow_up('flow'))
            return ("I am not seeing any concerning patterns in your recent data, which is great. Keep logging consistently and I will flag anything that emerges.\n\n"
                    + self._pick_follow_up('injury'))
        response = "Here is what I am seeing across your recent journal entries:\n\n"
        for p in patterns:
            response += "- " + p.capitalize() + "\n"
        response += ("\n\nSome of these may be cycle-phase related rather than problems. "
                     "The key is whether they repeat on the same cycle days each month.\n\n"
                     + self._pick_follow_up('environment'))
        return response

    def _respond_recovery(self, msg):
        phase = self._detect_phase()
        response = "Recovery and your cycle interact in important ways. "
        if phase:
            info = self.PHASE_INFO[phase]
            response += "\n\nIn your " + info['name'] + " phase: " + info['recovery'] + "\n\n"
        response += ("Universal recovery principles:\n"
                     "- Sleep is the most powerful recovery tool - protect it above everything\n"
                     "- Protein within 30 to 60 minutes post-training accelerates muscle repair\n"
                     "- Active recovery often beats complete rest\n"
                     "- Deload every 4 to 6 weeks prevents accumulated fatigue\n"
                     "- Heat such as sauna or bath reduces soreness and improves recovery\n\n"
                     + self._pick_follow_up('injury'))
        return response

    def _respond_thanks(self):
        options = [
            "Really glad that helped! " + self._pick_follow_up('environment'),
            "Happy to help" + ((", " + self.name) if self.name else "") + ". " + self._pick_follow_up('injury'),
            "Of course, that is what I am here for. " + self._pick_follow_up('flow'),
        ]
        return random.choice(options)

    def _respond_help(self):
        return ("Here is what I can help with:\n\n"
                "Cycle phases - what each phase means for training and recovery\n"
                "Predictions - when your next period is expected\n"
                "Injuries - how injuries interact with your cycle and training\n"
                "Environmental factors - how heat, cold, altitude, and travel affect your cycle\n"
                "Flow tracking - what changes in flow might mean\n"
                "Sleep and recovery - cycle-specific advice\n"
                "Mood and stress - how to track and prepare for mood patterns\n"
                "Nutrition - phase-specific fuelling\n"
                "Pattern spotting - trends in your logged data\n\n"
                "The more you log in your journal, the more personalised and accurate I become. What would you like to explore?")

    def _respond_contextual(self, msg, history):
        if history and len(history) > 1:
            for h in reversed(history[:-1]):
                if h.get('role') == 'assistant':
                    last = h.get('content', '').lower()
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
            response = ("To give you the most useful answer, keep in mind you appear to be in your "
                        + self.PHASE_INFO[phase]['name'] + " phase. That context shapes what is happening in your body.\n\n")
        response += ("Could you tell me a bit more about what you are trying to figure out? "
                     "Is this about training, how you are feeling physically, mood, nutrition, your cycle timing, or something else?\n\n"
                     + self._pick_follow_up('injury'))
        return response
