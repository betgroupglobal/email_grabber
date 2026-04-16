"""FastAPI app for the consented opt-in lead pipeline."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from email_validator import EmailNotValidError, validate_email
from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import engine, get_db
from .email import EmailSender, get_sender
from .models import Base, Lead
from .tokens import (
    hash_ip,
    make_confirmation_token,
    new_jti,
    parse_confirmation_token,
)


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Convenience for SQLite/dev. In prod, schema comes from db/init.sql.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="email_grabber lead pipeline",
    description=(
        "Consent-first opt-in mailing list service. All sign-ups require an "
        "affirmative consent checkbox AND a confirmation click on a unique link "
        "emailed to the user (double opt-in). Designed to satisfy s 16 of the "
        "Spam Act 2003 (Cth)."
    ),
    version="0.1.0",
    lifespan=_lifespan,
)

_TEMPLATE_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))


@app.get("/", response_class=HTMLResponse)
def signup_form(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "form.html", {})


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/signup", response_class=HTMLResponse)
async def signup(
    request: Request,
    email: str = Form(...),
    name: str | None = Form(default=None),
    company: str | None = Form(default=None),
    consent: str | None = Form(default=None),
    db: Session = Depends(get_db),
    sender: EmailSender = Depends(get_sender),
) -> HTMLResponse:
    if consent != "true":
        return templates.TemplateResponse(
            request,
            "error.html",
            {"message": "You must tick the consent box before subscribing."},
            status_code=400,
        )
    try:
        validated = validate_email(email.strip(), check_deliverability=False)
    except EmailNotValidError:
        return templates.TemplateResponse(
            request,
            "error.html",
            {"message": "That doesn't look like a valid email address."},
            status_code=400,
        )

    email_norm = validated.normalized.lower()
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")[:500]

    existing = db.execute(select(Lead).where(Lead.email == email_norm)).scalar_one_or_none()
    if existing and existing.confirmed:
        # Don't leak whether the email is already subscribed; just show "sent".
        return templates.TemplateResponse(request, "sent.html", {"email": email_norm})

    jti = new_jti()
    token = make_confirmation_token(email_norm, jti)

    if existing is None:
        lead = Lead(
            email=email_norm,
            name=name,
            company=company,
            confirmed=False,
            consent_source=f"web_form:{request.url.path}",
            ip_hash=hash_ip(client_ip),
            user_agent=user_agent,
            token_jti=jti,
        )
        db.add(lead)
    else:
        # Re-issue: refresh jti so old links stop working.
        existing.token_jti = jti
        existing.user_agent = user_agent
        existing.ip_hash = hash_ip(client_ip)
    db.commit()

    settings = get_settings()
    confirm_url = f"{settings.base_url}/confirm?token={token}"
    body = (
        f"Hi{f' {name}' if name else ''},\n\n"
        f"You (or someone using this address) asked to subscribe to BetGroup "
        f"Research updates. To confirm, click:\n\n"
        f"  {confirm_url}\n\n"
        f"This link is valid for 7 days. If you didn't ask for this, just ignore "
        f"this email and we'll discard the request.\n\n"
        f"— BetGroup Research\n"
    )
    await sender.send(to=email_norm, subject="Confirm your subscription", text=body)

    return templates.TemplateResponse(request, "sent.html", {"email": email_norm})


@app.get("/confirm", response_class=HTMLResponse)
def confirm(
    request: Request,
    token: str,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    try:
        email, jti = parse_confirmation_token(token)
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "error.html",
            {"message": f"Confirmation link is not valid ({exc})."},
            status_code=400,
        )

    lead = db.execute(select(Lead).where(Lead.email == email)).scalar_one_or_none()
    if lead is None or lead.token_jti != jti:
        return templates.TemplateResponse(
            request,
            "error.html",
            {"message": "Confirmation link is no longer valid. Please sign up again."},
            status_code=400,
        )

    if not lead.confirmed:
        lead.confirmed = True
        lead.confirmed_at = datetime.now(UTC)
        db.commit()

    return templates.TemplateResponse(request, "confirmed.html", {"email": email})


@app.get("/unsubscribe")
def unsubscribe(
    token: str,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        email, _jti = parse_confirmation_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"invalid token: {exc}") from exc

    lead = db.execute(select(Lead).where(Lead.email == email)).scalar_one_or_none()
    if lead is not None:
        lead.unsubscribed_at = datetime.now(UTC)
        lead.confirmed = False
        db.commit()
    return RedirectResponse(url="/", status_code=303)
