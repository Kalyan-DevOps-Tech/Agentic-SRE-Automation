# Agentic SRE Alert Triage and Email Automation

A Git-ready starter project for reducing noisy SRE alerts. It receives alerts from a monitoring platform, suppresses repeated notifications during a cooldown window, gathers optional read-only evidence, performs rule-based or optional LLM-assisted triage, and sends a structured email to the on-call team.

> Safety boundary: this project does **not** restart pods, scale workloads, roll back releases, delete files, or make production changes automatically. It recommends runbook steps and notifies humans. Add any remediation only behind explicit approval, authorization, audit logging, and a tested rollback plan.

## Real-world scenario

A production `checkout-api` deployment starts reporting CPU above 90%, increasing p95 latency, and repeated alerts from Datadog or Prometheus. Rather than emailing the team for every repeat:
1. Alert webhook receives the event.
2. Deduplication uses the supplied `dedup_key` (or environment + service + title) and suppresses repeats for 15 minutes.
3. Evidence collection optionally runs read-only Kubernetes checks (`kubectl get pods` and `kubectl get events`).
4. Triage classifies the alert using rules, or an optional LLM generates a cautious summary and suggested diagnostic steps.
5. Email includes severity, service, environment, evidence, likely causes, next steps, dashboard/runbook links, and safety guardrails.
6. An engineer validates telemetry and decides whether to scale, roll back, or follow another approved runbook.

## Multiple automations in this project

- **Automation 1 — Alert normalization:** accept a common JSON payload from alert sources.
- **Automation 2 — Deduplication/cooldown:** suppress repeated notifications for the same issue.
- **Automation 3 — Basic correlation/triage:** map CPU, memory/OOM, latency, and disk alerts to diagnostic checklists.
- **Automation 4 — Read-only evidence gathering:** optionally capture Kubernetes pod and event information.
- **Automation 5 — AI-assisted analysis:** optional OpenAI-based JSON triage; rule-based fallback works without an API key.
- **Automation 6 — Email notification:** send one structured incident email to the configured recipients.
- **Automation 7 — Audit trail:** record alert outcomes in SQLite so repeated alerts can be suppressed.

This is a practical starter, not a full autonomous incident-management platform. The included correlation is deduplication by key; richer cross-alert correlation can be added using service, cluster, time window, and shared trace/deployment identifiers.

## Architecture

```text
Datadog / Prometheus Alertmanager
              |
              v
       POST /webhook/alert
              |
       Validate webhook token
              |
       Normalize + deduplicate
              |
       Optional read-only checks
              |
       Rule-based / optional LLM triage
              |
       SQLite audit record + SMTP email
              |
              v
        SRE / on-call team
```

## Requirements

- Docker + Docker Compose, or Python 3.12+
- An SMTP relay or mail provider approved by your organization
- Optional: OpenAI API key for LLM-assisted triage
- Optional: `kubectl` and a least-privilege, read-only kubeconfig if enabling Kubernetes evidence collection

## Run locally

```bash
cp .env.example .env
# Edit .env and set WEBHOOK_TOKEN, SMTP settings and ALERT_EMAIL_TO.
docker compose up --build -d
curl http://localhost:8000/health
```

Send a demo alert:

```bash
curl -X POST http://localhost:8000/test-alert
```

Send a webhook alert:

```bash
curl -X POST http://localhost:8000/webhook/alert \
  -H 'Content-Type: application/json' \
  -H 'X-Webhook-Token: replace-with-a-long-random-secret' \
  -d '{
    "source":"manual",
    "alert_id":"cpu-001",
    "title":"High CPU on checkout-api",
    "status":"firing",
    "severity":"critical",
    "service":"checkout-api",
    "environment":"prod",
    "message":"CPU above 90% for 8 minutes and p95 latency elevated",
    "dedup_key":"prod:checkout-api:high-cpu",
    "labels":{"cluster":"prod-eks-01","namespace":"checkout","team":"payments"},
    "dashboard_url":"https://your-datadog/dashboard",
    "runbook_url":"https://your-wiki/runbooks/high-cpu"
  }'
```

The demo endpoint does not require a webhook token; secure or remove it before exposing the service outside a trusted development environment.

## Connect a real alert source

### Datadog
Create a Datadog Workflow/Webhook integration that POSTs the alert JSON to `https://<your-host>/webhook/alert`. Configure the `X-Webhook-Token` header if your integration supports custom headers. Map monitor name, status, service, env, severity, tags, dashboard URL, and runbook URL into the payload. Exact webhook templating differs by Datadog integration and account configuration; test with a non-production monitor first.

### Prometheus Alertmanager
Configure a generic webhook receiver to target this endpoint. Alertmanager's native webhook JSON schema differs from this project's normalized payload, so use an adapter/transformer or extend `AlertPayload`/`main.py` to map `alerts[]`, `labels.alertname`, `labels.severity`, `annotations.summary`, and `generatorURL`. Do not point Alertmanager directly at this endpoint until the payload mapping is implemented and tested.

## Enable Kubernetes read-only evidence

Set `ENABLE_KUBECTL_READONLY=true` only after installing `kubectl` in the container/runtime and mounting a dedicated read-only kubeconfig. Grant only the permissions needed to list pods and events in the required namespaces. Do not mount an administrator kubeconfig. In a production deployment, prefer workload identity or your platform's supported identity mechanism over static credentials.

## Optional AI mode

Set `OPENAI_API_KEY` in the secret store/environment. Without it, rule-based triage still works. Do not send secrets, credentials, full environment dumps, or unnecessary personal/customer data to an LLM. Review your organization's data-handling policies before enabling AI triage. The LLM output is advisory and must be treated as untrusted input.

## Run tests

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

## Production hardening checklist

- Put the service behind TLS and an authenticated ingress/API gateway.
- Store SMTP and AI credentials in a secrets manager; never commit `.env`.
- Rotate webhook tokens and credentials.
- Restrict inbound network access to alert-provider egress or an internal gateway.
- Add structured logging, metrics, health probes, rate limiting, and durable storage.
- Configure database retention/backup and monitor notification delivery failures.
- Add a dead-letter/retry strategy for SMTP outages.
- Validate alert signatures if the source supports signed webhooks.
- Add unit/integration tests for the exact Datadog/Alertmanager payloads.
- Use least-privilege RBAC and read-only checks by default.
- Require human approval for remediation, with audit logs and rollback procedures.

## Suggested Git repository description

`Agentic SRE alert triage automation using FastAPI, alert deduplication, optional LLM analysis, read-only Kubernetes evidence collection, and email notifications.`
