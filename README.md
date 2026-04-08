# Red Moon Recovery

Multi-language cycle tracking platform for athletes.

## Language Stack

| Language | Role |
|----------|------|
| Python + Flask | Web server, routing, auth, database access |
| Java | Cycle phase calculation, period prediction, ovulation estimation, event phase forecasting |
| C++ | Pattern analysis engine - detects overtraining, injury trends, sleep patterns |
| HTML + CSS + JavaScript | Full frontend application |
| SQLite | Persistent data storage for all users |

---

## Running in GitHub Codespaces

1. Go to your GitHub repo
2. Click the green Code button, then Codespaces tab
3. Click Create codespace on main
4. Wait about 2 minutes (installs Java, g++, Python deps, compiles Java and C++)
5. Click Open in Browser when port 3000 popup appears

The `postCreateCommand` in devcontainer.json handles everything automatically.

---

## If you get a 502 error

Open the terminal in your Codespace and run:

```bash
sudo apt-get install -y default-jdk g++
pip install -r requirements.txt
cd java && javac CycleEngine.java && cd ..
cd cpp && g++ -o pattern_analyzer pattern_analyzer.cpp -std=c++17 && cd ..
python app.py
```

---

## Running Locally

Requires Python 3.8+, Java JDK 11+, and g++.

```bash
pip install -r requirements.txt
cd java && javac CycleEngine.java && cd ..
cd cpp && g++ -o pattern_analyzer pattern_analyzer.cpp -std=c++17 && cd ..
python app.py
```

---

## File Structure

```
app.py                    Python Flask server and all API routes
database.py               SQLite schema (CURRENT_TIMESTAMP, not datetime("now"))
engines.py                Python bridge calling Java and C++ via subprocess
luna_ai.py                Luna conversational AI engine (Python)
requirements.txt
java/
  CycleEngine.java        Period prediction, ovulation, event phase calculation
cpp/
  pattern_analyzer.cpp    Pattern detection - sleep, stress, injury, overtraining
static/
  index.html              Full frontend (HTML + CSS + JavaScript)
data/
  redmoon.db              Created automatically on first run
.devcontainer/
  devcontainer.json       Installs Java + g++ then compiles and starts server
```

---

## Optional: Claude Enhanced Predictions

Add `ANTHROPIC_API_KEY` as a Codespace secret for Claude-assisted predictions on top of the Java engine.
