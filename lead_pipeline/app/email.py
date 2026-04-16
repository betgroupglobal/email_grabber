"""Email sending — Resend if configured, stdout otherwise."""

from __future__ import annotations

import logging
from typing import Protocol

import httpx

from .config import get_settings

logger = logging.getLogger(__name__)


class EmailSender(Protocol):
    async def send(self, *, to: str, subject: str, text: str) -> None: ...


class StdoutSender:
    """Dev/test fallback. Prints the email instead of sending it."""

    async def send(self, *, to: str, subject: str, text: str) -> None:
        logger.info("=== email to=%s subject=%r ===\n%s\n=== end ===", to, subject, text)


class ResendSender:
    """Sends via https://resend.com REST API."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def send(self, *, to: str, subject: str, text: str) -> None:
        settings = get_settings()
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "from": f"{settings.from_name} <{settings.from_email}>",
                    "to": [to],
                    "subject": subject,
                    "text": text,
                },
            )
        if resp.status_code >= 400:
            raise RuntimeError(f"Resend error {resp.status_code}: {resp.text}")


def get_sender() -> EmailSender:
    settings = get_settings()
    if settings.resend_api_key:
        return ResendSender(settings.resend_api_key)
    return StdoutSender()
