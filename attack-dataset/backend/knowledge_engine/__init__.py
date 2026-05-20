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
    "API_HOST",
    "API_PORT",
    "POSTGRES_DSN",
    "QDRANT_HOST",
    "QDRANT_PORT",
]


def __getattr__(name: str):
    """Lazy imports so `import knowledge_engine.core.models` does not require qdrant."""
    _lazy = {
        "AttackSearcher": (".search.searcher", "AttackSearcher"),
        "AttackChainer": (".search.attack_chainer", "AttackChainer"),
        "get_ml_service": (".ml.ml_service", "get_ml_service"),
        "get_threat_emulation_service": (".ml.threat_emulation", "get_threat_emulation_service"),
        "ClaudeAnalyst": (".ai.jail_break_ai", "ClaudeAnalyst"),
        "OpSecAuditEngine": (".utils.opsec_audit", "OpSecAuditEngine"),
    }
    if name in _lazy:
        module_path, attr = _lazy[name]
        import importlib
        mod = importlib.import_module(module_path, __name__)
        return getattr(mod, attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
