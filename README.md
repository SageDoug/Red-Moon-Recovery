# Red Moon Recovery

Menstrual cycle tracking app for athletes with a free AI guide (Luna) powered by Google Gemini.

---

## Setup: Free Gemini API Key (required for AI chat)

1. Go to https://aistudio.google.com
2. Sign in with a Google account
3. Click "Get API Key" then "Create API key"
4. Copy the key

### Add it to GitHub Codespaces
1. Go to your GitHub repo
2. Click Settings, then Secrets and variables, then Codespaces
3. Click "New repository secret"
4. Name: GEMINI_API_KEY
5. Value: paste your key
6. Save, then stop and restart your Codespace

### Verify it loaded
In your Codespace terminal run:
```
echo $GEMINI_API_KEY
```
If it prints your key you are good to go.

---

## Running in Codespaces

1. Click the green Code button on the repo
2. Click Codespaces tab
3. Click "Create codespace on main"
4. Wait about 60 seconds for it to install and start
5. Click Open in Browser when port 3000 popup appears

---

## Running Locally

Requires Node.js 18 or higher from https://nodejs.org

```
git clone https://github.com/YOUR_USERNAME/red-moon-recovery.git
cd red-moon-recovery
npm install
GEMINI_API_KEY=your-key-here node server.js
```

Open http://localhost:3000

---

## File Structure

```
red-moon-recovery/
  server.js              - Express server, database, Gemini AI chat
  package.json           - Dependencies
  .gitignore
  README.md
  .devcontainer/
    devcontainer.json    - Codespaces auto-start config
  public/
    index.html           - Full frontend
```

## Tech Stack
- Node.js and Express for the server
- Google Gemini 2.0 Flash for AI (free)
- SQLite via better-sqlite3 for the database
- bcryptjs and express-session for login
- Vanilla HTML, CSS, JavaScript for the frontend
