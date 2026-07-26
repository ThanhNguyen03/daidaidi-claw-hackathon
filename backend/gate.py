"""
Requirement Gate
================
Pure code. No model call, no bypass flag (BRD §8).

The model extracts information; this module decides whether that is enough to
let specialist agents run. Letting the model make that call is what produced the
previous behaviour, where an incomplete brief still dispatched because the check
lived inside a prompt and prompts are advisory.

Three states, not a boolean — a boolean forces a choice between blocking a rep
who knowingly wants to proceed and letting an empty brief through:

    CHAN_HOI_LAI        required field missing, rep has not opted out
                        -> only the elicitation path runs
    CHAY_CO_PHONG_DOAN  rep said "proceed anyway", or only nice-to-have gaps
                        -> runs, output is labelled, assumptions listed
    CHAY_DAY_DU         required fields present
                        -> runs normally

Deliberately absent: any parameter, config key or environment variable that
skips the gate (§8.1). The only opt-out is the rep saying so in the conversation,
and even then the missing fields become labelled assumptions rather than
disappearing (§8.2).

Which fields are guarded is data, in config/gate_fields.yaml — sales and BA can
change the policy without a deploy. That the gate runs at all is code.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_POLICY_PATH = os.path.join(_HERE, "config", "gate_fields.yaml")


class GateState(str, Enum):
    BLOCK_AND_ASK = "CHAN_HOI_LAI"
    RUN_WITH_ASSUMPTIONS = "CHAY_CO_PHONG_DOAN"
    RUN_COMPLETE = "CHAY_DAY_DU"


@dataclass
class MissingField:
    field: str
    why: str
    blocking: bool


@dataclass
class GateVerdict:
    state: GateState
    missing: list[MissingField] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    reason: str = ""

    @property
    def may_dispatch(self) -> bool:
        """True when specialist agents are allowed to run."""
        return self.state is not GateState.BLOCK_AND_ASK

    @property
    def blocking_fields(self) -> list[str]:
        return [m.field for m in self.missing if m.blocking]

    def log_line(self) -> str:
        """One line for the §14 log: state plus the fields that caused it."""
        missing = ",".join(m.field for m in self.missing) or "-"
        return f"[gate] {self.state.value} missing={missing} reason={self.reason}"


# --------------------------------------------------------------------------
# Policy
# --------------------------------------------------------------------------

_policy_cache: Optional[dict] = None

# Used only if the policy file is unreadable. Fails CLOSED — a broken policy file
# must not silently turn the gate into a pass-through.
_FALLBACK_POLICY: dict = {
    "required": [
        {"field": "industry", "why": "Compliance rules and case studies are keyed by industry."},
        {"field": "goal", "why": "Determines campaign vs platform, which changes package and price."},
    ],
    "conditional": [],
    "nice_to_have": [],
    "bypass_intents": ["lookup", "coaching"],
    "proceed_anyway_phrases": ["cứ làm đi", "proceed anyway", "just do it"],
}


def load_policy() -> dict:
    global _policy_cache
    if _policy_cache is not None:
        return _policy_cache
    try:
        import yaml

        with open(_POLICY_PATH, "r", encoding="utf-8") as f:
            _policy_cache = yaml.safe_load(f) or {}
    except Exception as exc:
        print(f"[gate] WARNING: cannot read {_POLICY_PATH} ({exc}); using built-in policy")
        _policy_cache = dict(_FALLBACK_POLICY)
    return _policy_cache


# --------------------------------------------------------------------------
# Evaluation
# --------------------------------------------------------------------------

def _is_present(value: Any) -> bool:
    """A field counts as present only when it is non-empty (BRD §12.1) —
    existing but blank is the same as missing."""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) > 0
    return True


def said_proceed_anyway(text: str, history: Optional[list[dict]] = None) -> bool:
    """Did the rep explicitly accept running on assumptions?

    Checked against the current message and this session's earlier user turns,
    because the permission should persist once given rather than having to be
    repeated every turn.
    """
    policy = load_policy()
    phrases = [p.lower() for p in policy.get("proceed_anyway_phrases", [])]
    haystack = (text or "").lower()
    for m in history or []:
        if m.get("role") == "user":
            haystack += " " + (m.get("content") or "").lower()
    return any(p in haystack for p in phrases)


def _conditional_applies(entry: dict, brief: Any, text: str) -> bool:
    triggers = [t.lower() for t in entry.get("when_any_of", [])]
    if not triggers:
        return False
    haystack = (text or "").lower()
    for attr in ("industry", "goal", "target_audience", "additional_context"):
        value = getattr(brief, attr, None)
        if isinstance(value, str):
            haystack += " " + value.lower()
    return any(t in haystack for t in triggers)


def evaluate(
    brief: Any,
    message: str = "",
    intent: str = "brief",
    history: Optional[list[dict]] = None,
) -> GateVerdict:
    """Decide whether specialist agents may run for this turn.

    `brief` is anything with the Brief attributes; `intent` comes from the
    classifier. Lookup and coaching skip the gate (§8.3) — a rep asking what ZNS
    costs is not building a brief and should not be interrogated.
    """
    policy = load_policy()

    if intent in policy.get("bypass_intents", []):
        return GateVerdict(
            state=GateState.RUN_COMPLETE,
            reason=f"intent '{intent}' does not pass through the gate",
        )

    if brief is None:
        missing = [
            MissingField(e["field"], e.get("why", ""), blocking=True)
            for e in policy.get("required", [])
        ]
        if said_proceed_anyway(message, history):
            return GateVerdict(
                state=GateState.RUN_WITH_ASSUMPTIONS,
                missing=missing,
                assumptions=[m.field for m in missing],
                reason="no brief, but rep asked to proceed anyway",
            )
        return GateVerdict(
            state=GateState.BLOCK_AND_ASK, missing=missing, reason="no brief captured yet"
        )

    missing: list[MissingField] = []

    for entry in policy.get("required", []):
        if not _is_present(getattr(brief, entry["field"], None)):
            missing.append(MissingField(entry["field"], entry.get("why", ""), blocking=True))

    for entry in policy.get("conditional", []):
        if not _conditional_applies(entry, brief, message):
            continue
        if not _is_present(getattr(brief, entry["field"], None)):
            missing.append(MissingField(entry["field"], entry.get("why", ""), blocking=True))

    for entry in policy.get("nice_to_have", []):
        if not _is_present(getattr(brief, entry["field"], None)):
            missing.append(MissingField(entry["field"], entry.get("why", ""), blocking=False))

    blocking = [m for m in missing if m.blocking]

    if not blocking:
        soft = [m.field for m in missing]
        if soft:
            return GateVerdict(
                state=GateState.RUN_WITH_ASSUMPTIONS,
                missing=missing,
                assumptions=soft,
                reason="all required fields present; nice-to-have gaps assumed",
            )
        return GateVerdict(
            state=GateState.RUN_COMPLETE, reason="all required fields present"
        )

    if said_proceed_anyway(message, history):
        # The field is NOT dropped — it becomes an assumption the output must label (§8.2).
        return GateVerdict(
            state=GateState.RUN_WITH_ASSUMPTIONS,
            missing=missing,
            assumptions=[m.field for m in missing],
            reason="rep asked to proceed anyway; missing fields carried as labelled assumptions",
        )

    return GateVerdict(
        state=GateState.BLOCK_AND_ASK,
        missing=missing,
        reason="required field(s) missing: " + ", ".join(m.field for m in blocking),
    )


def assumption_notice(verdict: GateVerdict) -> str:
    """Text appended to a skill task when running on assumptions, so the output
    declares what it guessed instead of presenting guesses as fact."""
    if verdict.state is not GateState.RUN_WITH_ASSUMPTIONS or not verdict.assumptions:
        return ""
    lines = [
        "",
        "⚠️ RUNNING WITH ASSUMPTIONS — the following were never confirmed by the rep:",
    ]
    for m in verdict.missing:
        if m.field in verdict.assumptions:
            lines.append(f"  - {m.field}: {m.why.strip()}")
    lines.append(
        "State your assumption for each of these explicitly in the output, and mark "
        "any number that depends on one as provisional. Do not present an assumption "
        "as a confirmed fact."
    )
    return "\n".join(lines)
