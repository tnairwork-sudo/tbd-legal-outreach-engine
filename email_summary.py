import smtplib
from email.mime.text import MIMEText
from typing import Dict

from apscheduler.schedulers.background import BackgroundScheduler

from database import get_today_summary


def build_summary_body(summary: Dict) -> str:
    log = summary.get("log", {})
    top_targets = summary.get("top_targets", [])
    updates = summary.get("status_updates", [])

    lines = [
        f"Date: {summary.get('date')}",
        "",
        f"Messages sent today: {log.get('targets_contacted', 0)}",
        f"Replies received: {log.get('replies_received', 0)}",
        f"Meetings booked: {log.get('meetings_booked', 0)}",
        "",
        "Status changes (Replied / Meeting Booked):",
    ]
    if updates:
        lines.extend([f"- {u.get('name')} | {u.get('company')} | {u.get('status')}" for u in updates])
    else:
        lines.append("- None")

    lines.append("")
    lines.append("Top 3 new targets discovered:")
    if top_targets:
        lines.extend(
            [
                f"- {t.get('name')} | {t.get('company')} | Fit Score: {t.get('fit_score')}"
                for t in top_targets
            ]
        )
    else:
        lines.append("- None")

    return "\n".join(lines)


def send_daily_summary(db_path: str, smtp_config: Dict) -> None:
    host = smtp_config.get("SMTP_HOST")
    port = int(smtp_config.get("SMTP_PORT", 587))
    user = smtp_config.get("SMTP_USER")
    password = smtp_config.get("SMTP_PASS")

    if not (host and user and password):
        return

    summary = get_today_summary(db_path)
    subject = f"TBD Legal Outreach — Daily Summary [{summary.get('date')}]"
    body = build_summary_body(summary)

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = "tushaar@tnairchambers.in"

    with smtplib.SMTP(host, port, timeout=30) as server:
        server.starttls()
        server.login(user, password)
        server.sendmail(user, ["tushaar@tnairchambers.in"], msg.as_string())


def start_email_scheduler(db_path: str, smtp_config: Dict) -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        send_daily_summary,
        trigger="cron",
        hour=18,
        minute=0,
        kwargs={"db_path": db_path, "smtp_config": smtp_config},
        id="daily_email_summary",
        replace_existing=True,
    )
    scheduler.start()
    return scheduler
