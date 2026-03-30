# 🌕 Red Moon Recovery

A menstrual cycle tracking platform for athletes — with a free AI guide (Luna) powered by Google Gemini.

## Features
- User accounts with encrypted login — all data saved per user
- Full cycle + performance daily journal
- AI chat with Luna — reads your journal data and profile, has real adaptive conversations
- Conversation history saved and resumable across sessions
- Luna's Insights panel — automatically extracts key patterns from your chats
- Reverse mapping calculator
- Dashboard with trends and entry history

---

## ⚙️ Setup: Adding Your FREE Gemini API Key

The AI chat uses Google Gemini which is **completely free** — no credit card needed.

### Step 1 — Get your free key (2 minutes)
1. Go to **https://aistudio.google.com**
2. Sign in with a Google account
3. Click **"Get API Key"** in the top left
4. Click **"Create API key"**
5. Copy the key (it looks like `AIzaSy...`)

### Step 2 — Add it to GitHub Codespaces
1. Go to your GitHub repository page
2. Click **Settings** → **Secrets and variables** → **Codespaces**
3. Click **"New repository secret"**
4. Name: `GEMINI_API_KEY`
5. Value: paste your key
6. Click **"Add secret"**
7. **Important:** Stop and restart your Codespace after adding the secret so it picks it up

### Step 3 — Verify it's working
In your Codespace terminal, run:
```bash
echo $GEMINI_API_KEY
```
If it prints your key, you're good. If it prints nothing, restart the Codespace.

---

## Running in GitHub Codespaces (Recommended)

1. On the GitHub repo page click the green **"Code"** button
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
GEMINI_API_KEY=your-key-here npm start
```

Open: **http://localhost:3000**

---

## File Structure

```
red-moon-recovery/
├── server.js                    ← Express server + Gemini AI + all routes + database
├── package.json
├── .gitignore
├── README.md
├── .devcontainer/
│   └── devcontainer.json        ← Codespaces auto-start config
└── public/
    └── index.html               ← Full frontend
```

---

## Tech Stack
- **Backend:** Node.js + Express
- **AI:** Google Gemini 2.0 Flash (free tier) via REST API
- **Database:** SQLite via better-sqlite3
- **Auth:** bcryptjs + express-session
- **Frontend:** Vanilla HTML/CSS/JavaScript
