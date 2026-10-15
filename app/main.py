import os
from datetime import datetime, timezone
from typing import Any
from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel
from app.pipeline import process_alert

app = FastAPI(title="Agentic SRE Alert Triage", version="1.0.0")
WEBHOOK_TOKEN = os.getenv("WEBHOOK_TOKEN", "")

class AlertPayload(BaseModel):
    source: str = "manual"
    alert_id: str | None = None
    title: str
    status: str = "firing"
    severity: str = "warning"
    service: str = "unknown"
    environment: str = "unknown"
    message: str = ""
    dedup_key: str | None = None
    labels: dict[str, Any] = {}
    starts_at: str | None = None
    dashboard_url: str | None = None
    runbook_url: str | None = None

@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}

@app.post("/webhook/alert")
async def alert_webhook(payload: AlertPayload, request: Request, x_webhook_token: str | None = Header(default=None)):
    if WEBHOOK_TOKEN and x_webhook_token != WEBHOOK_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid webhook token")
    result = process_alert(payload.model_dump())
    return result

@app.post("/test-alert")
def test_alert():
    sample = {
        "source": "demo", "alert_id": "demo-001",
        "title": "High CPU on checkout-api", "status": "firing",
        "severity": "critical", "service": "checkout-api", "environment": "prod",
        "message": "CPU utilization exceeded 92% for 8 minutes; p95 latency elevated.",
        "dedup_key": "prod:checkout-api:high-cpu",
        "labels": {"cluster": "prod-eks-01", "namespace": "checkout", "team": "payments"},
        "dashboard_url": "https://datadog.example/dashboard/checkout",
        "runbook_url": "https://wiki.example/runbooks/high-cpu"
    }
    return process_alert(sample)
