# InternMind AI — Autonomous Internship Workflow (working MVP)

Client context: Thozhil (`https://thozhil.co.in/`). This project provides an autonomous enrollment workflow that starts from a student CSV and then creates per-intern task chains, sends task invitations, prepares private AI interview rooms, optionally creates Google Calendar/Meet events, accepts submissions without requiring an intern account login, evaluates the AI interview, and either allocates the next dependent task or starts a correction/re-review cycle.

> **Important accuracy note:** This is an autonomous workflow MVP, not a security-reviewed production system. Real Gmail delivery requires SMTP credentials; real Google Meet links require one-time Google Calendar OAuth setup. The AI avatar interview currently runs in the InternMind browser room. Calendar API can create a Meet link, but it does not make the AI avatar join and speak inside a standard Google Meet call. If the requirement is specifically “AI avatar joins the Google Meet call”, that requires a separate supported real-time meeting-agent integration and is not implemented by this package.

## What is now automated

- `GET /autonomous/status` reports whether SMTP and Google Calendar/Meet configuration is present.
- `POST /autonomous/enroll-csv` accepts student details (`name,email`, optional `skills`). It creates/reuses the Thozhil autonomous project, creates a three-stage dependent task chain per student, assigns the first stage, creates a private AI interview room, attempts to schedule a Calendar/Meet event, and sends an email invitation.
- Public task submission link: students can submit a GitHub/repository URL, notes, and evidence through `/task-submit.html` without an intern account. The invite token protects the link.
- After submission, the student uses the private browser interview link. In autonomous mode, finishing the interview requires a submission to exist.
- If the interview evaluation passes, the next dependent task is assigned to the same intern, a new interview/submission link is created, and the student is emailed.
- If the evaluation requests corrections, the system creates a correction cycle, schedules a new review date, creates fresh submission/interview links, and emails feedback. When configured, it attempts to create a Meet event for the review.
- Optional Ollama local model evaluation; deterministic heuristic fallback if unavailable.
- CSV enrollment UI at `http://localhost:5173/autonomous.html`.

## Requirements

- Windows 10/11
- Python 3.11+ recommended
- Node.js 20+ and npm
- Chrome or Edge recommended for browser speech features
- Internet access for Gmail SMTP and Google Calendar API

## Windows quick start

Extract the ZIP. Open PowerShell in the project root—the folder containing `requirements.txt`.

### 1. Configure the environment

```powershell
Copy-Item .env.example .env
notepad .env
```

Generate a secret in another PowerShell command:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Copy that value into `SECRET_KEY`. Change `ADMIN_PASSWORD` before using the app. Keep `.env`, `credentials.json`, and `token.json` private; never commit them to GitHub.

### 2. Backend

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Keep this terminal open. Backend API docs: `http://127.0.0.1:8000/docs`.

If PowerShell blocks environment activation, run this for the current terminal only:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### 3. Frontend

Open a second PowerShell window:

```powershell
cd "FULL_PATH_TO\InternMind_AI_Complete_Project\frontend"
npm install
npm run dev
```

Open the Vite URL, usually `http://localhost:5173`.

### 4. Log in and enroll students

1. Open `http://localhost:5173` and log in with the admin credentials set in `.env`.
2. Open `http://localhost:5173/autonomous.html`.
3. Sign in there using the same admin email/password.
4. Upload a CSV with headers:

```csv
name,email,skills
Sankar,1212sankar1212@gmail.com,Python; SQL; GitHub
```

5. Click **Start autonomous enrollment**. The response lists created tasks, review dates, interview URLs, and whether a real Meet link was created.

For existing records, an intern with an active task in the same autonomous project is skipped to avoid duplicate assignments. Use a new CSV row/email or complete the active task before trying again.

## Gmail delivery setup

In `.env`, configure:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-gmail@gmail.com
SMTP_PASSWORD=your-new-16-character-gmail-app-password
SMTP_FROM=your-gmail@gmail.com
```

Use a Gmail App Password where Google supports it; do not use your normal Google password. If you have previously exposed an App Password in chat, revoke it and generate a new one. Restart the backend after changing `.env`.

If SMTP is not configured, the backend prints `[EMAIL PREVIEW]` and no email is delivered. `SENT` means the SMTP server accepted the message; it does not guarantee Inbox delivery. Check backend logs, Gmail Sent, Inbox, Spam, and the `notices` records if needed.

## Automatic Google Meet link setup (one-time OAuth)

Google Calendar OAuth setup is needed once before the app can create real Meet links:

1. In Google Cloud Console, create/select a project.
2. Enable **Google Calendar API**.
3. Configure the OAuth consent screen for your use case.
4. Create an OAuth Client ID of type **Desktop app** and download its JSON file as `credentials.json` into the project root. Keep it private.
5. In `.env`, set:

```env
GOOGLE_CALENDAR_ENABLED=true
GOOGLE_CALENDAR_CREDENTIALS=credentials.json
GOOGLE_CALENDAR_TOKEN=token.json
GOOGLE_CALENDAR_ID=primary
```

6. With the Python virtual environment active, run once:

```powershell
python .\scripts\google_calendar_setup.py
```

A browser opens for Google authorization. After success, a private `token.json` is saved. Restart the backend and open `/autonomous.html`, then click **Check configuration**. When configured, the system attempts to create a Calendar event with a Google Meet link and email the attendee.

Google OAuth can be in testing mode and may restrict which Google accounts can authorize it. Configure the consent screen and test users appropriately. Do not upload credentials or tokens to a public repository.

## Deploying for students outside your laptop

`APP_PUBLIC_URL=http://localhost:5173` works only on your own computer. Students cannot open your local localhost links from their devices. For real remote students, deploy the frontend and backend to HTTPS hosting, set `APP_PUBLIC_URL` to the public frontend URL, update `FRONTEND_ORIGINS`, and use a persistent database and secure secrets. The API URL for the frontend can be set in `frontend/.env` as `VITE_API_URL=https://your-api-domain.example`. Do not use placeholder domains in production.

## Optional local AI evaluation (free, runs locally)

1. Install Ollama and download a suitable model, for example `llama3.2`.
2. Set these in `.env`:

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
```

3. Restart FastAPI. If Ollama is unavailable, the interview uses a deterministic fallback heuristic.

## How the automatic cycle works

1. Upload student CSV once.
2. System creates a project and three dependent tasks for each student.
3. Stage 1 is assigned automatically with deadline, submission link, interview link, and scheduled review date.
4. Student submits evidence through the private submission page.
5. Student completes the browser-based AI interview.
6. A passing result approves the task and assigns the next stage to the same student.
7. A non-passing result creates a correction cycle and new links/review date.
8. The cycle repeats until all three stages are approved.

## Important limitations

- The voice/avatar interview runs in the InternMind website, not inside Google Meet. Calendar event creation and AI participation in a Meet call are separate capabilities.
- AI evaluation is not proof of code correctness or authorship. This MVP does not execute submitted code in a hardened sandbox; it uses interview answers and submission evidence. Add isolated test execution and repository analysis before trusting automatic pass/fail decisions for real placements.
- Browser speech recognition support varies. Text input is available as a fallback.
- Invite URLs are bearer tokens. Keep them private. The MVP has a 45-day check for submission links but does not include a complete token revocation dashboard.
- A local SQLite database is suitable for development only. For production, use PostgreSQL, HTTPS, rate limiting, background workers, audit/monitoring, backup and restore, stronger user activation, data retention, and security review.
- Get appropriate consent and comply with applicable privacy and employment rules before processing student information.

## Useful endpoints

- `GET /health`
- `GET /autonomous/status`
- `POST /autonomous/enroll-csv` (admin/mentor bearer token)
- `POST /autonomous/tasks/{task_id}/submit?join_token=...`
- `GET /interviews/{id}/public?join_token=...`
- `POST /interviews/{id}/answer?join_token=...`
- `POST /interviews/{id}/finish?join_token=...`
- `GET /docs`
