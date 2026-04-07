# Red Moon Recovery

Menstrual cycle tracking platform for athletes with AI guide, shared calendar, team system, and cycle predictions.

No API keys required. Runs entirely on Python with a built-in SQLite database.

---

## Running in GitHub Codespaces

1. Go to your GitHub repo
2. Click the green Code button
3. Click the Codespaces tab
4. Click Create codespace on main
5. Wait about 60 to 90 seconds for it to install and start
6. A popup says port 3000 is available - click Open in Browser

If no popup appears: click the Ports tab at the bottom of the screen, find port 3000, and click the globe icon.

---

## If the server is not running (502 error)

Open the Codespace terminal and run:

```
pip install -r requirements.txt
python app.py
```

You should see: Starting Red Moon Recovery on port 3000

---

## Running Locally

Requires Python 3.8 or higher from https://nodejs.org

```
git clone https://github.com/YOUR_USERNAME/red-moon-recovery.git
cd red-moon-recovery
pip install -r requirements.txt
python app.py
```

Open http://localhost:3000

---

## Optional: Claude AI Predictions

For enhanced predictions add your Anthropic API key:

1. Go to https://console.anthropic.com and get a free API key
2. In your GitHub repo go to Settings, Secrets and variables, Codespaces
3. Add a secret named ANTHROPIC_API_KEY with your key
4. Restart your Codespace

Without it the built-in Python predictor runs automatically.

---

## File Structure

```
app.py            Main Flask server and all API routes
luna_ai.py        Luna conversational AI engine
predictor.py      Cycle prediction engine with optional Claude
database.py       SQLite database schema and helpers
requirements.txt  Python dependencies
startup.sh        Manual startup script if needed
static/
  index.html      Full frontend application
data/
  redmoon.db      Created automatically on first run
.devcontainer/
  devcontainer.json  Codespaces configuration
```

---

## Features

- Athlete, Coach, and Trainer account types
- Daily journal with injuries, environmental conditions, stress, flow, and symptoms
- Luna AI chatbot that checks yesterday's entry and asks follow-up questions
- Cycle predictions with period date, ovulation estimate, and event phase forecast
- Shared calendar with color-coded events by creator type
- Teams created by coaches with invite codes
- All data saved to SQLite and persists across sessions
