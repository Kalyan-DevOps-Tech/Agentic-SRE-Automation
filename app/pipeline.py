import hashlib
import json
import os
from datetime import datetime, timezone
from app.store import seen_recently, record_alert
from app.triage import triage_alert
from app.emailer import send_email
from app.actions import run_read_only_checks

COOLDOWN_SECONDS = int(os.getenv("ALERT_COOLDOWN_SECONDS", "900"))
EMAIL_TO = os.getenv("ALERT_EMAIL_TO", "")

def process_alert(alert: dict) -> dict:
    status = str(alert.get("status", "firing")).lower()
    raw_key = alert.get("dedup_key") or "|".join([
        str(alert.get("environment", "unknown")),
        str(alert.get("service", "unknown")),
        str(alert.get("title", "unknown")).lower()
    ])
    key = hashlib.sha256(raw_key.encode()).hexdigest()

    if status in ("resolved", "ok", "recovered"):
        record_alert(alert, "resolved", "Alert recovered; no incident email sent by default.", dedup_key=key)
        return {"accepted": True, "action": "resolved_recorded", "notified": False}

    if seen_recently(key, COOLDOWN_SECONDS):
        record_alert(alert, "suppressed_duplicate", "Duplicate alert suppressed during cooldown.", dedup_key=key)
        return {"accepted": True, "action": "duplicate_suppressed", "notified": False}

    # The agent gathers evidence with read-only checks before triage.
    checks = run_read_only_checks(alert)
    analysis = triage_alert(alert, checks)
    incident = {
        "received_at": datetime.now(timezone.utc).isoformat(),
        "alert": alert,
        "checks": checks,
        "analysis": analysis,
        "guardrails": [
            "No production changes were executed.",
            "Any remediation must be reviewed and approved by an authorized engineer."
        ]
    }
    sent = send_email(
        subject=f"[SRE {alert.get('severity','warning').upper()}] {alert.get('service','unknown')}: {alert.get('title','Alert')}",
        body=json.dumps(incident, indent=2, ensure_ascii=False),
        recipients=EMAIL_TO
    )
    record_alert(alert, "notified" if sent else "triaged_email_not_configured", analysis.get("summary", ""), dedup_key=key)
    return {"accepted": True, "action": "triaged", "notified": sent, "dedup_key_hash": key, "analysis": analysis}
