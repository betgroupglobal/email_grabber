from __future__ import annotations

import pytest


def test_make_and_parse_token_roundtrip() -> None:
    from lead_pipeline.app.tokens import (
        make_confirmation_token,
        new_jti,
        parse_confirmation_token,
    )

    jti = new_jti()
    token = make_confirmation_token("Foo@Example.com", jti)
    email, parsed_jti = parse_confirmation_token(token)
    assert email == "foo@example.com"
    assert parsed_jti == jti


def test_parse_rejects_garbage() -> None:
    from lead_pipeline.app.tokens import parse_confirmation_token

    with pytest.raises(ValueError):
        parse_confirmation_token("not-a-token")


def test_hash_ip_is_deterministic_and_not_reversible() -> None:
    from lead_pipeline.app.tokens import hash_ip

    h1 = hash_ip("203.0.113.7")
    h2 = hash_ip("203.0.113.7")
    h3 = hash_ip("203.0.113.8")
    assert h1 == h2
    assert h1 != h3
    assert "203.0.113.7" not in h1
    assert len(h1) == 64  # sha256 hex
