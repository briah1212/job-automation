#!/usr/bin/env python3
"""Poll job-automation API for paused browser submissions, alert via Telegram.

Run as: python3 /home/hermes/.hermes/cron/poll_paused_apps.py

Or better: wire as a Hermes cron job that runs this and Telegram-delivers output.
"""
import json, os, sys, urllib.request, urllib.error

API_BASE = "http://localhost:8001"
API_KEY = os.environ.get("INTERNAL_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

def main():
    # Auth first — get a token
    reg_data = json.dumps({"email": "hermes-monitor@local", "password": "hermes-monitor-pw", "name": "Hermes Monitor"}).encode()
    try:
        req = urllib.request.Request(f"{API_BASE}/api/auth/register", data=reg_data,
            headers={"Content-Type": "application/json"}, method="POST")
        resp = urllib.request.urlopen(req, timeout=10)
        token = json.loads(resp.read())["access_token"]
    except urllib.error.HTTPError as e:
        if e.code == 400:
            # Already registered — login instead
            login_data = json.dumps({"email": "hermes-monitor@local", "password": "hermes-monitor-pw"}).encode()
            req = urllib.request.Request(f"{API_BASE}/api/auth/login", data=login_data,
                headers={"Content-Type": "application/json"}, method="POST")
            resp = urllib.request.urlopen(req, timeout=10)
            token = json.loads(resp.read())["access_token"]
        else:
            print(f"ERROR: Auth failed: {e}")
            return

    # Get all applications, filter for paused ones
    req = urllib.request.Request(f"{API_BASE}/api/applications",
        headers={"Authorization": f"Bearer {token}"})
    resp = urllib.request.urlopen(req, timeout=10)
    apps = json.loads(resp.read())

    paused = [a for a in apps if a.get("pipeline_status") == "waiting_user_input"]
    
    if not paused:
        return  # Silent exit — nothing to report

    # Build alert message
    lines = ["🚨 **Manual intervention needed**\n"]
    for app in paused[:5]:
        aid = app["id"][:8]
        company = app.get("company", "?")
        title = app.get("title", "?")
        reason = app.get("pause_reason", "manual_intervention")
        lines.append(f"• `{aid}` — {title} @ {company}  [{reason}]")
    
    if len(paused) > 5:
        lines.append(f"\n+{len(paused)-5} more")
    
    msg = "\n".join(lines)

    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        tg_data = json.dumps({"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}).encode()
        tg_req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data=tg_data, headers={"Content-Type": "application/json"}, method="POST")
        try:
            urllib.request.urlopen(tg_req, timeout=10)
            print(f"Alert sent: {len(paused)} paused applications")
        except Exception as e:
            print(f"Failed to send Telegram: {e}")
    else:
        print(msg)

if __name__ == "__main__":
    main()
