"""
MisfireAI HITL (Human-in-the-Loop) approval gate.

Flow:
  1. generate_repair_brief() calls send_approval_request()
  2. A one-time token is created and stored in memory
  3. An HTML email is sent via SendGrid with Approve / Reject buttons
  4. A local FastAPI server listens for the callback on HITL_CALLBACK_PORT
  5. Pipeline blocks until owner clicks a button or timeout expires
  6. Decision (approved / rejected) is logged with timestamp + Phoenix span

Environment variables required:
  SENDGRID_API_KEY      — SendGrid API key
  HITL_FROM_EMAIL       — e.g. alerts@misfire.ai
  HITL_CALLBACK_HOST    — default: http://localhost
  HITL_CALLBACK_PORT    — default: 8741
"""

import os
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from opentelemetry import trace
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

tracer = trace.get_tracer("misfire-ai")

# In-memory token store: token → {"status": "pending"|"approved"|"rejected", "decided_at": ...}
_pending: dict[str, dict] = {}

_app = FastAPI()
_server_thread: threading.Thread | None = None


# ---------------------------------------------------------------------------
# FastAPI callback endpoints
# ---------------------------------------------------------------------------

@_app.get("/hitl/approve", response_class=HTMLResponse)
def approve(token: str):
    if token in _pending and _pending[token]["status"] == "pending":
        _pending[token]["status"] = "approved"
        _pending[token]["decided_at"] = datetime.now(timezone.utc).isoformat()
    return _decision_page("approved", "✅ Repair brief approved and logged.")


@_app.get("/hitl/reject", response_class=HTMLResponse)
def reject(token: str):
    if token in _pending and _pending[token]["status"] == "pending":
        _pending[token]["status"] = "rejected"
        _pending[token]["decided_at"] = datetime.now(timezone.utc).isoformat()
    return _decision_page("rejected", "🚫 Repair brief rejected and logged.")


def _decision_page(decision: str, message: str) -> str:
    color = "#44ff88" if decision == "approved" else "#ff4444"
    return f"""
    <!DOCTYPE html>
    <html>
    <head><title>MisfireAI</title>
    <style>
      body {{ background: #0d1117; color: #e8e8e8; font-family: sans-serif;
              display: flex; align-items: center; justify-content: center;
              height: 100vh; margin: 0; }}
      .card {{ text-align: center; padding: 40px; border: 1px solid {color};
               border-radius: 12px; max-width: 400px; }}
      h2 {{ color: {color}; }}
    </style>
    </head>
    <body>
      <div class="card">
        <h2>{message}</h2>
        <p>You can close this window.</p>
        <p style="color:#666;font-size:12px;">MisfireAI · {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>
      </div>
    </body>
    </html>
    """


# ---------------------------------------------------------------------------
# Server lifecycle
# ---------------------------------------------------------------------------

def _start_server():
    global _server_thread
    port = int(os.getenv("HITL_CALLBACK_PORT", "8741"))
    config = uvicorn.Config(_app, host="0.0.0.0", port=port, log_level="warning")
    server = uvicorn.Server(config)
    _server_thread = threading.Thread(target=server.run, daemon=True)
    _server_thread.start()
    time.sleep(0.8)  # give uvicorn a moment to bind


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

def _build_email_html(brief: "RepairBrief", approve_url: str, reject_url: str) -> str:
    systems_rows = ""
    for system, info in brief.system_scores.items():
        score = info.get("score")
        summary = info.get("summary", "")
        if score is None:
            bar_color = "#555"
            score_display = "N/A"
        elif score >= 0.75:
            bar_color = "#44ff88"
            score_display = f"{score:.2f}"
        elif score >= 0.50:
            bar_color = "#f5a623"
            score_display = f"{score:.2f}"
        else:
            bar_color = "#ff4444"
            score_display = f"{score:.2f}"

        systems_rows += f"""
        <tr>
          <td style="padding:8px;color:#ccc;text-transform:capitalize;">{system}</td>
          <td style="padding:8px;color:{bar_color};font-weight:bold;">{score_display}</td>
          <td style="padding:8px;color:#aaa;font-size:13px;">{summary}</td>
        </tr>"""

    dtc_block = ""
    if brief.dtcs:
        dtc_list = "  ".join(f"<code style='background:#1a1a2e;padding:2px 6px;border-radius:4px;color:#f5a623'>{d}</code>" for d in brief.dtcs)
        dtc_block = f"<p style='margin:12px 0'><strong style='color:#f5a623'>Active DTCs:</strong> {dtc_list}</p>"

    urgency_color = {
        "CRITICAL": "#ff2222",
        "HIGH":     "#ff6622",
        "MEDIUM":   "#f5a623",
        "LOW":      "#aaaaaa",
        "NORMAL":   "#44ff88",
    }.get(brief.urgency, "#aaaaaa")

    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="background:#0d1117;color:#e8e8e8;font-family:Arial,sans-serif;padding:0;margin:0;">
      <div style="max-width:620px;margin:40px auto;background:#161b22;border:1px solid #30363d;border-radius:12px;overflow:hidden;">

        <!-- Header -->
        <div style="background:#1e3a5f;padding:24px 32px;border-bottom:2px solid #4a9eff;">
          <h1 style="margin:0;color:#4a9eff;font-size:22px;">🔧 MisfireAI — Repair Brief</h1>
          <p style="margin:6px 0 0;color:#aaa;font-size:14px;">{brief.vehicle_year} {brief.vehicle_make} {brief.vehicle_model} &nbsp;·&nbsp; {brief.session_id}</p>
        </div>

        <!-- Urgency -->
        <div style="padding:20px 32px;border-bottom:1px solid #30363d;">
          <span style="background:{urgency_color}22;border:1px solid {urgency_color};color:{urgency_color};
                       padding:6px 16px;border-radius:20px;font-weight:bold;font-size:14px;">
            {brief.urgency}
          </span>
        </div>

        <!-- System scores -->
        <div style="padding:20px 32px;border-bottom:1px solid #30363d;">
          <h3 style="margin:0 0 12px;color:#e8e8e8;font-size:15px;">System Health Scores</h3>
          <table style="width:100%;border-collapse:collapse;">
            <thead>
              <tr style="border-bottom:1px solid #30363d;">
                <th style="padding:8px;text-align:left;color:#666;font-size:12px;">SYSTEM</th>
                <th style="padding:8px;text-align:left;color:#666;font-size:12px;">SCORE</th>
                <th style="padding:8px;text-align:left;color:#666;font-size:12px;">SUMMARY</th>
              </tr>
            </thead>
            <tbody>{systems_rows}</tbody>
          </table>
        </div>

        <!-- DTCs -->
        {dtc_block and f'<div style="padding:16px 32px;border-bottom:1px solid #30363d;">{dtc_block}</div>' or ''}

        <!-- Assessment -->
        <div style="padding:20px 32px;border-bottom:1px solid #30363d;">
          <h3 style="margin:0 0 10px;color:#e8e8e8;font-size:15px;">Agent Assessment</h3>
          <p style="margin:0;color:#ccc;font-size:14px;line-height:1.6;">{brief.assessment[:600]}{"..." if len(brief.assessment) > 600 else ""}</p>
        </div>

        <!-- Approval buttons -->
        <div style="padding:28px 32px;text-align:center;">
          <p style="margin:0 0 20px;color:#aaa;font-size:14px;">
            Review the assessment above and approve or reject this repair brief.<br>
            <strong style="color:#e8e8e8;">Your decision will be logged with a timestamp.</strong>
          </p>
          <a href="{approve_url}"
             style="background:#44ff88;color:#0d1117;padding:14px 36px;border-radius:8px;
                    font-weight:bold;font-size:15px;text-decoration:none;margin-right:16px;">
            ✅ Approve
          </a>
          <a href="{reject_url}"
             style="background:#ff4444;color:#fff;padding:14px 36px;border-radius:8px;
                    font-weight:bold;font-size:15px;text-decoration:none;">
            🚫 Reject
          </a>
        </div>

        <!-- Footer -->
        <div style="padding:16px 32px;background:#0d1117;border-top:1px solid #30363d;">
          <p style="margin:0;color:#444;font-size:12px;text-align:center;">
            MisfireAI · {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} ·
            This brief requires owner approval before any action is taken.
          </p>
        </div>

      </div>
    </body>
    </html>
    """


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

@dataclass
class RepairBrief:
    vehicle_make:  str
    vehicle_model: str
    vehicle_year:  int | str
    session_id:    str
    urgency:       str
    overall_score: float | None
    system_scores: dict
    dtcs:          list[str]
    assessment:    str
    recipient_email: str


def send_approval_request(brief: RepairBrief, timeout_seconds: int = 300) -> dict:
    """
    Send a repair brief via email and block until the owner approves/rejects
    or the timeout expires.

    Returns a dict:
      { "decision": "approved"|"rejected"|"timeout",
        "decided_at": ISO timestamp or None,
        "token": str }
    """
    _start_server()

    token = secrets.token_urlsafe(24)
    _pending[token] = {"status": "pending", "decided_at": None}

    host = os.getenv("HITL_CALLBACK_HOST", "http://localhost")
    port = os.getenv("HITL_CALLBACK_PORT", "8741")
    base = f"{host}:{port}"
    approve_url = f"{base}/hitl/approve?token={token}"
    reject_url  = f"{base}/hitl/reject?token={token}"

    with tracer.start_as_current_span("misfire.hitl.send_brief") as span:
        span.set_attribute("hitl.vehicle", f"{brief.vehicle_year} {brief.vehicle_make} {brief.vehicle_model}")
        span.set_attribute("hitl.urgency",  brief.urgency)
        span.set_attribute("hitl.recipient", brief.recipient_email)
        span.set_attribute("hitl.token",    token)
        span.set_attribute("hitl.overall_score", brief.overall_score or 0.0)

        # Send email
        api_key    = os.getenv("SENDGRID_API_KEY", "")
        from_email = os.getenv("HITL_FROM_EMAIL", "alerts@misfire.ai")

        if api_key:
            html_body = _build_email_html(brief, approve_url, reject_url)
            message = Mail(
                from_email=from_email,
                to_emails=brief.recipient_email,
                subject=f"[MisfireAI] {brief.urgency} — {brief.vehicle_year} {brief.vehicle_make} {brief.vehicle_model} Repair Brief",
                html_content=html_body,
            )
            try:
                sg = SendGridAPIClient(api_key)
                response = sg.send(message)
                span.set_attribute("hitl.email_status", response.status_code)
                print(f"   📧 Email sent → {brief.recipient_email} (HTTP {response.status_code})")
            except Exception as e:
                span.set_attribute("hitl.email_error", str(e))
                print(f"   ⚠  Email failed: {e}")
        else:
            print(f"   ⚠  SENDGRID_API_KEY not set — skipping email send")
            print(f"   🔗 Approve: {approve_url}")
            print(f"   🔗 Reject:  {reject_url}")

        # Wait for decision
        print(f"   ⏳ Waiting for owner decision (timeout: {timeout_seconds}s)...")
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            status = _pending[token]["status"]
            if status != "pending":
                break
            time.sleep(1)

        entry = _pending.pop(token, {})
        decision = entry.get("status", "timeout")
        if decision == "pending":
            decision = "timeout"
        decided_at = entry.get("decided_at")

        span.set_attribute("hitl.decision",   decision)
        span.set_attribute("hitl.decided_at", decided_at or "timeout")

        icon = {"approved": "✅", "rejected": "🚫", "timeout": "⏱"}.get(decision, "?")
        print(f"   {icon} Decision: {decision.upper()}"
              + (f" at {decided_at}" if decided_at else ""))

        return {"decision": decision, "decided_at": decided_at, "token": token}
