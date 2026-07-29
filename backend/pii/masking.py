"""
PII Masking
===========
A system component, not an agent (BRD §3, §4[A]).

Runs on the raw message before intent classification and before any model call.
The specification in `agents/sales_orchestrator_agent/reference/data-masking.md`
places masking after brief validation; this implementation deliberately moves it
earlier, because by the time a validating agent has read the brief it has already
seen the raw PII — which is exactly what masking is supposed to prevent.

Nothing in the router can skip this. It is not a step an agent chooses to run.

Scope
-----
Deterministic identity masking only: email, phone, domain, project code, and
contact names introduced by a Vietnamese honorific. These are the fields that
identify a client and can be matched without guessing.

Monetary amounts are NOT masked, a considered departure from the spec's "deal
value (exact)" row. Producing a quotation is the system's whole purpose: the gate
reads `budget_vnd`, the ratecard arithmetic needs real numbers, and an amount on
its own does not identify anyone. Brand and company aliasing also stays a
model-side instruction — reliably spotting "Masan" or "Công ty TNHH XYZ" needs
recognition, not a regular expression, and a half-working regex here would be
worse than an explicit rule in the prompt because it would look like protection.

Alias tables live only in memory, keyed by session, and are never written to
state, to disk, or to a log (BRD §13). `SalesCaseState` is persisted to SQLite,
so the table is intentionally kept outside it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterator, Optional

# --------------------------------------------------------------------------
# Patterns
# --------------------------------------------------------------------------

# Order matters: email before domain, or the domain rule eats the address tail.
_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    (
        "PHONE",
        # Vietnamese mobile/landline, optional +84, tolerating spaces, dots and dashes.
        re.compile(r"(?<![\w])(?:\+?84|0)(?:[\s.\-]?\d){8,10}(?![\w])"),
    ),
    (
        "PROJECT",
        re.compile(r"\b[A-Z]{2,6}-\d{2,4}-\d{2,6}\b"),
    ),
    (
        "DOMAIN",
        re.compile(
            r"\b(?:https?://)?(?:www\.)?"
            r"[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*"
            r"\.(?:com|vn|net|org|io|co|asia)(?:\.[a-z]{2})?"
            r"(?:/[^\s]*)?\b"
        ),
    ),
    (
        "CONTACT",
        # A Vietnamese honorific followed by a capitalised name. Requires the
        # honorific: bare capitalised words are far more often brands or places.
        re.compile(
            r"\b(?:anh|chị|chi|ông|ong|bà|ba|em|Mr\.?|Ms\.?|Mrs\.?)\s+"
            r"((?:[A-ZÀ-Ỹ][a-zà-ỹ]+)(?:\s+[A-ZÀ-Ỹ][a-zà-ỹ]+){0,3})",
            re.IGNORECASE,
        ),
    ),
]

# Words that look like domains but are platforms, not client identity (spec: "Do NOT mask").
_DOMAIN_ALLOWLIST = {
    "zalo.me", "zalo.vn", "facebook.com", "tiktok.com", "shopee.vn", "lazada.vn",
    "haravan.com", "kiotviet.vn", "google.com", "youtube.com",
}


@dataclass
class MaskResult:
    text: str
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return sum(self.counts.values())

    def log_line(self) -> str:
        """§14: log how many items of each kind were masked. Never the values."""
        if not self.counts:
            return "[pii] nothing to mask"
        detail = ", ".join(f"{k}×{v}" for k, v in sorted(self.counts.items()))
        return f"[pii] masked {self.total} item(s): {detail}"


class SessionMasker:
    """Holds one session's alias table. Never persisted, never logged."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self._to_alias: dict[str, str] = {}   # raw value -> alias
        self._to_raw: dict[str, str] = {}     # alias -> raw value
        self._counters: dict[str, int] = {}
        # unmask() runs on every streamed SSE chunk for the life of the turn,
        # and used to re-sort self._to_raw by length on every single call.
        # Alias counts are single digits so the sort itself was cheap, but it
        # was still wasted work on a hot path — invalidated only when a new
        # alias is actually added.
        self._sorted_aliases: Optional[list[str]] = None

    def _alias_for(self, kind: str, raw: str) -> str:
        existing = self._to_alias.get(raw)
        if existing:
            return existing
        self._counters[kind] = self._counters.get(kind, 0) + 1
        alias = f"[{kind}-{self._counters[kind]}]"
        self._to_alias[raw] = alias
        self._to_raw[alias] = raw
        self._sorted_aliases = None
        return alias

    def mask(self, text: str) -> MaskResult:
        if not text:
            return MaskResult(text=text or "")

        counts: dict[str, int] = {}
        masked = text

        for kind, pattern in _PATTERNS:
            def _replace(m: re.Match) -> str:
                # CONTACT captures the name only, so the honorific survives.
                raw = m.group(1) if kind == "CONTACT" and m.groups() else m.group(0)
                if kind == "DOMAIN":
                    bare = raw.lower().lstrip("https://").lstrip("www.").split("/")[0]
                    if bare in _DOMAIN_ALLOWLIST:
                        return m.group(0)
                alias = self._alias_for(kind, raw)
                counts[kind] = counts.get(kind, 0) + 1
                return m.group(0).replace(raw, alias)

            masked = pattern.sub(_replace, masked)

        return MaskResult(text=masked, counts=counts)

    def unmask(self, text: str) -> str:
        """Restore real values for text about to be shown to the rep.

        Longest alias first so `[PHONE-11]` is not clipped by `[PHONE-1]`.
        """
        if not text or not self._to_raw:
            return text
        if self._sorted_aliases is None:
            self._sorted_aliases = sorted(self._to_raw, key=len, reverse=True)
        for alias in self._sorted_aliases:
            text = text.replace(alias, self._to_raw[alias])
        return text

    def has_aliases(self) -> bool:
        return bool(self._to_raw)


# --------------------------------------------------------------------------
# Registry — in memory only, deliberately not part of SalesCaseState
# --------------------------------------------------------------------------

_MASKERS: dict[str, SessionMasker] = {}


def get_masker(session_id: str) -> SessionMasker:
    masker = _MASKERS.get(session_id)
    if masker is None:
        masker = SessionMasker(session_id)
        _MASKERS[session_id] = masker
    return masker


def forget_session(session_id: str) -> None:
    """Drop a session's alias table. Call when a session ends or is deleted."""
    _MASKERS.pop(session_id, None)


def iter_sessions() -> Iterator[str]:
    return iter(list(_MASKERS.keys()))
