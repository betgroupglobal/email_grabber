"""Request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class SignupIn(BaseModel):
    email: EmailStr
    name: str | None = Field(default=None, max_length=200)
    company: str | None = Field(default=None, max_length=200)
    consent: bool = Field(
        ...,
        description=(
            "User must affirmatively tick a consent box before their address is "
            "stored. Required by the Spam Act 2003 (Cth)."
        ),
    )


class SignupOut(BaseModel):
    status: str
    message: str
