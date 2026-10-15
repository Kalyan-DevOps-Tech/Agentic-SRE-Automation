import os
import json

def _rule_based_triage(alert: dict, checks: dict) -> dict:
    text = f"{alert.get('title','')} {alert.get('message','')}".lower()
    likely_cause = "Unknown; inspect recent changes and service dependencies."
    next_steps = [
        "Check the service dashboard and compare metrics with the previous deployment.",
        "Review application logs and recent change history.",
        "Follow the linked runbook and escalate to the service owner if customer impact continues."
    ]
    if "cpu" in text:
        likely_cause = "Possible CPU saturation, increased traffic, or a runaway process; validate with host/container metrics."
        next_steps = [
            "Compare CPU, request rate, and p95/p99 latency for the same time window.",
            "Check top processes/pods and recent deployment or traffic changes.",
            "If customer impact is confirmed, follow the approved scaling or rollback runbook."
        ]
    elif "memory" in text or "oom" in text:
        likely_cause = "Possible memory pressure or leak; confirm working set, restarts, and OOM events."
        next_steps = [
            "Check memory working set, limits, restarts, and OOMKilled events.",
            "Compare memory growth with traffic and the latest release.",
            "Follow the runbook; do not increase limits or restart production workloads without approval."
        ]
    elif "latency" in text or "slow" in text or "timeout" in text:
        likely_cause = "Possible application saturation or a slow downstream dependency."
        next_steps = [
            "Compare p95/p99 latency, error rate, traffic, and dependency latency.",
            "Inspect traces and logs for the slowest endpoint or dependency.",
            "Check recent deployments and use the service runbook for mitigation."
        ]
    elif "disk" in text or "filesystem" in text:
        likely_cause = "Possible filesystem capacity growth or log/temp-file accumulation."
        next_steps = [
            "Check filesystem usage and growth rate; identify the affected mount.",
            "Check large log/temp files and retention policies without deleting data blindly.",
            "Use the approved disk cleanup runbook and confirm capacity recovery."
        ]
    return {
        "mode": "rules",
        "summary": f"{alert.get('severity','warning').upper()} alert for {alert.get('service','unknown')}: {alert.get('title','Alert')}",
        "likely_cause": likely_cause,
        "evidence": checks,
        "recommended_steps": next_steps,
        "confidence": "low-to-medium; validate against live telemetry"
    }

def triage_alert(alert: dict, checks: dict) -> dict:
    # Optional LLM enhancement. Rule-based mode remains available when no API key is set.
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return _rule_based_triage(alert, checks)
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        prompt = {
            "alert": alert,
            "read_only_checks": checks,
            "instructions": (
                "Act as an SRE incident triage assistant. Return valid JSON with keys summary, "
                "likely_cause, evidence, recommended_steps, confidence. Separate facts from hypotheses. "
                "Do not claim root cause without evidence. Recommend only safe diagnostic steps. "
                "Never execute or recommend automatic destructive production actions."
            )
        }
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            temperature=0.1,
            messages=[
                {"role": "system", "content": "You produce cautious, concise SRE alert triage. Output JSON only."},
                {"role": "user", "content": json.dumps(prompt)}
            ],
            response_format={"type": "json_object"}
        )
        result = json.loads(response.choices[0].message.content)
        result["mode"] = "llm"
        return result
    except Exception as exc:
        fallback = _rule_based_triage(alert, checks)
        fallback["llm_fallback_reason"] = type(exc).__name__
        return fallback
