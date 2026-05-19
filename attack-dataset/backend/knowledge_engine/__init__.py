"""
Knowledge Engine — Attack Dataset Indexing & Query

Organized package structure:
- core/: API and data models
- search/: Search and attack chaining
- ml/: Machine learning models
- ai/: AI analysis and chat
- utils/: Configuration and utilities
- tests/: Unit tests
"""

import sys
import os
# Add parent directory to path to import shared modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Re-export main components for backwards compatibility
from .core.models import (
    AttackRecord,
    SearchQuery,
    SearchResponse,
    AttackVectorRequest,
    AttackVectorResponse,
)
from .search.searcher import AttackSearcher
from .search.attack_chainer import AttackChainer
from .ml.ml_service import get_ml_service
from .ml.threat_emulation import get_threat_emulation_service
from .ai.jail_break_ai import ClaudeAnalyst
from .utils.opsec_audit import OpSecAuditEngine
from .utils.config import (
    API_HOST,
    API_PORT,
    POSTGRES_DSN,
    QDRANT_HOST,
    QDRANT_PORT,
)

__all__ = [
    "AttackRecord",
    "SearchQuery",
    "SearchResponse",
    "AttackVectorRequest",
    "AttackVectorResponse",
    "AttackSearcher",
    "AttackChainer",
    "get_ml_service",
    "get_threat_emulation_service",
    "ClaudeAnalyst",
    "OpSecAuditEngine",
    "API_HOST",
    "API_PORT",
    "POSTGRES_DSN",
    "QDRANT_HOST",
    "QDRANT_PORT",
]
