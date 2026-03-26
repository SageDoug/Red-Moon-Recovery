# 🌕 Red Moon Recovery

A menstrual cycle tracking platform for athletes — with a real AI guide (Luna) powered by Claude.

## Features
- User accounts with encrypted login — all data saved per user
- Full cycle + performance daily journal
- AI chat with Luna — she reads your journal data and profile and has real conversations
- Conversation history saved and resumable across sessions
- Luna's Insights panel — automatically extracts key patterns from your chats
- Reverse mapping calculator
- Dashboard with trends and entry history

---

## ⚙️ Setup: Adding Your Anthropic API Key

The AI chat requires an Anthropic API key. Without it, the rest of the app works fine but Luna won't respond.

### Get a free API key
1. Go to https://console.anthropic.com
2. Sign up / sign in
3. Go to **API Keys** → click **Create Key**
4. Copy the key (starts with `sk-ant-...`)

### Add it in GitHub Codespaces
1. In your GitHub repo, go to **Settings → Secrets and variables → Codespaces**
2. Click **New repository secret**
3. Name: `ANTHROPIC_API_KEY`
4. Value: paste your key
5. Click **Add secret**
6. Next time you open a Codespace, the key will be available automatically

### Add it for local development
Create a file called `.env` in the root of the project:
```
ANTHROPIC_API_KEY=sk-ant-your-key-here
```
Then install dotenv: `npm install dotenv`
And add this line to the very top of `server.js`:
```js
require('dotenv').config();
```

---

## Running in GitHub Codespaces (Recommended)

1. On the GitHub repo page, click the green **"Code"** button
2. Click the **"Codespaces"** tab
3. Click **"Create codespace on main"**
4. Wait ~60 seconds — it automatically runs `npm install` and starts the server
5. A popup appears saying port 3000 is open → click **Open in Browser**

---

## Running Locally

### Prerequisites
- Node.js 18+ (https://nodejs.org)

```bash
git clone https://github.com/YOUR_USERNAME/red-moon-recovery.git
cd red-moon-recovery
npm install
npm start
```

Open: **http://localhost:3000**

---

## File Structure

```
red-moon-recovery/
├── server.js                    ← Express server + API routes + AI chat + database
├── package.json
├── .gitignore                   ← Excludes node_modules, database, .env
├── README.md
├── .devcontainer/
│   └── devcontainer.json        ← Codespaces auto-start config
└── public/
    └── index.html               ← Full frontend (HTML + CSS + JS)
```

The SQLite database is created automatically at `data/redmoon.db` on first run.

---

## Tech Stack
- **Backend:** Node.js + Express
- **AI:** Anthropic Claude (claude-sonnet-4-20250514) via REST API
- **Database:** SQLite via better-sqlite3
- **Auth:** bcryptjs + express-session
- **Frontend:** Vanilla HTML/CSS/JavaScript
