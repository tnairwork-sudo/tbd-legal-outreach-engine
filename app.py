import csv
import io
import os
import threading
from datetime import datetime
from typing import Dict, List

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, send_file

from database import (
    DB_PATH,
    export_rows,
    get_messages_for_target,
    get_target,
    get_today_contacted_count,
    increment_daily,
    init_db,
    insert_target,
    list_targets,
    mark_contacted,
    replace_messages,
    update_profile,
    update_status,
    upsert_discovered_target,
)
from email_summary import start_email_scheduler
from message_gen import generate_messages
from profiler import profile_target
from serpapi_search import discover_targets

load_dotenv()

app = Flask(__name__)

DAILY_CONTACT_LIMIT = 150
DB_FILE = os.getenv("DB_PATH", DB_PATH)
SMTP_CONFIG = {
    "SMTP_HOST": os.getenv("SMTP_HOST"),
    "SMTP_PORT": os.getenv("SMTP_PORT", "587"),
    "SMTP_USER": os.getenv("SMTP_USER"),
    "SMTP_PASS": os.getenv("SMTP_PASS"),
    "SMTP_TO_EMAIL": os.getenv("SMTP_TO_EMAIL", "tushaar@tnairchambers.in"),
}

init_db(DB_FILE)
scheduler = start_email_scheduler(DB_FILE, SMTP_CONFIG)

def _process_target(target_id: int) -> Dict:
    target = get_target(target_id, DB_FILE)
    if not target:
        return {"error": "Target not found"}

    profile = profile_target(target, os.getenv("ANTHROPIC_API_KEY", ""))
    update_profile(target_id, profile, DB_FILE)

    # Always generate messages regardless of fit score
    messages = generate_messages(target, profile, os.getenv("ANTHROPIC_API_KEY", ""))
    replace_messages(target_id, messages, DB_FILE)
    return {"qualified": True, "fit_score": profile.get("fit_score", 0)}

def _run_discovery_thread() -> None:
    api_key = os.getenv("SERP_API_KEY", "")
    discovered = discover_targets(api_key)
    inserted = 0
    for target in discovered:
        row_id = upsert_discovered_target(target, DB_FILE)
        if row_id:
            inserted += 1
    if inserted:
        increment_daily("targets_discovered", inserted, DB_FILE)


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/targets", methods=["GET"])
def api_targets():
    return jsonify(list_targets(DB_FILE))

@app.route("/api/messages/<int:target_id>", methods=["GET"])
def api_messages(target_id: int):
    return jsonify(get_messages_for_target(target_id, DB_FILE))

@app.route("/api/run-discovery", methods=["POST"])
def api_run_discovery():
    thread = threading.Thread(target=_run_discovery_thread, daemon=True)
    thread.start()
    return jsonify({"status": "started"})

@app.route("/api/generate/<int:target_id>", methods=["POST"])
def api_generate(target_id: int):
    result = _process_target(target_id)
    if "error" in result:
        return jsonify(result), 404
    return jsonify(result)

@app.route("/api/add-target", methods=["POST"])
def api_add_target():
    payload = request.get_json(silent=True) or request.form.to_dict()
    required = ["name", "company", "role", "location"]
    if not all(payload.get(field) for field in required):
        return jsonify({"error": "name, company, role, location are required"}), 400

    target_id = insert_target(
        {
            "name": payload.get("name"),
            "company": payload.get("company"),
            "role": payload.get("role"),
            "location": payload.get("location"),
            "industry": payload.get("industry", ""),
            "email": payload.get("email", ""),
            "linkedin_url": payload.get("linkedin_url", ""),
            "source": payload.get("source", "manual"),
            "created_at": datetime.utcnow().isoformat(),
        },
        DB_FILE,
    )
    increment_daily("targets_discovered", 1, DB_FILE)
    _process_target(target_id)
    return jsonify({"id": target_id, "status": "created"})

@app.route("/api/upload-csv", methods=["POST"])
def api_upload_csv():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "CSV file is required"}), 400

    content = file.read().decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(content))
    inserted_ids: List[int] = []
    for row in reader:
        target_id = insert_target(
            {
                "name": row.get("name", "").strip(),
                "company": row.get("company", "").strip(),
                "role": row.get("role", "").strip(),
                "location": row.get("location", "").strip(),
                "industry": row.get("industry", "").strip(),
                "email": row.get("email", "").strip(),
                "linkedin_url": row.get("linkedin_url", "").strip(),
                "source": "csv",
            },
            DB_FILE,
        )
        inserted_ids.append(target_id)

    if inserted_ids:
        increment_daily("targets_discovered", len(inserted_ids), DB_FILE)

    def profile_batch() -> None:
        for target_id in inserted_ids:
            _process_target(target_id)

    threading.Thread(target=profile_batch, daemon=True).start()

    return jsonify({"inserted": len(inserted_ids)})

@app.route("/api/send/<int:target_id>", methods=["POST"])
def api_send(target_id: int):
    today_count = get_today_contacted_count(DB_FILE)
    if today_count >= DAILY_CONTACT_LIMIT:
        return jsonify({"error": "Daily outreach limit reached", "limit": DAILY_CONTACT_LIMIT}), 429

    target = get_target(target_id, DB_FILE)
    if not target:
        return jsonify({"error": "Target not found"}), 404

    if target.get("status") != "Contacted":
        mark_contacted(target_id, DB_FILE)
        increment_daily("targets_contacted", 1, DB_FILE)

    return jsonify({"linkedin_url": target.get("linkedin_url", ""), "status": "Contacted"})

@app.route("/api/update-status/<int:target_id>", methods=["POST"])
def api_update_status(target_id: int):
    payload = request.get_json(silent=True) or {}
    status = payload.get("status")
    allowed = {"Pending", "Contacted", "Replied", "Meeting Booked", "Retained"}
    if status not in allowed:
        return jsonify({"error": "Invalid status"}), 400

    update_status(target_id, status, DB_FILE)
    if status == "Replied":
        increment_daily("replies_received", 1, DB_FILE)
    elif status == "Meeting Booked":
        increment_daily("meetings_booked", 1, DB_FILE)

    return jsonify({"status": status})

@app.route("/api/daily-count", methods=["GET"])
def api_daily_count():
    count = get_today_contacted_count(DB_FILE)
    return jsonify(
        {
            "count": count,
            "limit": DAILY_CONTACT_LIMIT,
            "warning": count >= 130,
        }
    )

@app.route("/api/export", methods=["GET"])
def api_export():
    rows = export_rows(DB_FILE)
    output = io.StringIO()
    fieldnames = [
        "id",
        "name",
        "company",
        "role",
        "location",
        "industry",
        "linkedin_url",
        "email",
        "inner_condition",
        "decision_driver",
        "intelligence_hook",
        "fit_score",
        "status",
        "created_at",
        "contacted_at",
        "source",
        "connection_message",
        "followup_message",
        "email_message",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    mem = io.BytesIO(output.getvalue().encode("utf-8"))
    mem.seek(0)
    filename = f"tbd_outreach_export_{datetime.utcnow().date().isoformat()}.csv"
    return send_file(mem, mimetype="text/csv", as_attachment=True, download_name=filename)

if __name__ == '__main__':
    import time
    import webbrowser

    def open_browser():
        time.sleep(1.5)
        try:
            webbrowser.get('chrome').open('http://127.0.0.1:5000')
        except Exception:
            webbrowser.open('http://127.0.0.1:5000')

    threading.Thread(target=open_browser, daemon=True).start()
    app.run(debug=False, port=5000)