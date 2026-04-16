# TBD Legal Outreach Engine

TBD Legal Outreach Engine is a browser-based Flask application for discovering, profiling, and managing direct outreach to senior in-house legal leaders at companies with India-linked exposure. It uses SerpAPI for LinkedIn discovery, Claude for psychological profiling plus personalized outreach drafts, SQLite for pipeline tracking, and a dark-mode dashboard for daily execution control with a 150-contact/day outreach cap.

## Setup

```bash
git clone https://github.com/tnairwork-sudo/tbd-legal-outreach-engine
cd tbd-legal-outreach-engine
python3 -m pip install -r requirements.txt
cp .env.example .env
python3 app.py
```

Then edit `.env` with your keys and SMTP credentials.

## SerpAPI Key

1. Create/login account at [https://serpapi.com](https://serpapi.com)
2. Copy your API key from dashboard
3. Set `SERP_API_KEY` in `.env`

## Anthropic API Key

1. Create/login at [https://console.anthropic.com](https://console.anthropic.com)
2. Generate API key
3. Set `ANTHROPIC_API_KEY` in `.env`

## Gmail App Password for Daily Summary

1. Enable 2-Step Verification on your Google account
2. Open Google Account settings → Security → App passwords
3. Create an app password for Mail
4. Set:
   - `SMTP_HOST=smtp.gmail.com`
   - `SMTP_PORT=587`
   - `SMTP_USER=<your gmail>`
   - `SMTP_PASS=<app password>`

## Daily Workflow

1. Click **Run Discovery** to pull LinkedIn targets from SerpAPI in the background.
2. Add manual prospects via **Manual Target Entry** and upload lists via **Batch CSV Upload**.
3. Click **Generate** for any target that needs profile + messages.
4. Review score, driver, and intelligence hook in the table.
5. Click **View Messages** and use **Copy** for channel-specific text.
6. Click **Send** to open LinkedIn and mark the target as Contacted.
7. Keep daily outreach under the visible **150/day** counter.
8. Use **Export CSV** for full pipeline snapshot.

## Voice Guidelines Reminder

- Never mention TBD or The Big Dinner in outreach messages.
- Open with psychological condition, not job title.
- End every message with: `Tushaar Nair, Advocate, Supreme Court of India, T Nair Chambers`.
- Never use em dashes.
- Never use the word `networking`.

## Notes

- Claude model used for all AI generation: `claude-sonnet-4-20250514`.
- `/api/run-discovery` runs in a background thread to keep UI responsive.
- Daily email summary is scheduled with APScheduler for 18:00 local server time.
