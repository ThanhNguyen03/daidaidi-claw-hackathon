"""
Central Agent
=============
Single entry point that:
1. Assesses whether the client brief is clear enough to run analysis
2. If incomplete: asks targeted clarifying questions (max 3 per turn, Layer 0 first)
3. If clear: picks relevant skills and executes in parallel
4. Streams a synthesized final response

Design principles:
- Clarify first using the 6-layer requirement elicitation framework
- Execute as soon as industry + basic goal are known (don't over-ask)
- If planning LLM fails, fall back to direct skill execution (never block)
- Skills run concurrently; synthesis streams tokens as they arrive
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import datetime
from functools import partial
import random
from typing import Any, AsyncGenerator, Optional

import gate
from knowledge.loader import RequestLedger
from schemas.state import (
    AgentOutput,
    Brief,
    FeedbackRule,
    Question,
    SalesCaseState,
)
from skills.base import SkillContext, SkillOutput, strip_think_blocks, extract_json_block
from skills.registry import get_skill_registry

_HERE = os.path.dirname(os.path.abspath(__file__))
_SKILL_MD_PATH = os.path.join(_HERE, "SKILL.md")


def _load_central_skill() -> str:
    try:
        with open(_SKILL_MD_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"Warning: Could not load central agent SKILL.md: {e}")
        return "You are the AdtimaBox Sales Agent."


_CENTRAL_SKILL = _load_central_skill()

_SKILL_TIMEOUT_S = 270  # per-skill wall-clock timeout; increased to give slow GreenNode MAAS room
_RECENT_HISTORY_WINDOW = 20
_SYNTHESIS_HISTORY_WINDOW = 12
# Skills that must run in the final group (after all analysis skills complete).
# Both assembler and wireframe_designer run in parallel within that final group —
# wireframe_designer reads the 4 analysis skill outputs directly (not assembler output)
# which is exactly what we want: deck generation without waiting for the assembler.
_ALWAYS_SEQUENTIAL: set[str] = {"proposal_assembler", "wireframe_designer"}
# Fallback only: fires if wireframe_designer wasn't paired with assembler in the plan.
# In normal flow both are injected together and _AUTO_AFTER never triggers.
_AUTO_AFTER: dict[str, str] = {"proposal_assembler": "wireframe_designer"}


# ---------------------------------------------------------------------------
# Assessment + Planning prompt
# ---------------------------------------------------------------------------

_PLANNING_SYSTEM_TEMPLATE = """You are the AdtimaBox Sales AI — planning engine.

You receive:
  • Conversation History — all prior messages (USER and ASSISTANT turns)
  • Accumulated Brief — client info extracted so far
  • Already Executed Skills — what ran in earlier turns this session
  • Current Message — what the user just sent

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 1 — CLARIFY or EXECUTE?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Count CLARIFICATION ROUNDS USED = number of ASSISTANT turns in Conversation History.

ALWAYS EXECUTE when clarification rounds ≥ 2 — never ask more questions after 2 rounds.

Otherwise, decide based on task type and missing info:

QUOTE / PRICING request (user wants a formal pricing estimate, quotation, or cost breakdown):
  → CLARIFY if missing ANY of: (1) campaign type (short-term campaign vs long-term loyalty platform), (2) rough user base / expected scale
  → This rule takes priority over STRATEGY rule when brief contains both strategy + pricing asks
  → Questions to ask: campaign type & duration, expected number of users/participants, budget range (optional)
  → EXECUTE directly only if scale AND campaign type are both known

STRATEGY / MARKET ANALYSIS request:
  Clarification is allowed for up to 2 rounds (the server enforces execute after ≥2 assistant turns).
  Apply these rules at each turn — regardless of how many prior turns exist:
  → CLARIFY if industry OR primary goal/objective is still missing from the brief
  → CLARIFY if industry + goal are known but ALL of (scale/user-base, budget, timeline) are missing
  → EXECUTE when industry + goal + at least one of (scale, budget, timeline) is known
  → EXECUTE immediately when prior assistant turn(s) already contained full analysis or recommendations
    (the user has seen analysis output and is now refining or asking follow-up — NOT just answering questions)

DESIGN / USERFLOW request:
  → CLARIFY if missing core mechanics or user journey goal
  → EXECUTE if rough use-case is known

FOLLOW-UP / REFINEMENT (user already received a response):
  → ALWAYS EXECUTE — user is refining, not starting fresh
  → Signs: "nói kĩ hơn", "giải thích thêm", "chi tiết hơn", "về phần X", "tại sao", "so sánh"

GENERAL QUESTION or VAGUE REQUEST:
  → CLARIFY if completely missing context
  → EXECUTE if any context exists

When CLARIFYING:
  • Infer everything you reasonably can first. Fill it in, mark it as inferred, and ask
    the rep to CONFIRM — never ask a question you could have answered yourself.
  • Ask only what genuinely cannot be inferred.
  • Put it all in ONE turn under three headings:
        Mình tự suy ra  ·  Cần bạn cho biết  ·  Cần hỏi lại khách
    That last split lets the rep send the client one email instead of three.
  • Give the reason for each question.
  • Never ask a question whose answer depends on another question in the same batch.
  • There is NO cap on the number of questions. Stop when you have enough to reach a
    feasibility verdict — not at some fixed count. A rep does not know what they do
    not know, so a cap drops exactly the questions they would never have thought of.
  • Be warm and direct — frame as "để đưa ra đề xuất chính xác nhất, mình cần thêm..."
  • Do NOT ask for info already in Conversation History or Accumulated Brief
  • Match the user's language (Vietnamese if they wrote in Vietnamese)
  • END with what unblocks it, concretely: which field you need and what you will do
    once you have it. The rep must never have to guess whose turn it is.
    e.g. "**Tiếp theo:** cho mình ngành hàng và mục tiêu là mình chạy phân tích ngay."

When EXECUTING:
  • Skills will flag "cần xác nhận thêm" for unknowns — that is fine
  • Do not refuse to help because of incomplete info after 2 rounds of questions

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 2 — MATCH BRIEF TO SKILLS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Available skills (name: description):
{skill_catalog}

BASELINE RULE: For any sales brief (brand + objective present), ALWAYS include both:
  • market_strategy — strategic positioning, case studies, why-Zalo, audience insights, competitive edge
  • product_solution — product fit, architecture, pricing, userflow

Additional skills to add when relevant:
  • design — add when brief asks for idea, userflow, wireframe, game mechanic, screen design
  • compliance — add when brief involves personal data collection, ZNS, advertising claims, or regulatory concerns
  • client_simulator — add when brief has signs of a competitive pitch or objection-handling is useful
  • proposal_assembler (alone, last group):
      INCLUDE when the user intends to receive a formal proposal document, deck, or pricing summary
      as a deliverable — based on semantic understanding of the FULL conversation context.

      ALREADY GENERATED: if "proposal_assembler" is listed in Already Executed This Session → it ran before.
        → Re-include ONLY if the user is explicitly requesting a new or updated proposal THIS turn.
        → Do NOT re-include just because the conversation continues or the user is adding context.

      NOT YET GENERATED: if proposal_assembler is NOT in Already Executed This Session:
        → Include if the user's current message OR a very recent prior message (≤2 turns ago)
          expressed intent to receive a formal proposal or deck — even if they are now
          providing budget/scale/timeline details that complete that earlier request.

Read the FULL context — Conversation History + Accumulated Brief + Current Message.
The current message is the primary signal for which skills to select, but ALSO scan
Conversation History for signals the user expressed in prior turns.

Write a SPECIFIC task for every selected skill — reference the brand, objective, TA, and
exactly what aspect of the brief that skill should address. Vague tasks produce vague output.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 3 — DESIRED OUTPUTS (semantic intent extraction)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Before outputting JSON, extract what output artifacts the user wants. This field is STICKY
across turns — once set it stays set for the whole session (the server accumulates it).

Set desired_outputs to ["proposal"] when the user's overall intent across the conversation
is to receive a formal proposal, deck, or pricing document as a deliverable.
Detect this semantically — a user asking for formal output materials should set this field.
Leave as [] for analysis-only conversations, refinement questions, or strategy discussions.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 4 — OUTPUT (valid JSON only, no markdown fences)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Skills in the same array run in parallel. Arrays run sequentially.
proposal_assembler must be alone in the last array if included.

Case A — clarify:
{{"brief_update": {{"industry": null, "goal": null, "target_audience": null, "budget_vnd": null, "timeline": null, "additional_context": null}}, "needs_clarification": true, "clarification_message": "<one grouped set of questions in the user's language, under the three headings above, each with its reason>", "desired_outputs": []}}

Case B — execute:
{{"brief_update": {{"industry": "<or null>", "goal": "<or null>", "target_audience": "<or null>", "budget_vnd": null, "timeline": null, "additional_context": null}}, "needs_clarification": false, "skill_plan": [[{{"skill": "<name>", "task": "<specific task>"}}]], "desired_outputs": ["proposal"]}}"""


# ---------------------------------------------------------------------------
# Context-aware skill plan builder (uses accumulated brief + history)
# ---------------------------------------------------------------------------

def _build_contextual_skill_plan(state, message: str) -> list[list[dict[str, str]]]:
    """Fallback plan builder used when the planning LLM fails or returns an empty plan.

    Priority:
    1. Prior outputs exist → re-run those same skills (they were contextually chosen)
    2. History exists but no prior outputs → run all registered non-sequential skills
    3. Fresh session → run all registered non-sequential skills (safe default)
    """
    from skills.registry import get_skill_registry
    task_short = message[:400]
    # Sequential skills are excluded from the analysis group and injected
    # as their own final parallel group (assembler + wireframe run together).
    _SEQUENTIAL = {"proposal_assembler", "wireframe_designer"}

    registry = get_skill_registry()
    all_skill_names = registry.all_names()
    core_skills = [n for n in all_skill_names if n not in _SEQUENTIAL]

    prior_skill_names = [n for n in state.outputs.keys() if n not in _SEQUENTIAL] if state.outputs else []

    if prior_skill_names:
        first_group = [
            {"skill": s, "task": f"Continue and deepen analysis for: {task_short}"}
            for s in prior_skill_names
        ]
        plan: list[list[dict[str, str]]] = [first_group]
        if "proposal_assembler" in (state.outputs or {}):
            plan.append([
                {"skill": "proposal_assembler",
                 "task": f"Reassemble proposal incorporating: {task_short}"},
                {"skill": "wireframe_designer",
                 "task": "Generate HTML deck + PPTX from all skill outputs"},
            ])
        return plan

    # Default: run all core skills
    return [[
        {"skill": s, "task": f"Analyze and provide insights for: {task_short}"}
        for s in core_skills
    ]]


# ---------------------------------------------------------------------------
# Confirmation stops (BRD §11)
# ---------------------------------------------------------------------------

def _classify_brief_sources(state, verdict) -> dict[str, list[dict]]:
    """Split the working brief into what the rep said, what we inferred, and what we
    are assuming (BRD §12.2 — every item carries its origin).

    "Said" is anything that appears verbatim in the rep's own turns; everything else
    the extractor produced is an inference. Fields the gate flagged as missing but
    which we are proceeding on are assumptions.
    """
    said_text = " ".join(
        (m.get("content") or "").lower()
        for m in state.messages
        if m.get("role") == "user"
    )

    labels = {
        "industry": "Ngành hàng",
        "goal": "Mục tiêu",
        "target_audience": "Đối tượng mục tiêu",
        "budget_vnd": "Ngân sách",
        "timeline": "Thời gian",
        "specific_requirements": "Yêu cầu cụ thể",
        "constraints": "Ràng buộc",
    }

    assumed_fields = set(getattr(verdict, "assumptions", []) or [])
    groups: dict[str, list[dict]] = {"said": [], "inferred": [], "assumed": []}

    for fieldname, label in labels.items():
        value = getattr(state.brief, fieldname, None) if state.brief else None
        if value in (None, "", [], {}):
            if fieldname in assumed_fields:
                groups["assumed"].append(
                    {"field": fieldname, "label": label, "value": "(chưa có — sẽ phỏng đoán)"}
                )
            continue
        shown = ", ".join(str(v) for v in value) if isinstance(value, list) else str(value)
        bucket = "said" if shown.lower()[:40] in said_text else "inferred"
        groups[bucket].append({"field": fieldname, "label": label, "value": shown})

    return groups


def _build_brief_checkpoint(state, verdict):
    """Chốt 1 card: the brief as understood, grouped by where each item came from."""
    import uuid as _uuid

    from schemas.state import Checkpoint, CheckpointAction

    groups = _classify_brief_sources(state, verdict)
    counts = {k: len(v) for k, v in groups.items()}

    return Checkpoint(
        id=f"cp_brief_{_uuid.uuid4().hex[:10]}",
        action=CheckpointAction(
            type="confirm_brief",
            description=(
                "Mình hiểu brief như dưới đây. Bạn xác nhận giúp trước khi mình "
                "chạy phân tích — sửa bây giờ rẻ hơn sửa sau khi đã có proposal."
            ),
            parameters={"gate_state": verdict.state.value},
            preview={"groups": groups, "counts": counts},
        ),
        preview={"groups": groups, "counts": counts},
    )


def _build_solution_checkpoint(state, outputs):
    """Chốt 2 card: the direction and feasibility verdict, before anything is rendered."""
    import uuid as _uuid

    from schemas.state import Checkpoint, CheckpointAction

    def _head(name: str, limit: int = 900) -> str:
        out = outputs.get(name)
        text = getattr(out, "content", "") if out else ""
        return text[:limit]

    return Checkpoint(
        id=f"cp_solution_{_uuid.uuid4().hex[:10]}",
        action=CheckpointAction(
            type="confirm_solution",
            description=(
                "Đây là hướng giải pháp và phán quyết khả thi. Duyệt thì mình dựng "
                "proposal đầy đủ; muốn đổi hướng thì nói, phần chiến lược và pháp lý "
                "vẫn giữ nguyên."
            ),
            parameters={},
            preview={
                "strategy": _head("market_strategy"),
                "solution": _head("product_solution"),
                "compliance": _head("compliance", 500),
            },
        ),
        preview={
            "strategy": _head("market_strategy"),
            "solution": _head("product_solution"),
            "compliance": _head("compliance", 500),
        },
    )


_VND_UNITS = (
    ("tỷ", 1_000_000_000), ("ty", 1_000_000_000), ("tỉ", 1_000_000_000),
    ("triệu", 1_000_000), ("trieu", 1_000_000), ("tr", 1_000_000),
    ("nghìn", 1_000), ("nghin", 1_000), ("k", 1_000),
)


def _parse_vnd(value: Any) -> Optional[int]:
    """Read a budget out of the way a Vietnamese rep actually writes one.

    Handles "300 triệu", "1.5 tỷ", "200 - 500 triệu", "Dưới 100 triệu",
    "500,000,000" and a bare integer. A range collapses to its midpoint: the top
    of the range risks quoting a client out of the deal, the bottom under-serves
    them, and the original phrasing is preserved in additional_context anyway so
    the pricing skill can still see the spread.

    Returns None when there is no number to find — "chưa chốt" is an answer, not
    a parse failure, and must not be turned into a fabricated figure.
    """
    if isinstance(value, (int, float)):
        return int(value) or None

    text = str(value).lower().strip()
    if not text:
        return None

    # Pair each number with the unit written right after it. A single multiplier
    # for the whole string breaks on mixed ranges: "500 triệu - 1 tỷ" would take
    # "tỷ" for both and land two orders of magnitude out.
    unit_pattern = "|".join(re.escape(t) for t, _ in _VND_UNITS)
    matches = re.findall(rf"(\d[\d.,]*)\s*({unit_pattern})?", text)

    parsed: list[tuple[float, Optional[int]]] = []
    for raw, unit in matches:
        cleaned = raw.rstrip(".,")
        if not cleaned:
            continue
        if re.fullmatch(r"\d{1,3}([.,]\d{3})+", cleaned):
            cleaned = re.sub(r"[.,]", "", cleaned)       # 1.500.000 -> 1500000
        else:
            cleaned = cleaned.replace(",", ".")          # 1,5 -> 1.5
        try:
            number = float(cleaned)
        except ValueError:
            continue
        factor = next((f for t, f in _VND_UNITS if t == unit), None) if unit else None
        parsed.append((number, factor))

    if not parsed:
        return None

    # A bare number in a range borrows the unit of its neighbour: in
    # "200 - 500 triệu" the 200 is plainly also in millions.
    known = [f for _, f in parsed if f]
    fallback = known[0] if known else 1
    amounts = [n * (f or fallback) for n, f in parsed]

    amount = sum(amounts[:2]) / 2 if len(amounts) >= 2 else amounts[0]
    return int(amount) or None


_GANTT_DATE_RE = re.compile(r'\d{4}-\d{2}-\d{2}')
_GANTT_YEAR_RE = re.compile(r'\b(\d{4})\b')


def _fix_gantt(content: str) -> str:
    """Repair gantt task lines with incomplete dates/durations so Mermaid renders correctly.
    Never removes task lines — only fixes their format.

    Common fixes:
    - Year-only date "2024"  → padded to "2024-01-01" (or inferred from prior task end)
    - Missing duration       → appended default "7d"
    """
    from datetime import datetime, timedelta

    def _advance_date(date_str: str, days: int) -> str:
        try:
            return (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=days)).strftime("%Y-%m-%d")
        except ValueError:
            return date_str

    def _fix_block(m: re.Match) -> str:
        lines = m.group(0).split('\n')
        out = []
        last_date = None   # last known valid YYYY-MM-DD
        last_dur = 7       # last known duration in days

        for line in lines:
            stripped = line.strip()
            indent = line[: len(line) - len(line.lstrip())]

            # Non-task lines (fences, directives, sections) — keep as-is with targeted fixes
            if not stripped or stripped.startswith('```'):
                out.append(line)
                continue

            # Fix `dateFormat <actual-date>` → `dateFormat YYYY-MM-DD`
            # LLMs often write the project start date instead of the format pattern.
            if re.match(r'^dateFormat\b', stripped, re.I):
                parts = stripped.split(None, 1)
                if len(parts) == 2 and _GANTT_DATE_RE.fullmatch(parts[1].strip()):
                    out.append(f"{indent}dateFormat YYYY-MM-DD")
                else:
                    out.append(line)
                continue

            # Drop axisFormat — frequently causes parse failures with non-YYYY-MM-DD dateFormat
            if re.match(r'^axisFormat\b', stripped, re.I):
                continue

            if re.match(r'^(title|excludes|section|gantt)', stripped, re.I):
                out.append(line)
                continue

            # Lines without ':' are not task lines
            if ':' not in stripped:
                out.append(line)
                continue

            # Already has a valid date — strip invalid `after <id>` if mixed with explicit date
            if _GANTT_DATE_RE.search(stripped):
                dm = _GANTT_DATE_RE.search(stripped)
                last_date = dm.group(0)
                dur_m = re.search(r'(\d+)d\b', stripped)
                if dur_m:
                    last_dur = int(dur_m.group(1))
                # Remove `after <taskId>` params mixed with an explicit date (invalid syntax)
                if re.search(r'\bafter\s+\w+', stripped, re.I):
                    colon_idx = stripped.index(':')
                    task_name = stripped[:colon_idx]
                    params = [p.strip() for p in stripped[colon_idx + 1:].split(',')]
                    params = [p for p in params if not re.match(r'^after\b', p, re.I)]
                    out.append(f"{indent}{task_name}:{', '.join(params)}")
                else:
                    out.append(line)
                continue

            # --- Task line with invalid/incomplete date → repair ---
            # Split on ':' to separate task name from id/date/duration
            colon_idx = stripped.index(':')
            task_name = stripped[:colon_idx]
            params_raw = stripped[colon_idx + 1:]
            params = [p.strip() for p in params_raw.split(',')]
            # Strip 'during <taskId>' and 'after <taskId>' — not valid when date is absent/malformed
            params = [p for p in params if not re.match(r'^(during|after)\b', p, re.I)]

            # Fix year-only date like "2024"
            fixed_date = None
            for i, p in enumerate(params):
                if _GANTT_DATE_RE.match(p):
                    fixed_date = p
                    break
                if _GANTT_YEAR_RE.fullmatch(p):
                    # Infer date: day after last task ended (or Jan 1 if no context)
                    inferred = _advance_date(last_date, last_dur) if last_date else f"{p}-01-01"
                    params[i] = inferred
                    fixed_date = inferred
                    break

            # If still no date found, infer entirely
            if not fixed_date:
                inferred = _advance_date(last_date, last_dur) if last_date else "2024-01-01"
                # Insert date after the first param (which is usually the id like 'a2')
                if params:
                    params.insert(1, inferred)
                else:
                    params.append(inferred)
                fixed_date = inferred

            # Ensure duration is present (last param should match \d+d)
            if not re.search(r'\d+d\b', params[-1]):
                params.append(f"{last_dur}d")

            fixed_line = f"{indent}{task_name}:{', '.join(params)}"
            out.append(fixed_line)

            # Update context
            last_date = fixed_date
            dur_m = re.search(r'(\d+)d\b', params[-1])
            if dur_m:
                last_dur = int(dur_m.group(1))

        return '\n'.join(out)

    return re.sub(r'```(?:mermaid\s*)?\ngantt[\s\S]*?```', _fix_block, content)


class CentralAgent:
    """Central agent: assess brief completeness, clarify if needed, then dispatch skills."""

    def __init__(self):
        self.name = "central_agent"
        self.model_key = "MODEL_CENTRAL_AGENT"

    @property
    def model_path(self) -> str:
        return os.getenv(self.model_key, os.getenv("MODEL_SALES_ORCHESTRATOR", "minimax/minimax-m2.5"))

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    # Keywords that indicate a user wants a formal proposal/deck/pricing document.
    # Covers common Vietnamese + English phrasing. This list is intentionally broad
    # (false positives waste compute but aren't harmful; false negatives drop user requests).
    _PROPOSAL_INTENT_KWS: frozenset[str] = frozenset({
        # Vietnamese
        "proposal", "báo giá", "báo giá chi tiết", "bảng giá",
        "tổng hợp", "làm deck", "tạo deck", "xuất deck", "xuất proposal",
        "bản trình bày", "bản đề xuất", "tài liệu đề xuất",
        "bản báo cáo", "làm tài liệu", "kế hoạch chi tiết",
        # English
        "deck", "slides", "presentation", "pitch deck", "pitch",
        "quotation", "quote", "estimate", "pricing doc",
        "make deck", "generate deck", "create deck", "build deck",
    })

    def _detect_proposal_intent(self, state: SalesCaseState, message: str) -> bool:
        """Return True if any text source (current msg, history, brief) contains proposal intent."""
        haystack = message.lower()
        for m in state.messages:
            if m.get("role") == "user":
                haystack += " " + (m.get("content") or "").lower()
        if state.brief and state.brief.additional_context:
            haystack += " " + state.brief.additional_context.lower()
        return any(kw in haystack for kw in self._PROPOSAL_INTENT_KWS)

    async def run(
        self, state: SalesCaseState, message: str
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Process a user message.
        Step 0: Pre-scan for proposal intent → update state.desired_outputs (server-side, reliable)
        Step 1: Casual check → greet if casual
        Step 2: Assess brief + plan → either clarify or execute
        Step 3A: If clarification needed → stream questions and stop
        Step 3B: If ready → execute skills in parallel
        Step 4: Synthesize and stream final response
        """
        # Step 0: Reliable server-side proposal intent detection.
        # Can't depend solely on the LLM to output desired_outputs correctly —
        # models often omit new schema fields. Scan all text sources here first,
        # then LLM extraction supplements for unusual paraphrases.
        if self._detect_proposal_intent(state, message) and "proposal" not in state.desired_outputs:
            state.desired_outputs.append("proposal")

        # Is this turn the continuation of an approved confirmation stop?
        #
        # Resuming must not depend on what the rep typed. The frontend sends a short
        # nudge after approval, and "Tiếp tục" is exactly the shape the casual-chat
        # detector matches — so the pipeline greeted the rep instead of carrying on.
        # The approved checkpoint sitting on the session is the real signal.
        resuming = bool(
            state.checkpoint
            and state.checkpoint.status == "APPROVED"
            and state.checkpoint.action.type in ("confirm_brief", "confirm_solution")
        )
        if resuming:
            print(f"[checkpoint] resuming after {state.checkpoint.action.type}")
            state.checkpoint = None  # consumed; a later stop will raise a fresh one

        # Step 1: Quick check — is this just a greeting/casual chat?
        if not resuming and self._is_casual(message):
            response = await self._casual_reply(message)
            yield {"type": "content", "content": response}
            state.messages.append({
                "role": "assistant", "content": response,
                "agent": "central_agent", "timestamp": datetime.now().isoformat(),
            })
            yield {"type": "done"}
            return

        # Step 2: Assess brief completeness + plan (LLM decides clarify vs execute)
        assessment = await self._assess_and_plan(state, message)
        self._apply_brief_update(state, assessment.get("brief_update") or {})

        # Step 2b: THE GATE (BRD §8). The model above extracted information and has an
        # opinion about whether that is enough; this decides. Pure code, no bypass.
        #
        # The planner's `needs_clarification` is now advisory: it can ask for more, but
        # it can no longer wave an incomplete brief through. That inversion is the whole
        # point — previously the only thing standing between a half-empty brief and a
        # priced proposal was a sentence in a prompt.
        verdict = gate.evaluate(
            brief=state.brief,
            message=message,
            intent="brief",
            history=state.messages,
        )
        print(verdict.log_line())

        # Step 2c: the model provider is down. Say so. Every skill uses the same
        # client, so nothing useful can happen this turn, and dressing the outage up
        # as a clarifying question just makes the rep retype their brief.
        if assessment.get("llm_failed"):
            msg = self._service_error_message(message)
            print(f"[CentralAgent] reporting provider outage to user")
            yield {"type": "content", "content": msg}
            state.messages.append({
                "role": "assistant", "content": msg, "agent": "central_agent",
                "kind": "service_error", "timestamp": datetime.now().isoformat(),
            })
            yield {"type": "done"}
            return

        # On a resume the rep has just approved this brief on screen. The planner sees
        # only the short nudge that carried the turn and will often ask for more; that
        # would bounce them straight back to a question they already answered. The gate
        # still applies — it just no longer takes the planner's opinion as a veto.
        must_clarify = not verdict.may_dispatch or (
            bool(assessment.get("needs_clarification")) and not resuming
        )

        # Step 3A: Not cleared to dispatch → ask, and only ask
        if must_clarify:
            clarification_msg = (
                assessment.get("clarification_message")
                or self._fallback_clarification(message)
            )
            if not verdict.may_dispatch and verdict.missing:
                blocking = ", ".join(
                    f"{m.field}" for m in verdict.missing if m.blocking
                )
                print(f"[gate] blocked dispatch — no specialist agent ran. missing: {blocking}")

            # Asking the identical question again teaches the rep nothing. If the last
            # turn was already a clarification and this one added no new field — or the
            # rep just told us they don't know — change tack and offer the assumption
            # route instead of repeating (BRD §10.1: infer, then confirm).
            stuck = self._consecutive_clarifications(state) >= 1
            if (stuck or gate.said_dont_know(message)) and not verdict.may_dispatch:
                clarification_msg = self._escalated_clarification(message, verdict)
                print("[CentralAgent] repeat clarification detected — offering assumption route")

            yield {"type": "content", "content": clarification_msg}

            # Alongside the prose, hand over pickable answers for the fields the gate
            # is actually blocking on. Typing "FMCG" costs a rep more than tapping it,
            # and free text arrives in a hundred spellings that the extractor then has
            # to normalise. The card always carries a free-text option too — a closed
            # list would quietly steer briefs toward whatever we guessed.
            questions = gate.build_questions(verdict)
            if questions:
                state.question_stack = [
                    Question(**q) for q in questions
                ]
                print(f"[gate] offering {len(questions)} pickable question(s): "
                      f"{[q['target_field'] for q in questions]}")
                yield {"type": "question_card", "questions": questions}

            state.messages.append({
                "role": "assistant", "content": clarification_msg,
                "agent": "central_agent", "kind": "clarification",
                "timestamp": datetime.now().isoformat(),
            })
            yield {"type": "done"}
            return

        # Step 3A2 — CHỐT 1 (BRD §11): before spending any specialist work, show the rep
        # what we think they said and let them correct it. Running the whole pipeline
        # first means an error in the first line is only discovered at the last one.
        if "confirm_brief" not in state.confirmed_stages:
            checkpoint = _build_brief_checkpoint(state, verdict)
            state.checkpoint = checkpoint
            print(f"[checkpoint] CHOT 1 raised — awaiting brief confirmation")
            yield {"type": "checkpoint", "checkpoint": checkpoint.model_dump(mode="json")}
            yield {"type": "done"}
            return

        # Step 3B: Cleared → execute skills
        skill_plan: list[list[dict]] = assessment.get("skill_plan") or []

        if not skill_plan:
            skill_plan = _build_contextual_skill_plan(state, message)

        # Safety net: inject assembler + wireframe as a paired parallel group if missing.
        # Both run in parallel: assembler synthesizes the text response, wireframe_designer
        # reads the 4 analysis skill outputs directly to build the deck (no assembler wait).
        if ("proposal" in state.desired_outputs
                and not assessment.get("needs_clarification")
                and "proposal_assembler" not in state.outputs):
            _pa_in_plan = {s.get("skill") for g in skill_plan for s in g}
            if "proposal_assembler" not in _pa_in_plan:
                skill_plan.append([
                    {
                        "skill": "proposal_assembler",
                        "task": (
                            "Tổng hợp toàn bộ phân tích thành proposal hoàn chỉnh: "
                            "giới thiệu giải pháp Zalo, idea game, userflow, "
                            "data reactivation strategy và báo giá chi tiết."
                        ),
                    },
                    {
                        "skill": "wireframe_designer",
                        "task": "Generate HTML deck + PPTX from all skill outputs",
                    },
                ])
            elif "wireframe_designer" not in _pa_in_plan:
                # assembler is already in the plan but wireframe is missing — pair them
                skill_plan = [
                    (group + [{"skill": "wireframe_designer",
                               "task": "Generate HTML deck + PPTX from all skill outputs"}])
                    if any(s.get("skill") == "proposal_assembler" for s in group)
                    else group
                    for group in skill_plan
                ]

        # Snapshot which skills already ran in PRIOR turns (before this execution)
        prior_skill_names: set[str] = set(state.outputs.keys())

        skill_registry = get_skill_registry()
        all_outputs: dict[str, SkillOutput] = {}

        # One ledger for the whole turn: a reference read for the strategy agent is not
        # read again for the product agent, and the §14 log can account for the total.
        ledger = RequestLedger(request_id=f"{state.session_id}:{len(state.messages)}")

        # When the gate let this run on assumptions, every skill is told what is being
        # assumed so the output declares it rather than passing a guess off as fact.
        assumption_note = gate.assumption_notice(verdict)

        def _safe_field(v: Any, field: str, default: Any) -> Any:
            """Safely read a field from either a dict or an object (handles old DB records)."""
            if isinstance(v, dict):
                return v.get(field, default) or default
            return getattr(v, field, default) or default

        for group in skill_plan:
            if not group:
                continue

            # CHỐT 2 (BRD §11): the analysis is done, the render is not. Stop here and
            # show the direction — a proposal built on the wrong direction is the most
            # expensive thing this system can produce.
            is_render_group = any(
                s.get("skill") in ("proposal_assembler", "wireframe_designer") for s in group
            )
            if is_render_group and "confirm_solution" not in state.confirmed_stages:
                merged_now = dict(state.outputs)
                merged_now.update(all_outputs)
                checkpoint = _build_solution_checkpoint(state, merged_now)
                state.checkpoint = checkpoint
                print("[checkpoint] CHOT 2 raised — awaiting solution confirmation")
                yield {"type": "checkpoint", "checkpoint": checkpoint.model_dump(mode="json")}
                break

            tasks: dict[asyncio.Task, str] = {}
            for item in group:
                skill_name = item.get("skill", "")
                task_desc = item.get("task", message)
                skill = skill_registry.get(skill_name)
                if not skill:
                    print(f"[CentralAgent] Skill not found: {skill_name}, skipping")
                    continue

                # Approving a confirmation stop means "carry on", not "start over".
                # The planner rebuilds the full plan on the resume turn, so without this
                # the analysis skills all ran a second time — wasted minutes, and on a
                # rate-limited tier it burned the quota the deck extractor needed next,
                # which is how a proposal ended up with only a cover and a closing slide.
                # Re-running is what a *rejection* is for (BRD §11.3).
                if resuming and skill_name not in _ALWAYS_SEQUENTIAL:
                    prior = state.outputs.get(skill_name)
                    if prior is not None and _safe_field(prior, "status", "") == "COMPLETE":
                        print(f"[CentralAgent] {skill_name}: reusing result from before the checkpoint")
                        continue
                # Merge prior session outputs with current-run group outputs so skills
                # can build on previous analysis when handling follow-up questions.
                merged_previous = {
                    k: {
                        "content": _safe_field(v, "content", ""),
                        "summary": _safe_field(v, "summary", ""),
                        "payload": _safe_field(v, "payload", {}),
                    }
                    for k, v in state.outputs.items()
                }
                merged_previous.update({
                    k: {"content": v.content, "summary": v.summary, "payload": v.payload}
                    for k, v in all_outputs.items()
                })
                ctx = SkillContext(
                    task=task_desc + assumption_note,
                    brief=state.brief,
                    # Keep a wider rolling window here because the session transcript
                    # is the primary source of cross-turn context for re-entrant skills.
                    messages=state.messages[-_RECENT_HISTORY_WINDOW:],
                    previous_outputs=merged_previous,
                    constraints=state.constraints,
                    session_id=state.session_id,
                    ledger=ledger,
                )
                t = asyncio.create_task(
                    asyncio.wait_for(skill.execute(ctx), timeout=_SKILL_TIMEOUT_S)
                )
                tasks[t] = skill_name
                yield {"type": "agent_status", "agent": skill_name, "status": "thinking"}

            if not tasks:
                continue

            pending = set(tasks.keys())
            while pending:
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    skill_name = tasks[task]
                    try:
                        out: SkillOutput = task.result()
                        all_outputs[skill_name] = out
                        state.outputs[skill_name] = AgentOutput(
                            agent=skill_name,
                            status="COMPLETE" if out.status == "COMPLETE" else "FAILED",
                            payload=out.payload,
                            summary=out.summary,
                            content=out.content,
                            confidence=out.confidence,
                        )
                        yield {"type": "agent_status", "agent": skill_name, "status": "completed"}
                    except asyncio.TimeoutError:
                        print(f"[CentralAgent] Skill {skill_name} timed out after {_SKILL_TIMEOUT_S}s")
                        yield {"type": "agent_status", "agent": skill_name, "status": "failed",
                               "message": f"Timed out after {_SKILL_TIMEOUT_S}s"}
                    except Exception as e:
                        print(f"[CentralAgent] Skill {skill_name} error: {e}")
                        yield {"type": "agent_status", "agent": skill_name, "status": "failed",
                               "message": str(e)}

        # Step 3C: Auto-trigger wireframe_designer after proposal_assembler (only if COMPLETE)
        for trigger_skill, auto_skill in _AUTO_AFTER.items():
            trigger_out = all_outputs.get(trigger_skill)
            if (trigger_out and trigger_out.status == "COMPLETE"
                    and trigger_out.content and auto_skill not in all_outputs):
                auto = skill_registry.get(auto_skill)
                if auto:
                    merged_auto = {
                        k: {"content": _safe_field(v, "content", ""),
                            "summary": _safe_field(v, "summary", ""),
                            "payload": _safe_field(v, "payload", {})}
                        for k, v in state.outputs.items()
                    }
                    merged_auto.update({
                        k: {"content": v.content, "summary": v.summary, "payload": v.payload}
                        for k, v in all_outputs.items()
                    })
                    auto_ctx = SkillContext(
                        task="Generate proposal deck assets (HTML deck + PPTX)",
                        brief=state.brief,
                        messages=state.messages[-_RECENT_HISTORY_WINDOW:],
                        previous_outputs=merged_auto,
                        constraints=state.constraints,
                        session_id=state.session_id,
                        ledger=ledger,
                    )
                    yield {"type": "agent_status", "agent": auto_skill, "status": "thinking"}
                    try:
                        auto_out = await asyncio.wait_for(
                            auto.execute(auto_ctx), timeout=_SKILL_TIMEOUT_S
                        )
                        all_outputs[auto_skill] = auto_out
                        state.outputs[auto_skill] = AgentOutput(
                            agent=auto_skill,
                            status="COMPLETE" if auto_out.status == "COMPLETE" else "FAILED",
                            payload=auto_out.payload,
                            summary=auto_out.summary,
                            content=auto_out.content,
                            confidence=auto_out.confidence,
                        )
                        yield {"type": "agent_status", "agent": auto_skill, "status": "completed"}
                    except Exception as e:
                        print(f"[CentralAgent] Auto-skill {auto_skill} error: {e}")
                        yield {"type": "agent_status", "agent": auto_skill, "status": "failed"}

        # Step 3D: Deck-only shortcut — user explicitly requests deck but proposal_assembler
        # was not re-run this turn. If prior assembled content exists, generate deck from it.
        _DECK_REQUEST_KWS = frozenset({
            "deck", "slide", "slides", "pptx", "html deck",
            "làm deck", "tạo deck", "xuất deck", "update deck",
            "làm lại deck", "tạo lại deck", "regenerate deck",
        })
        _msg_lower = message.lower()
        _is_deck_request = any(kw in _msg_lower for kw in _DECK_REQUEST_KWS)
        if _is_deck_request and "wireframe_designer" not in all_outputs:
            prior_pa = state.outputs.get("proposal_assembler")
            if (prior_pa and _safe_field(prior_pa, "status", "") == "COMPLETE"
                    and _safe_field(prior_pa, "content", "")):
                _deck_skill = skill_registry.get("wireframe_designer")
                if _deck_skill:
                    merged_deck = {
                        k: {"content": _safe_field(v, "content", ""),
                            "summary": _safe_field(v, "summary", ""),
                            "payload": _safe_field(v, "payload", {})}
                        for k, v in state.outputs.items()
                    }
                    merged_deck.update({
                        k: {"content": v.content, "summary": v.summary, "payload": v.payload}
                        for k, v in all_outputs.items()
                    })
                    deck_ctx = SkillContext(
                        task="Generate proposal deck assets (HTML deck + PPTX)",
                        brief=state.brief,
                        messages=state.messages[-_RECENT_HISTORY_WINDOW:],
                        previous_outputs=merged_deck,
                        constraints=state.constraints,
                        session_id=state.session_id,
                        ledger=ledger,
                    )
                    yield {"type": "agent_status", "agent": "wireframe_designer", "status": "thinking"}
                    try:
                        deck_out = await asyncio.wait_for(
                            _deck_skill.execute(deck_ctx), timeout=_SKILL_TIMEOUT_S
                        )
                        all_outputs["wireframe_designer"] = deck_out
                        state.outputs["wireframe_designer"] = AgentOutput(
                            agent="wireframe_designer",
                            status="COMPLETE" if deck_out.status == "COMPLETE" else "FAILED",
                            payload=deck_out.payload,
                            summary=deck_out.summary,
                            content=deck_out.content,
                            confidence=deck_out.confidence,
                        )
                        yield {"type": "agent_status", "agent": "wireframe_designer", "status": "completed"}
                    except Exception as e:
                        print(f"[CentralAgent] Deck-only wireframe_designer error: {e}")
                        yield {"type": "agent_status", "agent": "wireframe_designer", "status": "failed"}

        # §14: one line per turn accounting for the knowledge that reached the prompts.
        print(f"[knowledge] turn {ledger.request_id}: {ledger.summary()}")
        print(f"[agents] ran: {', '.join(all_outputs.keys()) or 'none'}")

        # Step 4: Synthesize final response
        if all_outputs:
            async for event in self._synthesize(state, message, all_outputs, prior_skill_names):
                yield event
        else:
            yield {"type": "content", "content": "Xin lỗi, các skill không trả về kết quả. Vui lòng thử lại."}

        yield {"type": "done"}

    # ------------------------------------------------------------------
    # Assessment + Planning
    # ------------------------------------------------------------------

    async def _assess_and_plan(self, state: SalesCaseState, message: str) -> dict[str, Any]:
        """
        Assess brief completeness and return either:
        - {"needs_clarification": True, "clarification_message": "..."} → ask questions
        - {"needs_clarification": False, "skill_plan": [...]} → execute skills
        Falls back to execute mode if LLM fails.
        """
        try:
            return await self._plan(state, message)
        except Exception as e:
            # Flag it. Previously this returned a normal "execute" result, so a dead
            # provider was indistinguishable from a real plan — the turn fell through
            # to the canned clarification and the rep saw the same paragraph every
            # time with no hint that anything was wrong.
            print(f"[CentralAgent] Assessment LLM failed ({e}) — cannot plan this turn")
            return {
                "brief_update": {},
                "needs_clarification": False,
                "llm_failed": True,
                "llm_error": str(e),
                "skill_plan": _build_contextual_skill_plan(state, message),
            }

    @staticmethod
    def _format_prior_skills(state: SalesCaseState) -> str:
        """Summarize which skills ran this session and what they found."""
        if not state.outputs:
            return ""
        lines = []
        for skill_name, output in state.outputs.items():
            summary = (output.summary or "")[:200].replace("\n", " ")
            lines.append(f"- {skill_name} ({output.status}): {summary}")
        return "\n".join(lines)

    async def _plan(self, state: SalesCaseState, message: str) -> dict[str, Any]:
        """Single LLM call: match the brief to available skills, decide clarify or execute."""
        from llm.greennode import get_llm_client

        client = get_llm_client("central_agent")

        # Build a live skill catalog from the registry — no hardcoded skill names.
        # Exclude auto-triggered skills from the LLM's planning catalog.
        _EXCLUDE_FROM_PLAN = {"wireframe_designer"}
        registry = get_skill_registry()
        skill_catalog = "\n".join(
            f"  {name}: {desc}"
            for name, desc in registry.descriptions().items()
            if name not in _EXCLUDE_FROM_PLAN
        )
        system_prompt = _PLANNING_SYSTEM_TEMPLATE.format(skill_catalog=skill_catalog)

        # Prepend the orchestrator's own SKILL.md — identity, greeting behaviour,
        # elicitation stance and routing rules. It was being loaded at import and then
        # never used, so none of it had reached a prompt; the planner was running on the
        # template alone.
        if _CENTRAL_SKILL:
            system_prompt = f"{_CENTRAL_SKILL}\n\n---\n\n{system_prompt}"

        brief_block = self._format_brief(state.brief)
        history_block = self._format_history(state.messages[-_RECENT_HISTORY_WINDOW:])
        prior_skills_block = self._format_prior_skills(state)

        user_prompt = ""
        if history_block:
            user_prompt += f"## Conversation History\n{history_block}\n\n"
        if brief_block and brief_block != "No brief yet.":
            user_prompt += f"## Accumulated Brief\n{brief_block}\n\n"
        if prior_skills_block:
            user_prompt += f"## Already Executed This Session\n{prior_skills_block}\n\n"
        user_prompt += f"## Current Message\n{message}\n\nReturn JSON."

        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            partial(
                client.create_completion,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=3000,
                stream=False,
            ),
        )

        raw = response.choices[0].message.content or "{}"
        raw = strip_think_blocks(raw)
        raw = extract_json_block(raw)

        result = json.loads(raw)

        # Option B: allow up to 2 clarification rounds, then always execute.
        # Round 0 (0 assistant turns): may clarify if info missing.
        # Round 1 (1 assistant turn = first clarification): may clarify once more.
        # Round 2+ (2+ assistant turns): execute regardless — don't over-ask.
        prior_assistant_turns = [m for m in state.messages if m.get("role") == "assistant"]
        if len(prior_assistant_turns) >= 2 and result.get("needs_clarification"):
            result["needs_clarification"] = False

        # Accumulate desired_outputs into state — this makes proposal intent sticky across turns.
        # The LLM semantically detects intent ("bản trình bày", "slides", "báo giá", etc.)
        # regardless of exact phrasing; keyword matching would miss paraphrases.
        for _desired in (result.get("desired_outputs") or []):
            if _desired and _desired not in state.desired_outputs:
                state.desired_outputs.append(_desired)

        # One-time enforcement: if proposal was requested this session AND proposal_assembler
        # hasn't run yet → add it to the plan now.
        # This bridges the gap where the user asked for a proposal in a prior turn but the
        # current message is just answering clarification questions (no proposal keyword present),
        # so the LLM doesn't re-detect the intent.
        # The "not in state.outputs" guard ensures this fires ONCE only — never again after
        # proposal_assembler completes.
        if ("proposal" in state.desired_outputs
                and not result.get("needs_clarification")
                and result.get("skill_plan")
                and "proposal_assembler" not in state.outputs):
            _planned_skills = {s.get("skill") for g in result["skill_plan"] for s in g}
            if "proposal_assembler" not in _planned_skills:
                result["skill_plan"].append([
                    {
                        "skill": "proposal_assembler",
                        "task": (
                            "Tổng hợp toàn bộ phân tích thành proposal hoàn chỉnh: "
                            "giới thiệu giải pháp Zalo, idea game, userflow, "
                            "data reactivation strategy và báo giá chi tiết."
                        ),
                    },
                    {
                        "skill": "wireframe_designer",
                        "task": "Generate HTML deck + PPTX from all skill outputs",
                    },
                ])
            elif "wireframe_designer" not in _planned_skills:
                # assembler is already in the LLM plan but wireframe is missing — pair into same group
                result["skill_plan"] = [
                    (group + [{"skill": "wireframe_designer",
                               "task": "Generate HTML deck + PPTX from all skill outputs"}])
                    if any(s.get("skill") == "proposal_assembler" for s in group)
                    else group
                    for group in result["skill_plan"]
                ]

        # Safety net: if LLM returned execute but no skill_plan, build from session state.
        if not result.get("needs_clarification") and not result.get("skill_plan"):
            result["skill_plan"] = _build_contextual_skill_plan(state, message)

        # Validate that all skill names in the plan exist in the registry.
        # Drop any hallucinated skill names silently.
        valid_skill_names = set(registry.all_names())
        if result.get("skill_plan"):
            result["skill_plan"] = [
                [s for s in group if s.get("skill") in valid_skill_names]
                for group in result["skill_plan"]
            ]
            # Drop empty groups
            result["skill_plan"] = [g for g in result["skill_plan"] if g]
            # If everything was stripped, fallback
            if not result["skill_plan"]:
                result["skill_plan"] = _build_contextual_skill_plan(state, message)

            # Enforce sequential skills: pull them out of any mixed group and
            # append them as their own final group so they always run after others.
            plan = result["skill_plan"]
            sequential_entries: list[dict] = []
            cleaned: list[list[dict]] = []
            for group in plan:
                regular = [s for s in group if s.get("skill") not in _ALWAYS_SEQUENTIAL]
                pulled  = [s for s in group if s.get("skill") in _ALWAYS_SEQUENTIAL]
                if regular:
                    cleaned.append(regular)
                sequential_entries.extend(pulled)
            if sequential_entries:
                cleaned.append(sequential_entries)
            result["skill_plan"] = cleaned

        return result

    @staticmethod
    def _consecutive_clarifications(state: SalesCaseState) -> int:
        """How many clarification turns we have just sent in a row.

        Counts back from the end, stopping at the first assistant turn that was not a
        clarification. Used to notice we are asking the same thing twice.
        """
        count = 0
        for m in reversed(state.messages):
            if m.get("role") != "assistant":
                continue
            if m.get("kind") == "clarification":
                count += 1
                continue
            break
        return count

    def _escalated_clarification(self, message: str, verdict) -> str:
        """Second attempt at the same question — offer to proceed on assumptions.

        A rep who did not answer the first time usually cannot: the information sits
        with their client. Repeating the question strands them. Naming what we would
        assume and how to accept it gives them a way forward (BRD §8.2).
        """
        vi = bool(self._VI_CHARS.search(message) or self._VI_TOKENS.search(message))
        missing = [m for m in verdict.missing if m.blocking] or verdict.missing

        if vi:
            lines = [
                "Nếu giờ chưa có mấy thông tin này thì không sao — mình vẫn chạy được, "
                "chỉ là sẽ chạy trên giả định và ghi rõ chỗ nào đang đoán.",
                "",
                "**Mình sẽ giả định:**",
            ]
            for m in missing:
                lines.append(f"- **{m.field}** — chưa có, mình lấy mặc định phổ biến nhất cho tình huống này")
            lines += [
                "",
                'Bạn nhắn **"cứ làm đi"** là mình chạy luôn với giả định trên. '
                "Còn nếu tiện hỏi khách thì chỉ cần ngành hàng và mục tiêu là đủ để mình "
                "ra được phán quyết khả thi chính xác.",
            ]
            return "\n".join(lines)

        lines = [
            "No problem if you don't have these yet — I can still run, I'll just work "
            "from assumptions and label every one of them.",
            "",
            "**I would assume:**",
        ]
        for m in missing:
            lines.append(f"- **{m.field}** — not given, I'll take the most common default")
        lines += [
            "",
            'Reply **"just do it"** and I\'ll go ahead on those. If you can check with the '
            "client, industry and objective alone are enough for an accurate feasibility call.",
        ]
        return "\n".join(lines)

    def _service_error_message(self, message: str) -> str:
        """Told plainly, because a fake question wastes the rep's time."""
        vi = bool(self._VI_CHARS.search(message) or self._VI_TOKENS.search(message))
        if vi:
            return (
                "Mình đang không kết nối được tới dịch vụ mô hình nên chưa xử lý được "
                "yêu cầu này. Đây là sự cố hệ thống, không phải do brief của bạn thiếu "
                "gì cả — bạn thử lại sau ít phút giúp mình nhé. Nếu vẫn lỗi thì báo team "
                "kỹ thuật kiểm tra API key."
            )
        return (
            "I can't reach the model service right now, so I couldn't process this. "
            "That's a system problem, not anything missing from your brief — please try "
            "again in a few minutes, and if it persists, ask the tech team to check the "
            "API key."
        )

    def _fallback_clarification(self, message: str) -> str:
        """Fallback clarification message when LLM fails to generate one."""
        lang = "vi" if (self._VI_CHARS.search(message) or self._VI_TOKENS.search(message)) else "en"
        if lang == "vi":
            return (
                "Để mình có thể tư vấn giải pháp phù hợp nhất, bạn có thể chia sẻ thêm một chút:\n\n"
                "1. **Ngành hàng / lĩnh vực** brand đang hoạt động? (FMCG, dược phẩm, F&B, bán lẻ...)\n"
                "2. **Mục tiêu chính** của campaign / chương trình này là gì? "
                "(thu data khách hàng, tăng loyalty, tăng doanh số...)\n"
                "3. Brand hiện **đang có chương trình nào tương tự chưa**, "
                "hay đây là lần đầu tiên triển khai trên Zalo?\n\n"
                "Dù chỉ 1–2 dòng mô tả cũng được — mình sẽ phân tích ngay!"
            )
        return (
            "To give you the most relevant recommendation, could you share:\n\n"
            "1. **Industry / sector** the brand operates in? (FMCG, pharma, F&B, retail...)\n"
            "2. **Primary objective** of this campaign or program? "
            "(data capture, loyalty, sales increase, awareness...)\n"
            "3. Does the brand **already have any loyalty/CRM program**, "
            "or is this a fresh start on Zalo?\n\n"
            "Even 1–2 sentences is enough — I'll take it from there!"
        )

    # ------------------------------------------------------------------
    # Synthesis
    # ------------------------------------------------------------------

    async def _synthesize(
        self,
        state: SalesCaseState,
        original_message: str,
        skill_outputs: dict[str, SkillOutput],
        prior_skill_names: set[str] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream a synthesized final response from all skill outputs."""
        from llm.greennode import get_llm_client
        from main import _ThinkFilter

        proposal_out = skill_outputs.get("proposal_assembler")
        if proposal_out and proposal_out.content:
            # proposal_assembler ran and produced content → stream it as the full response.
            content = _fix_gantt(proposal_out.content)
            yield {"type": "content", "content": content}
            state.messages.append({
                "role": "assistant", "content": content,
                "agent": "central_agent", "timestamp": datetime.now().isoformat(),
            })
            return

        outputs_block = "\n\n".join(
            f"### {name}\n{out.content}"
            for name, out in skill_outputs.items()
            if out.content
        )
        # Detect whether this is the first response or a targeted follow-up.
        # Prior assistant turns = this is a follow-up; the user already has the full picture.
        is_followup = any(m.get("role") == "assistant" for m in state.messages)

        if not outputs_block.strip():
            if not is_followup:
                # First call with no skill output — show error
                msg = "Xin lỗi, mình chưa tổng hợp được kết quả phân tích. Bạn thử gửi lại câu hỏi không?"
                yield {"type": "content", "content": msg}
                state.messages.append({
                    "role": "assistant", "content": msg,
                    "agent": "central_agent", "timestamp": datetime.now().isoformat(),
                })
                return
            # Follow-up with no new skill output — synthesizer can still answer from history
            outputs_block = "(Không có phân tích mới từ chuyên gia — trả lời dựa trên ngữ cảnh hội thoại đã có.)"

        if not is_followup:
            system = """You are the AdtimaBox Sales AI — final proposal writer.
Given specialist analysis from multiple skill modules, assemble ONE cohesive proposal document.

Language rule: Match the user's language. Vietnamese brief → respond fully in Vietnamese.

Output structure (use ALL sections that have relevant content):
1. **Tóm tắt đề xuất** — 3–4 sentence executive summary: what we recommend and why
2. **Phân tích chiến lược** — key strategic insights, market context, consumer insight
3. **Giải pháp Zalo** — recommended solution with user journey (include Mermaid diagrams AS-IS)
4. **Báo giá ước tính** — pricing table if available
5. **Compliance & lưu ý pháp lý** — policy notes (only if compliance skill flagged something)
6. **Bước tiếp theo** — 3–5 concrete next steps

Format rules:
- Use ## for section headers, ### for sub-sections
- Be specific to this brief/brand — no generic filler
- Do NOT mention "skill", "agent", "module", or internal pipeline names

OUTPUT FORMAT GUIDE — follow these exactly so the UI renders correctly:

TABLES (comparison data, pricing, feature lists):
  Use standard Markdown pipe tables:
  | Column A | Column B | Column C |
  |----------|----------|----------|
  | value    | value    | value    |
  NEVER use ASCII box-drawing characters (┌─┐│└┘├┤) for tables.

BAR CHARTS (budget breakdown, allocation, percentages):
  Always wrap in a ``` plain code block. Use ONLY this format:
  ```
  ┌─────────────────────────────────────────┐
  │  BUDGET BREAKDOWN                       │
  ╠═════════════════════════════════════════╣
  │  35%  MiniApp Development               │
  │  25%  Voucher System                    │
  │  15%  ZNS/Ads                           │
  └─────────────────────────────────────────┘
  ```
  Rules: percentage FIRST then label on same line. NEVER use █ block chars. NEVER put a box inside another box.

INFO BOXES (game concepts, form wireframes, feature lists, structured text):
  Always wrap in a ``` plain code block. Use ONLY this format:
  ```
  ┌─────────────────────────────────────────┐
  │  TITLE HERE                             │
  ├─────────────────────────────────────────┤
  │  🎮 Section heading:                    │
  │  • Bullet point one                     │
  │  • Bullet point two                     │
  │                                         │
  │  □ Checkbox item                        │
  └─────────────────────────────────────────┘
  ```
  Rules: ONE level of box only — NEVER nest a box inside another box. Use ├──┤ separator (not ╠═╣) for info boxes.

DIAGRAMS (user flows, architecture):
  Use Mermaid in a ```mermaid block. Copy AS-IS from specialist outputs when available.
  If writing new Mermaid: node labels must be SHORT plain text (max 5 words, no <br/> or HTML, no | { } in labels).
  Edge labels: A -->|Label|B pipe syntax only — NEVER spaces.
  NEVER write placeholder blocks with only a label like "Mermaid User Journey".
  If no Mermaid code is available, describe the flow as a numbered list instead.
  MULTI-PARTY FLOWS (User + Staff, Customer + System): use `sequenceDiagram` — NEVER a two-column ASCII box.

TIMELINES / GANTT:
  Use Mermaid gantt syntax in a ```mermaid block. Copy AS-IS from specialist outputs.
  If writing new gantt: every task needs full date (YYYY-MM-DD) and duration (Nd). No partial lines.
  Write `dateFormat YYYY-MM-DD` EXACTLY — NEVER put an actual date here (e.g. NEVER `dateFormat 2024-09-01`).
  NEVER use `after <taskId>` — use explicit absolute dates only. NEVER include `axisFormat`.
  If gantt would be complex, use a Markdown table instead."""

            user_msg = (
                f"## Original Request\n{original_message}\n\n"
                f"## Specialist Outputs\n{outputs_block}\n\n"
                "Assemble into a complete proposal document following the structure above."
            )
        else:
            # Follow-up mode: the user already received the full analysis.
            # Respond ONLY to what they specifically asked about — do not rebuild the whole document.
            system = """You are the AdtimaBox Sales AI — follow-up responder.
The user already received a full initial analysis. They are now asking for something specific.

Your job: respond ONLY to what they asked about in the Current Request.
- Do NOT restate the whole proposal or repeat sections that were already covered.
- DO go deeper, add detail, add examples, or clarify the specific aspects they asked about.
- If they asked about 2 topics, cover both thoroughly.
- Start directly with the content — no "As I mentioned before..." preamble.
- Language: match the user's language (Vietnamese if they wrote in Vietnamese).
- Do NOT mention "skill", "agent", "module", or internal pipeline names.

ALWAYS CLOSE WITH WHAT HAPPENS NEXT. Never end on an explanation and leave the rep
guessing whether it is their turn. Finish with a short `**Tiếp theo:**` line that says
either what you need from them to continue, or what you can produce next and how to
ask for it. One or two sentences — concrete, not "let me know if you need anything".
  Good:  **Tiếp theo:** cho mình ngân sách dự kiến là mình ra được báo giá chi tiết.
  Good:  **Tiếp theo:** nói "làm proposal" là mình dựng bản đầy đủ kèm deck PPTX.
  Bad:   Hy vọng thông tin trên hữu ích cho bạn!

OUTPUT FORMAT GUIDE — follow these exactly so the UI renders correctly:
TABLES: Markdown pipe tables — NEVER ASCII box-drawing for tables.
BAR CHARTS: ``` plain block, ┌─╠═─┘ box, "NN%  Label" per line — NEVER █ block chars.
INFO BOXES: ``` plain block, ┌─├─┘ box (├──┤ separator), bullet/checkbox lines — NEVER nested boxes.
DIAGRAMS: ```mermaid block. Node labels: short plain text only — NO <br/> NO HTML NO | { } in labels.
  Edge labels: -->|Label| pipe syntax only. Max ~12 nodes. If none available, use numbered list.
  Multi-party flows (User + Staff): use sequenceDiagram — NEVER two-column ASCII box.
TIMELINES: ```mermaid gantt block. Every task: Name :id, YYYY-MM-DD, Nd format required.
  Write `dateFormat YYYY-MM-DD` EXACTLY — NEVER an actual date. NEVER `after <taskId>`. NEVER `axisFormat`.
  If gantt would be complex or dates uncertain, use a Markdown table instead."""

            # Include recent conversation history so the synthesizer knows what was already covered.
            history_lines = []
            for m in state.messages[-_SYNTHESIS_HISTORY_WINDOW:]:
                role = m.get("role", "")
                content = (m.get("content") or "")[:800]
                if role == "user":
                    history_lines.append(f"User: {content}")
                elif role == "assistant":
                    history_lines.append(f"Assistant: {content}")
            history_block = "\n\n".join(history_lines)

            user_msg = (
                f"## Conversation So Far\n{history_block}\n\n"
                f"## Current Request\n{original_message}\n\n"
                f"## New Analysis (respond based on this)\n{outputs_block}\n\n"
                "Respond directly to the Current Request. Be thorough on the specific topics asked. "
                "Do not repeat what was already covered in the previous response."
            )

        client = get_llm_client("central_agent")
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue(maxsize=8192)
        _DONE = object()

        def _stream_worker() -> None:
            def _safe_put(item: Any) -> None:
                try:
                    queue.put_nowait(item)
                except Exception as qe:
                    print(f"[CentralAgent] Synthesis queue overflow: {qe}")

            try:
                stream = client.create_completion(
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user_msg},
                    ],
                    temperature=0.5,
                    max_tokens=6000,
                    stream=True,
                )
                for chunk in stream:
                    loop.call_soon_threadsafe(_safe_put, chunk)
            except Exception as exc:
                loop.call_soon_threadsafe(_safe_put, exc)
            finally:
                loop.call_soon_threadsafe(_safe_put, _DONE)

        producer = loop.run_in_executor(None, _stream_worker)

        tf = _ThinkFilter()
        accumulated = ""
        _TOKEN_TIMEOUT = 180.0

        try:
            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=_TOKEN_TIMEOUT)
                except asyncio.TimeoutError:
                    print("[CentralAgent] Synthesis: no token received for 60s, aborting stream")
                    break

                if item is _DONE:
                    break

                if isinstance(item, Exception):
                    print(f"[CentralAgent] Synthesis stream error: {item}")
                    for name, out in skill_outputs.items():
                        if out.content:
                            yield {"type": "content", "content": f"\n\n## {name.replace('_', ' ').title()}\n{out.content}"}
                    return

                if item.choices and item.choices[0].delta.content:
                    token = item.choices[0].delta.content
                    for kind, text in tf.push(token):
                        if kind == "think_start":
                            yield {"type": "thinking_start"}
                        elif kind == "think_end":
                            yield {"type": "thinking_end"}
                        elif kind == "content" and text:
                            accumulated += text
                            yield {"type": "content", "content": text}
        finally:
            await producer

        for kind, text in tf.flush():
            if kind == "content" and text:
                accumulated += text
                yield {"type": "content", "content": text}

        if accumulated:
            state.messages.append({
                "role": "assistant",
                "content": accumulated,
                "agent": "central_agent",
                "timestamp": datetime.now().isoformat(),
            })

    # ------------------------------------------------------------------
    _CASUAL_PATTERNS = re.compile(
        r"^("
        r"hi+|hello+|hey+|howdy|yo+|sup|what'?s up|whats up|how are you|how r u|hru|"
        r"good morning|good afternoon|good evening|good day|good night|morning|evening|"
        r"ok+|okay|k+|kk|cool|nice|great|awesome|perfect|sounds good|"
        r"thanks?|thank you|ty|thx|cheers|much appreciated|appreciate it|"
        r"bye|goodbye|see ya|ttyl|later|cya|"
        r"ready|let'?s go|let'?s start|sure|got it|understood|noted|will do|"
        r"xin chào|chào|chào bạn|chào buổi sáng|chào buổi chiều|chào buổi tối|"
        r"alo|hello bạn|hi bạn|"
        r"cảm ơn|cảm ơn bạn|cảm ơn nhiều|cám ơn|"
        r"được rồi|được|ổn rồi|ổn|tốt rồi|tốt|tuyệt|tuyệt vời|hay quá|ngon|"
        r"sẵn sàng|bắt đầu|bắt đầu thôi|bắt đầu nào|bắt đầu đi|"
        r"tiếp tục|tiếp|tiếp đi|tiếp thôi|"
        r"hiểu rồi|rõ rồi|nhận được|rõ|ừ|ừm|vâng|dạ|dạ bạn|"
        r"tạm biệt|hẹn gặp lại|bái bai|"
        r"xin chao|chao ban|cam on|ok|oke|okie|duoc|tuyet|san sang|vang|da|tam biet|"
        r"bat dau|bat dau thoi|tiep tuc|tiep"
        r")[\s!.?🙏👋😊🎉✨]*$",
        re.IGNORECASE,
    )

    _VI_CHARS = re.compile(
        r"[àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ]",
        re.IGNORECASE,
    )
    _VI_TOKENS = re.compile(
        r"\b(xin|chao|ban|cam|oke|vang|tuyet|duoc|biet|nhan|tam|biet|buoi|sang|chieu|toi)\b",
        re.IGNORECASE,
    )

    _REPLIES_VI = [
        (
            "Xin chào! 👋 Mình là **AdtimaBox Sales AI** — trợ lý tư vấn giải pháp Zalo của Adtima.\n\n"
            "Bạn đang có chiến dịch nào cần tư vấn không? Mình có thể giúp:\n"
            "- Phân tích thị trường & ý tưởng campaign\n"
            "- Thiết kế user journey trên Zalo MiniApp\n"
            "- Báo giá gói CShub & add-ons\n\n"
            "Cứ chia sẻ brief — dù sơ lược cũng được, mình sẽ phân tích ngay! 🚀"
        ),
        (
            "Chào bạn! 😊 Mình là **AdtimaBox Sales AI**.\n\n"
            "Hôm nay bạn đang phụ trách chiến dịch hay brand nào vậy? "
            "Chia sẻ brief với mình — mình sẽ đề xuất giải pháp Zalo phù hợp nhất cho mục tiêu của bạn."
        ),
        (
            "Hello! ✨ Mình là **AdtimaBox Sales AI** của Adtima.\n\n"
            "Bạn muốn bắt đầu từ đâu?\n"
            "- Có brief chiến dịch → mình phân tích & lên giải pháp\n"
            "- Chưa có brief → mình hỏi thêm để hiểu nhu cầu\n"
            "- Muốn xem báo giá → mình tạo bảng giá ước tính\n\n"
            "Cứ nhắn là mình hỗ trợ ngay nhé! 💪"
        ),
        (
            "Chào! 🙌 Sẵn sàng hỗ trợ bạn rồi.\n\n"
            "Mình là **AdtimaBox Sales AI** — chuyên tư vấn giải pháp marketing trên nền tảng Zalo. "
            "Bạn đang có brief hay yêu cầu gì muốn mình xử lý không?"
        ),
        (
            "Xin chào bạn! 👋\n\n"
            "Mình là **AdtimaBox Sales AI**. Để mình giúp bạn hiệu quả nhất, "
            "bạn có thể chia sẻ:\n"
            "- **Ngành hàng / brand** bạn đang phụ trách\n"
            "- **Mục tiêu** chiến dịch (thu data, tăng traffic OA, gamification…)\n"
            "- **Ngân sách** ước tính nếu có\n\n"
            "Mình sẽ đề xuất giải pháp ngay! ✨"
        ),
        (
            "Chào! Mình đây — **AdtimaBox Sales AI** 🤖\n\n"
            "Gửi brief cho mình nhé — dù chỉ 1-2 dòng mô tả campaign cũng được. "
            "Mình sẽ phân tích và trả về đề xuất chi tiết về giải pháp Zalo, user flow, và báo giá."
        ),
    ]

    _REPLIES_EN = [
        (
            "Hey there! 👋 I'm **AdtimaBox Sales AI** — Adtima's Zalo ecosystem advisor.\n\n"
            "What can I help you with today? I can:\n"
            "- Analyze your market & propose campaign ideas\n"
            "- Design a Zalo MiniApp user journey\n"
            "- Generate a pricing estimate for CShub packages\n\n"
            "Just drop your brief and I'll get to work! 🚀"
        ),
        (
            "Hello! 😊 I'm **AdtimaBox Sales AI**.\n\n"
            "What campaign or brand are you working on? "
            "Share a brief — even a rough one — and I'll put together a tailored Zalo solution for you."
        ),
        (
            "Hi! ✨ I'm **AdtimaBox Sales AI** by Adtima.\n\n"
            "Where would you like to start?\n"
            "- Have a brief → I'll analyze and propose a solution\n"
            "- No brief yet → I'll ask a few questions to scope it\n"
            "- Need pricing → I'll generate an estimate right away\n\n"
            "Just let me know! 💪"
        ),
        (
            "Hey! 🙌 Ready to help.\n\n"
            "I'm **AdtimaBox Sales AI** — specialized in Zalo marketing solutions. "
            "Got a brief or a request you'd like me to work on?"
        ),
        (
            "Hello there! 👋\n\n"
            "I'm **AdtimaBox Sales AI**. To give you the best recommendation, feel free to share:\n"
            "- **Industry / brand** you're working with\n"
            "- **Campaign objective** (data capture, OA traffic, gamification…)\n"
            "- **Estimated budget** if you have one\n\n"
            "I'll come back with a full proposal! ✨"
        ),
        (
            "Hi! I'm **AdtimaBox Sales AI** 🤖\n\n"
            "Send me your brief — even just 1-2 lines describing the campaign. "
            "I'll analyze it and return a detailed Zalo solution with user flow and pricing."
        ),
    ]

    def _is_casual(self, message: str) -> bool:
        stripped = message.strip()
        return bool(self._CASUAL_PATTERNS.match(stripped)) and len(stripped) < 60

    async def _casual_reply(self, message: str) -> str:
        lang = "vi" if (self._VI_CHARS.search(message) or self._VI_TOKENS.search(message)) else "en"
        pool = self._REPLIES_VI if lang == "vi" else self._REPLIES_EN
        return random.choice(pool)

    # ------------------------------------------------------------------
    # Compat endpoints (for /chat/answer, /chat/skip_question)
    # ------------------------------------------------------------------

    async def handle_validation_response(
        self, state: SalesCaseState, answers: dict[str, str]
    ) -> AgentOutput:
        if not state.brief:
            state.brief = Brief()
        for q in state.question_stack:
            if q.id in answers and answers[q.id]:
                q.mark_answered(answers[q.id])
                self._apply_field(state.brief, q.target_field, answers[q.id])
        free_text = answers.get("free_text")
        if free_text:
            self._apply_brief_update(state, await self._extract_brief_from_text(state, free_text))

        # Drop only what was actually answered. Clearing the whole stack meant
        # answering the first of three questions silently discarded the other two,
        # so the rep tapped one chip and the rest of the card vanished.
        remaining = [q for q in state.question_stack if not q.answered]
        state.question_stack = [] if free_text else remaining

        status = "READY" if not state.question_stack else "PENDING"
        state.validation_status = status
        return AgentOutput(
            agent="central_agent",
            status="COMPLETE",
            payload={},
            summary="Ready to proceed." if status == "READY" else "More answers needed.",
            confidence=0.9,
            questions=[q.model_dump(mode="json") for q in state.question_stack],
        )

    async def extract_desired_outputs(self, answer: str) -> list[str]:
        """Determine which output artifacts the user wants. Uses LLM — no keyword matching."""
        from llm.greennode import get_llm_client
        system = (
            "You are a parser. The user described what output artifact(s) they want. "
            "Return ONLY a JSON array of strings from this set: [\"pptx\", \"figma\", \"userflow\", \"quote\"]. "
            "pptx = presentation/slide deck. figma = wireframe/UI design. "
            "userflow = user journey / flow diagram / Mermaid diagram. quote = pricing table / báo giá. "
            "Include all that apply. If unclear, return [\"pptx\"]. No explanation — JSON array only."
        )
        try:
            client = get_llm_client("central_agent")
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                partial(
                    client.create_completion,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": answer},
                    ],
                    temperature=0,
                    max_tokens=64,
                    stream=False,
                ),
            )
            raw = (response.choices[0].message.content or "").strip()
            raw = strip_think_blocks(raw)
            raw = extract_json_block(raw)
            parsed = json.loads(raw)
            if isinstance(parsed, list) and all(isinstance(x, str) for x in parsed):
                valid = {"pptx", "figma", "userflow", "quote"}
                result = [x for x in parsed if x in valid]
                return result or ["pptx"]
        except Exception as e:
            print(f"[CentralAgent] extract_desired_outputs LLM failed ({e}), using pptx default")
        return ["pptx"]

    async def validate_before_dispatch(self, state: SalesCaseState):
        output = AgentOutput(
            agent="central_agent",
            status="COMPLETE",
            payload={},
            summary="Ready",
            confidence=0.9,
            questions=[],
        )
        state.validation_status = "READY"
        return output, True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _apply_brief_update(self, state: SalesCaseState, brief_update: dict) -> None:
        if not brief_update:
            return
        if not state.brief:
            state.brief = Brief()
        for field, value in brief_update.items():
            if value is not None:
                self._apply_field(state.brief, field, value)

    @staticmethod
    def _apply_field(brief: Brief, field: str, value: Any) -> None:
        if not value:
            return
        if field == "industry" and not brief.industry:
            brief.industry = str(value)
        elif field == "goal" and not brief.goal:
            brief.goal = str(value)
        elif field == "target_audience" and not brief.target_audience:
            brief.target_audience = str(value)
        elif field == "budget_vnd" and not brief.budget_vnd:
            # Answers arrive as human phrases — "200 - 500 triệu", "Trên 1 tỷ" — from
            # the choice chips as much as from typing. int() on those raised and was
            # swallowed, so a budget the rep had explicitly picked never reached the
            # brief and the gate kept asking for it.
            parsed = _parse_vnd(value)
            if parsed:
                brief.budget_vnd = parsed
            # Keep the phrasing either way: a range carries intent that one number
            # cannot, and "chưa chốt" is itself worth telling the pricing skill.
            brief.additional_context = (
                (brief.additional_context or "") + f" Ngân sách khách nói: {value}."
            ).strip()
        elif field == "timeline" and not brief.timeline:
            brief.timeline = str(value)
        elif field == "additional_context":
            brief.additional_context = ((brief.additional_context or "") + " " + str(value)).strip()
        elif field in ("specific_requirements", "constraints"):
            # A chip answers with a string; only the LLM path produces a list. The
            # list-only check silently dropped every chip for these two fields.
            incoming = value if isinstance(value, list) else [str(value)]
            current = list(getattr(brief, field) or [])
            setattr(brief, field, current + [v for v in incoming if v not in current])

    async def _extract_brief_from_text(self, state: SalesCaseState, text: str) -> dict:
        from llm.greennode import get_llm_client
        client = get_llm_client("central_agent")
        loop = asyncio.get_running_loop()
        try:
            response = await loop.run_in_executor(
                None,
                partial(
                    client.create_completion,
                    messages=[
                        {"role": "system", "content": "Extract brief fields from text. Return JSON only: industry, goal, target_audience, budget_vnd (number|null), timeline, additional_context."},
                        {"role": "user", "content": text},
                    ],
                    temperature=0.1, max_tokens=300, stream=False,
                ),
            )
            raw = strip_think_blocks(response.choices[0].message.content or "{}")
            return json.loads(extract_json_block(raw))
        except Exception:
            return {}

    @staticmethod
    def _format_brief(brief: Optional[Brief]) -> str:
        if not brief:
            return "No brief yet."
        parts = []
        for label, val in [
            ("Industry", brief.industry), ("Goal", brief.goal),
            ("Audience", brief.target_audience), ("Timeline", brief.timeline),
            ("Context", brief.additional_context),
        ]:
            if val:
                parts.append(f"{label}: {val}")
        if brief.budget_vnd:
            parts.append(f"Budget: {brief.budget_vnd:,} VND")
        return "\n".join(parts) if parts else "No brief yet."

    @staticmethod
    def _format_history(messages: list[dict]) -> str:
        lines = []
        for m in messages[-_RECENT_HISTORY_WINDOW:]:
            role = m.get("role", "")
            # 800 chars per message — enough to preserve full clarification Q&A
            content = (m.get("content") or "")[:800]
            if role and content:
                lines.append(f"{role.upper()}: {content}")
        return "\n".join(lines)


_central_agent: Optional[CentralAgent] = None


def get_central_agent() -> CentralAgent:
    global _central_agent
    if _central_agent is None:
        _central_agent = CentralAgent()
    return _central_agent
