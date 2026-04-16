"""Shared pytest fixtures.

Forces the lead_pipeline to use a fresh in-memory SQLite per test run so
nothing touches Postgres.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator

import pytest

# Set env BEFORE importing the app modules.
_TMP = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMP.close()
os.environ.setdefault("DATABASE_URL", f"sqlite+pysqlite:///{_TMP.name}")
os.environ.setdefault("LEAD_PIPELINE_SECRET_KEY", "test-secret-key-min-16-bytes-long-aaaa")
os.environ.setdefault("LEAD_PIPELINE_BASE_URL", "http://test")


@pytest.fixture(autouse=True)
def _reset_db() -> Iterator[None]:
    # Lazy import so the env vars above are already set.
    from lead_pipeline.app.db import engine
    from lead_pipeline.app.models import Base

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
