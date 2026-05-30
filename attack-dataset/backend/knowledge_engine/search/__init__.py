"""
Search package - Search and attack chaining functionality.
"""

__all__ = [
    "AttackSearcher",
    "AttackChainer",
    "ingest",
]


def __getattr__(name: str):
    """Lazy imports so unit tests can import attack_chainer without qdrant/fastembed."""
    if name == "AttackSearcher":
        from .searcher import AttackSearcher

        return AttackSearcher
    if name == "AttackChainer":
        from .attack_chainer import AttackChainer

        return AttackChainer
    if name == "ingest":
        from .ingestor import ingest

        return ingest
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
