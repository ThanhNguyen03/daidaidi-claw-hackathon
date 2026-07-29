"""
Base Skill Contract
===================
Abstract base for all skills in the multi-skills architecture.
A skill is a focused executor: receives context + task, executes, returns structured output.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from abc import ABC, abstractmethod
from functools import partial
from typing import Any, Optional

from pydantic import BaseModel, Field

from schemas.state import Brief, FeedbackRule


def strip_think_blocks(text: str) -> str:
    """Remove <think>...</think> blocks from LLM output."""
    cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    result = cleaned.strip()
    # If all tokens were consumed by an unclosed think block, the regex above won't match.
    # Strip the partial <think>...</think> block so we don't return broken markup.
    if not result and '<think>' in text:
        after_think = re.sub(r'<think>.*', '', text, flags=re.DOTALL)
        result = after_think.strip()
    return result


class ThinkFilter:
    """Streaming filter that strips <think>...</think> blocks from LLM output.

    Emits (type, content) tuples:
      ("think_start", "")  -- first <think> tag encountered
      ("think", content)   -- text inside a <think> block (caller may discard)
      ("think_end", "")    -- closing </think> tag
      ("content", content) -- regular response text to stream to the client
    """

    OPEN = "<think>"
    CLOSE = "</think>"

    def __init__(self) -> None:
        self._buf = ""
        self._in_think = False

    def push(self, token: str) -> list[tuple[str, str]]:
        self._buf += token
        events: list[tuple[str, str]] = []
        while True:
            if self._in_think:
                pos = self._buf.find(self.CLOSE)
                if pos >= 0:
                    if pos > 0:
                        events.append(("think", self._buf[:pos]))
                    events.append(("think_end", ""))
                    self._buf = self._buf[pos + len(self.CLOSE):]
                    self._in_think = False
                else:
                    safe = max(0, len(self._buf) - len(self.CLOSE))
                    if safe > 0:
                        events.append(("think", self._buf[:safe]))
                        self._buf = self._buf[safe:]
                    break
            else:
                pos = self._buf.find(self.OPEN)
                if pos >= 0:
                    if pos > 0:
                        events.append(("content", self._buf[:pos]))
                    events.append(("think_start", ""))
                    self._buf = self._buf[pos + len(self.OPEN):]
                    self._in_think = True
                else:
                    safe = max(0, len(self._buf) - len(self.OPEN))
                    if safe > 0:
                        events.append(("content", self._buf[:safe]))
                        self._buf = self._buf[safe:]
                    break
        return events

    def flush(self) -> list[tuple[str, str]]:
        if not self._buf:
            return []
        kind = "think" if self._in_think else "content"
        result = [(kind, self._buf)]
        self._buf = ""
        return result


def extract_json_block(text: str) -> str:
    """Extract JSON from markdown code block if present, or return text as-is."""
    match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if match:
        return match.group(1).strip()
    return text.strip()


# A backslash that starts no legal JSON escape. Gemini produces these while writing
# Vietnamese — a truncated "\u1EA" or a stray "\d" inside a string — and json.loads
# then rejects the entire reply with "Invalid \uXXXX escape". Measured on the planner
# call: two turns in three died that way and were reported to the rep as a provider
# outage, which is both wrong and unactionable.
_BAD_ESCAPE = re.compile(r'\\(?:u(?![0-9a-fA-F]{4})|[^"\\/bfnrtu])')


def repair_json_escapes(text: str) -> str:
    """Double any backslash that is not a valid JSON escape, so the value survives as
    literal text instead of taking the whole document down with it."""
    return _BAD_ESCAPE.sub(lambda m: '\\' + m.group(0), text)


def loads_lenient(text: str):
    """json.loads, retried once with invalid escapes repaired.

    Kept separate from a bare json.loads so callers keep the strict error when the
    reply is genuinely malformed rather than merely badly escaped.
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        repaired = repair_json_escapes(text)
        if repaired == text:
            raise
        result = json.loads(repaired)
        print("[json] recovered a reply that had invalid escape sequences")
        return result


class SkillContext(BaseModel):
    """Context passed to a skill for execution."""

    task: str = Field(..., description="What this skill should accomplish")
    brief: Optional[Brief] = None
    messages: list[dict] = Field(default_factory=list)
    previous_outputs: dict[str, dict] = Field(default_factory=dict)
    constraints: list[FeedbackRule] = Field(default_factory=list)
    session_id: str = ""
    # One knowledge.RequestLedger shared by every skill in this turn, so a
    # document read for one agent is not read again for the next (BRD §5.2).
    ledger: Optional[Any] = None

    class Config:
        arbitrary_types_allowed = True


class SkillOutput(BaseModel):
    """Standardized output from any skill execution."""

    skill: str
    status: str = "COMPLETE"  # COMPLETE | PARTIAL (truncated by max_tokens) | FAILED
    payload: dict[str, Any] = Field(default_factory=dict)
    summary: str = ""
    content: str = ""
    confidence: float = 0.85


class BaseSkill(ABC):
    """
    Abstract base for all skills.
    Skills are isolated executors — no inter-skill communication during execution.
    They receive a task + context from the central agent and return structured output.
    """

    def __init__(
        self,
        name: str,
        description: str,
        model_key: str,
        skill_md_path: Optional[str] = None,
    ):
        self.name = name
        self.description = description
        self.model_key = model_key
        self._skill_content = self._load_file(skill_md_path) if skill_md_path else f"# {name}\n\n{description}"
        self._catalog = None  # parsed lazily by reference_catalog

    def _load_file(self, path: str) -> str:
        if path and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                print(f"Warning: Could not load {path}: {e}")
        return ""

    @property
    def model_path(self) -> str:
        return os.getenv(self.model_key, "minimax/minimax-m2.5")

    # Appended to every skill's system prompt so the UI renders output correctly.
    _OUTPUT_FORMAT_GUIDE = """

---
## OUTPUT FORMAT GUIDE (MUST FOLLOW — UI rendering depends on this)

TABLES (comparisons, pricing, feature matrices, platform comparisons):
  ALWAYS use standard Markdown pipe syntax. NEVER use ASCII box-drawing for tables.
  | Column A   | Column B | Column C |
  |------------|----------|----------|
  | value      | value    | value    |

  ⚠️ CRITICAL: A comparison box like the one below is a TABLE, NOT an info box.
  Use Markdown pipe syntax for it — NEVER wrap comparison rows in ┌┐└┘│├┤ borders:

  WRONG (will break UI — do not generate this):
  ┌──────────────┬──────────┬────────────┐
  │  Feature     │  Zalo    │  Facebook  │
  ├──────────────┼──────────┼────────────┤
  │  Cost        │  Low     │  Medium    │
  └──────────────┴──────────┴────────────┘

  CORRECT:
  | Feature | Zalo | Facebook |
  |---------|------|----------|
  | Cost    | Low  | Medium   |

BAR CHARTS (budget breakdown, allocation, share by %):
  Always wrap in a plain ``` code block. Use ONLY this exact format:
  ```
  ┌─────────────────────────────────────────┐
  │  BUDGET BREAKDOWN                       │
  ╠═════════════════════════════════════════╣
  │  35%  MiniApp Development               │
  │  25%  Voucher System                    │
  │  15%  ZNS Campaign                      │
  └─────────────────────────────────────────┘
  ```
  NEVER use █ block characters. NEVER put % at end of line. NEVER nest a box inside another box.
  NEVER add column separators │ inside the box — info boxes have ONE column of text only.

INFO BOXES (game mechanics, form wireframes, step-by-step flows, feature descriptions):
  Each box = its OWN separate ``` code block. NEVER put 2+ boxes inside one fence.
  Use ├──┤ (not ╠══╣) for the header separator — one level of box only, never nested.
  CORRECT — two separate fences:
  ```
  ┌─────────────────────────────────────────┐
  │  SCREEN 1 TITLE                         │
  ├─────────────────────────────────────────┤
  │  🎮 Section heading:                    │
  │  • Bullet item                          │
  └─────────────────────────────────────────┘
  ```

  ```
  ┌─────────────────────────────────────────┐
  │  SCREEN 2 TITLE                         │
  ├─────────────────────────────────────────┤
  │  □ Checkbox item                        │
  │  • Another item                         │
  └─────────────────────────────────────────┘
  ```
  Use ╠══╣ separator (double-lines). ONE level of box only — NEVER nested boxes.
  ONE column of content per box — if content needs columns, use a Markdown table instead.

DIAGRAMS / USER FLOWS:
  Use Mermaid flowchart syntax. STRICT rules — the renderer will REJECT invalid syntax:

  1. ALWAYS wrap in ```mermaid fences. NEVER write the word "mermaid" alone on a line.
     CORRECT:
     ```mermaid
     flowchart LR
         A[Start] --> B[Step]
     ```
     WRONG: writing "mermaid" alone then diagram code without backtick fences.

  2. Edge labels: PIPE SYNTAX ONLY → A -->|Yes|B[Next]
     NEVER spaces: A -->    Yes    B[Next]  ← WILL BREAK RENDERING

  3. Node labels: SHORT plain text ONLY (max 5 words). ZERO HTML allowed.
     ❌ NEVER use <br/>, <b>, <span>, or ANY HTML tag inside node labels — they BREAK rendering.
     ❌ NEVER use | inside labels — it breaks edge-label parsing.
     ❌ NEVER use { } or # unless required by syntax.
     ✅ Shorten the label or split into two nodes if text is long.
     WRONG: A["User nhận link/QR<br/>qua Zalo"]
     CORRECT: A[User nhan link qua Zalo]

  4. Quotes: use straight " not curly " " inside labels.

  5. Keep diagrams simple — avoid style/classDef/subgraph unless truly essential.
     If used: style A fill:#e1f5fe,color:#000 (one line per node, no complex CSS).
     NEVER put style statements after the closing `end` of a subgraph.

  6. Maximum ~12 nodes per diagram. Split into multiple diagrams if flow is longer.

  7. MULTI-PARTY FLOWS (User + Staff, Customer + System, Buyer + Seller):
     Use `sequenceDiagram` — NEVER a two-column ASCII box. The renderer CANNOT display two-column
     ASCII tables — column content will be destroyed. ALWAYS use sequenceDiagram for any flow
     that involves two or more distinct actors (e.g. PHÍA USER + PHÍA STAFF).
     CORRECT:
     ```mermaid
     sequenceDiagram
         participant U as User
         participant S as Staff
         U->>S: Show QR code
         S-->>U: Xác nhận thành công
     ```
     WRONG: ASCII box with two columns separated by │ — DO NOT generate this.

TIMELINES:
  Use Mermaid gantt syntax inside ```mermaid fences. Same strict rules as flowchart above, plus:
  - Write `dateFormat YYYY-MM-DD` EXACTLY — NEVER put an actual date here (e.g. NEVER `dateFormat 2024-09-01`)
  - Every task line needs: TaskName :id, YYYY-MM-DD, Nd  (e.g. "Phase 1 :a1, 2024-01-01, 14d")
  - NEVER use `after <taskId>` — use explicit absolute dates for every task
  - NEVER include `axisFormat` — it causes rendering errors
  - NEVER leave out the date or duration — partial task lines break the renderer
  - If gantt would be complex, use a Markdown pipe table instead: Phase | Duration | Deliverable
"""

    async def _fetch_org_rules(self) -> list[str]:
        """Admin-Panel-authored org rules scoped to this skill.

        `get_active_rules(scope)` already does real scope filtering — `scope IN
        ('all', ?)` — but the only two callers in the codebase (central_agent's
        planner and its final synthesizer) always passed the literal string
        "all", which the function treats as "no filter, return every active rule
        regardless of scope." So the per-skill scope picker in the Admin Panel
        ("Compliance", "Product Solution", ...) never actually narrowed anything,
        and worse: neither of those two callers is the skill that writes the
        content a scoped rule is meant to constrain. A rule scoped to
        "Compliance" never reached compliance/skill.py at all. Passing self.name
        here is what makes the scope picker real, and calling it from the skill
        itself is what makes the rule reach the prompt that matters.
        """
        try:
            from database import get_active_rules
            rules = await asyncio.to_thread(get_active_rules, self.name)
            if rules:
                print(f"[org_rules] {self.name}: {len(rules)} active rule(s) injected")
            return rules
        except Exception as e:
            print(f"[org_rules] {self.name}: lookup failed, non-fatal ({e})")
            return []

    def _build_system_prompt(
        self, constraints: list[FeedbackRule], org_rules: Optional[list[str]] = None
    ) -> str:
        prompt = self._skill_content
        if org_rules:
            rules_block = "\n".join(f"- {r}" for r in org_rules)
            prompt = f"## Quy tắc tổ chức bắt buộc tuân thủ\n{rules_block}\n\n---\n\n" + prompt
        if constraints:
            scoped = [c for c in constraints if not c.scope or self.name in c.scope]
            if scoped:
                rules = "\n".join(f"- {c.rule}" for c in scoped)
                prompt = f"## Active Rules (MUST FOLLOW)\n{rules}\n\n---\n\n" + prompt
        prompt += self._OUTPUT_FORMAT_GUIDE
        return prompt

    def _build_context_block(self, context: SkillContext) -> str:
        parts = []

        recent_messages = []
        for m in context.messages[-8:]:
            role = m.get("role", "")
            content = (m.get("content") or "")[:600]
            if role in ("user", "assistant") and content:
                recent_messages.append(f"{role.upper()}: {content}")
        if recent_messages:
            parts.append("## Recent Conversation\n" + "\n".join(recent_messages))

        if context.brief:
            b = context.brief
            lines = []
            if b.industry:
                lines.append(f"- Industry: {b.industry}")
            if b.goal:
                lines.append(f"- Goal: {b.goal}")
            if b.target_audience:
                lines.append(f"- Target Audience: {b.target_audience}")
            if b.budget_vnd:
                lines.append(f"- Budget: {b.budget_vnd:,} VND")
            if b.timeline:
                lines.append(f"- Timeline: {b.timeline}")
            if b.specific_requirements:
                lines.append(f"- Requirements: {', '.join(b.specific_requirements)}")
            if b.constraints:
                lines.append(f"- Constraints: {', '.join(b.constraints)}")
            if b.additional_context:
                lines.append(f"- Additional Context: {b.additional_context}")
            if lines:
                parts.append("## Client Brief\n" + "\n".join(lines))

        if context.previous_outputs:
            prev = []
            for skill_name, out in context.previous_outputs.items():
                # `summary` on a failed skill is an error message (e.g. "Skill X failed:
                # timed out"), not real analysis — never pass it off as prior content.
                text = out.get("content") or ""
                if text:
                    prev.append(f"### {skill_name}\n{text}")
            if prev:
                parts.append("## Previous Analysis\n" + "\n\n".join(prev))

        return "\n\n".join(parts)

    @property
    def reference_catalog(self):
        """The reference files this skill declares in its SKILL.md, parsed once."""
        if self._catalog is None:
            from knowledge.loader import parse_catalog

            self._catalog = parse_catalog(self._skill_content)
            names = [e.filename for e in self._catalog]
            print(f"[knowledge] {self.name}: catalog {names or '(none declared)'}")
        return self._catalog

    async def retrieve_reference_context(
        self, context: "SkillContext", top_k: int = 3
    ) -> str:
        """Select and load the reference documents this task needs.

        Progressive disclosure: SKILL.md carries only the role, the workflow and a
        catalog of what is available; the bodies are pulled in on demand. Everything
        goes through knowledge.loader so the §14 log can account for what reached
        the prompt.

        A failed *selection* degrades to the agent's primary references. A failed
        *read* propagates — BRD §5.6 requires stopping over improvising.
        """
        from knowledge import loader

        catalog = self.reference_catalog
        if not catalog:
            return ""

        chosen = await loader.select(self.name, context.task, catalog)
        return loader.load(self.name, chosen[:top_k], ledger=context.ledger)

    async def _call_llm(
        self,
        system: str,
        user_msg: str,
        history: list[dict],
        max_tokens: int = 3500,
        temperature: float = 0.4,
    ) -> tuple[str, bool]:
        """Call LLM (non-streaming). Returns (text, truncated).

        `truncated` is True when the provider stopped on `finish_reason ==
        "length"` rather than finishing on its own — nothing checked this
        before, so a reply cut off mid-sentence by max_tokens was wrapped as
        `status="COMPLETE"` same as a whole one, and got assembled into the
        proposal as if it were. Returned rather than stored on `self`: skill
        instances are shared singletons (skills/registry.py) serving
        concurrent turns, so per-call state cannot live on the instance
        without one turn's flag being clobbered by another's.
        """
        from llm.client import get_llm_client

        client = get_llm_client(self.name)
        messages = [{"role": "system", "content": system}]
        for m in history[-8:]:
            role = m.get("role", "")
            content = m.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user_msg})

        call_kwargs = dict(messages=messages, temperature=temperature, stream=False)
        if max_tokens is not None:
            call_kwargs["max_tokens"] = max_tokens
        # Run the synchronous OpenAI call in a thread pool so the event loop stays free.
        # The dedicated LLM_POOL, not the default executor — see llm/pool.py.
        from llm.pool import LLM_POOL
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(LLM_POOL, partial(client.create_completion, **call_kwargs))
        choice = response.choices[0]
        truncated = getattr(choice, "finish_reason", None) == "length"
        raw = choice.message.content or ""
        return strip_think_blocks(raw), truncated

    @abstractmethod
    async def execute(self, context: SkillContext) -> SkillOutput:
        raise NotImplementedError
