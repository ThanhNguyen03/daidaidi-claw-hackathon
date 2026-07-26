"""Knowledge retrieval layer — the only path by which agent knowledge reaches a prompt."""

from knowledge.loader import (
    KnowledgeUnavailable,
    ReferenceEntry,
    RequestLedger,
    load,
    parse_catalog,
    select,
)

__all__ = [
    "KnowledgeUnavailable",
    "ReferenceEntry",
    "RequestLedger",
    "load",
    "parse_catalog",
    "select",
]
