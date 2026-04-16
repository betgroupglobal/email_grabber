from __future__ import annotations

import re

from fastapi.testclient import TestClient


def _client() -> TestClient:
    from lead_pipeline.app.main import app

    return TestClient(app)


def test_healthz() -> None:
    resp = _client().get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_signup_requires_consent() -> None:
    resp = _client().post(
        "/signup",
        data={"email": "a@example.com"},
    )
    assert resp.status_code == 400
    assert "consent" in resp.text.lower()


def test_signup_rejects_invalid_email() -> None:
    resp = _client().post(
        "/signup",
        data={"email": "not-an-email", "consent": "true"},
    )
    assert resp.status_code == 400
    assert "valid email" in resp.text.lower()


def test_full_double_opt_in_flow(caplog) -> None:  # type: ignore[no-untyped-def]
    """End-to-end: sign up, capture token from emailed body, confirm."""
    import logging

    from sqlalchemy import select

    from lead_pipeline.app.db import SessionLocal
    from lead_pipeline.app.models import Lead

    client = _client()
    caplog.set_level(logging.INFO)

    resp = client.post(
        "/signup",
        data={"email": "lead@example.com", "name": "Lead Person", "consent": "true"},
    )
    assert resp.status_code == 200
    assert "Check your inbox" in resp.text

    # Lead exists, but not yet confirmed.
    with SessionLocal() as s:
        lead = s.execute(select(Lead).where(Lead.email == "lead@example.com")).scalar_one()
        assert lead.confirmed is False
        assert lead.confirmed_at is None
        assert lead.consent_source == "web_form:/signup"
        assert lead.ip_hash and len(lead.ip_hash) == 64

    # Pull the confirmation URL out of the StdoutSender's log line.
    log_text = "\n".join(r.getMessage() for r in caplog.records)
    match = re.search(r"http://test/confirm\?token=([\w\.\-]+)", log_text)
    assert match, f"no confirmation link in logs:\n{log_text}"
    token = match.group(1)

    resp = client.get(f"/confirm?token={token}")
    assert resp.status_code == 200
    assert "subscription is confirmed" in resp.text.lower()

    with SessionLocal() as s:
        lead = s.execute(select(Lead).where(Lead.email == "lead@example.com")).scalar_one()
        assert lead.confirmed is True
        assert lead.confirmed_at is not None


def test_unsubscribe(caplog) -> None:  # type: ignore[no-untyped-def]
    import logging

    from sqlalchemy import select

    from lead_pipeline.app.db import SessionLocal
    from lead_pipeline.app.models import Lead

    client = _client()
    caplog.set_level(logging.INFO)

    client.post(
        "/signup",
        data={"email": "bye@example.com", "consent": "true"},
    )
    log_text = "\n".join(r.getMessage() for r in caplog.records)
    token = re.search(r"http://test/confirm\?token=([\w\.\-]+)", log_text).group(1)  # type: ignore[union-attr]

    # Confirm first…
    client.get(f"/confirm?token={token}")
    # …then unsubscribe (uses same signed token format).
    resp = client.get(f"/unsubscribe?token={token}", follow_redirects=False)
    assert resp.status_code == 303

    with SessionLocal() as s:
        lead = s.execute(select(Lead).where(Lead.email == "bye@example.com")).scalar_one()
        assert lead.confirmed is False
        assert lead.unsubscribed_at is not None
