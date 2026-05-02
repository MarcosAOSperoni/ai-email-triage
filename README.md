# AI Email Triage

A self-hosted AI-powered email triage system that reads your Gmail inbox on a schedule, classifies every email, drafts suggested replies for important ones, and delivers a summary to your inbox. Runs entirely on a home lab — no third-party cloud services involved.

---

## How It Works

At 8am, 11am, 2pm, 5pm, and 8pm the system:

1. **Fetches** all emails received since the last run via the Gmail API
2. **Classifies** each email using a local LLM (Ollama) into one of four categories:
   - `important` — requires a response
   - `informational` — good to know, no reply needed
   - `newsletter` — bulk or marketing content
   - `spam` — junk
3. **Drafts a reply** for every email classified as important
4. **Sends an HTML summary email** to your inbox listing the important emails and their suggested replies

---

## Infrastructure

| Component | Host |
|---|---|
| Docker app + PostgreSQL | Ubuntu Server VM on pve2 |
| Ollama LLM server | Mac Studio M4 Max |
| Gmail API | Google Cloud | — |

The Mac Studio runs `llama3:70b` (40GB) fully in unified memory at ~120 tokens/sec. pve2 is a VM on a Proxmox cluster running Docker Compose.

---

## Architecture

```
Gmail API
    │
    ▼
Email Fetcher (pve2)
    │  fetches since last run, deduplicates via message_id
    ▼
Ollama — llama3:70b (Mac Studio on local network)
    │  classify → { classification, reason }
    │  draft reply for important emails
    ▼
PostgreSQL (pve2)
    │  stores emails + classifications + drafts
    ▼
Summary Email (SMTP → Gmail)
    │  HTML email listing important emails + suggested replies
    ▼
Your Inbox
```

---

## Tech Stack

| Layer | Tool |
|---|---|
| Language | Python 3.12 |
| LLM | Ollama — llama3:70b |
| Gmail | Gmail API (OAuth2) |
| Scheduler | APScheduler |
| Database | PostgreSQL 16 |
| ORM | SQLAlchemy 2.0 (async) |
| HTTP client | httpx |
| Email delivery | aiosmtplib |
| Containerization | Docker Compose |

---

## Project Structure

```
ai-email-triage/
├── app/
│   ├── config.py          # All settings via pydantic-settings + .env
│   ├── main.py            # Entry point — starts APScheduler
│   ├── pipeline.py        # Orchestrates fetch → classify → draft → store → email
│   ├── summary.py         # HTML summary email builder + sender
│   ├── gmail/
│   │   ├── auth.py        # OAuth2 flow, saves token.json
│   │   └── fetch.py       # Gmail API — fetches emails since last check
│   ├── llm/
│   │   ├── classify.py    # POST to Ollama /api/chat, returns JSON classification
│   │   └── draft.py       # POST to Ollama /api/chat, returns reply draft
│   └── db/
│       ├── models.py      # SQLAlchemy models — Email, Preference
│       └── session.py     # Async engine + session factory
├── run_once.py            # Run a single triage pass immediately (for testing)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── .gitignore
```

---

## Database Schema

### emails
| Column | Type | Description |
|---|---|---|
| id | UUID | Primary key |
| provider | string | `gmail` |
| message_id | string | Gmail message ID (unique, deduplicates) |
| subject | string | Email subject |
| sender | string | Sender address |
| received_at | timestamptz | When the email was received |
| body | text | Email body (trimmed to 4000 chars) |
| classification | string | `important` / `informational` / `newsletter` / `spam` |
| classification_reason | text | One-sentence reason from the LLM |
| suggested_reply | text | LLM-drafted reply (important emails only) |
| status | string | `pending` / `approved` / `dismissed` |
| created_at | timestamptz | When it was triaged |

### preferences
Stores learned user preferences (sender, topic, tone) used to refine future classifications.

---

## Setup

### Prerequisites
- Ollama running on a machine with enough RAM for `llama3:70b` (~40GB)
- Docker + Docker Compose on the deployment host
- A Google Cloud project with the Gmail API enabled

### 1. Google Cloud — Gmail OAuth credentials
1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a project → enable the **Gmail API**
3. **OAuth consent screen** → External → add your Gmail as a test user
4. **Credentials** → Create OAuth client ID → Desktop app
5. Copy the Client ID and Client Secret

### 2. Gmail App Password (for SMTP)
1. Go to [myaccount.google.com](https://myaccount.google.com) → Security → App passwords
2. Create a password named `email-triage`
3. Copy the 16-character password

### 3. Ollama
```bash
# Install
brew install ollama          # macOS
# or
curl -fsSL https://ollama.com/install.sh | sh   # Linux

# Pull the model (~40GB)
ollama pull llama3:70b

# Serve on all interfaces so other machines can reach it
OLLAMA_HOST=0.0.0.0 ollama serve
```

### 4. First run — authorize Gmail
On the machine where you'll run the app for the first time:

```bash
git clone <repo>
cd ai-email-triage
cp .env.example .env
# fill in .env with your credentials
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python run_once.py
```

A browser window will open asking you to authorize Gmail access. After approval, `token.json` is saved. The first triage run will process the last 24 hours of email and log results to the console (or send a summary email if SMTP is configured).

### 5. Deploy with Docker Compose
```bash
# Copy project + credentials to the server
scp -r ai-email-triage/ user@server:~/
scp token.json user@server:~/ai-email-triage/

# On the server
cd ai-email-triage
docker compose up -d
docker compose logs app -f
```

---

## Environment Variables

| Variable | Description |
|---|---|
| `GMAIL_CLIENT_ID` | OAuth2 client ID from Google Cloud |
| `GMAIL_CLIENT_SECRET` | OAuth2 client secret |
| `GMAIL_TOKEN_FILE` | Path to saved OAuth token (default: `token.json`) |
| `OLLAMA_HOST` | Ollama server URL (default: `http://localhost:11434`) |
| `OLLAMA_MODEL` | Model name (default: `llama3:70b`) |
| `POSTGRES_PASSWORD` | PostgreSQL password |
| `POSTGRES_URL` | Full database connection string |
| `SUMMARY_EMAIL_TO` | Where to send the summary |
| `SUMMARY_EMAIL_FROM` | Sender address |
| `SMTP_HOST` | SMTP server (e.g. `smtp.gmail.com`) |
| `SMTP_PORT` | SMTP port (default: `587`) |
| `SMTP_USER` | SMTP username |
| `SMTP_PASSWORD` | Gmail app password |
| `SCHEDULE_TIMES` | Comma-separated run times (default: `08:00,11:00,14:00,17:00,20:00`) |

---

## LLM Prompts

### Classification
The LLM receives the sender, subject, and body and returns structured JSON:
```json
{"classification": "important", "reason": "Rent payment reminder requiring action"}
```

### Reply Draft
The LLM drafts a concise reply under 150 words based on the email context and any learned writing style preferences.

---

## Portfolio Value
- Full-stack Python (async FastAPI-ready, SQLAlchemy, APScheduler)
- Practical LLM integration with local inference (no API costs)
- Self-hosted on Proxmox — no cloud dependency
- OAuth2, SMTP, Gmail API integration
- Docker Compose production deployment
