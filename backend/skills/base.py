"""
Base Skill Contract
===================
Abstract base for all skills in the multi-skills architecture.
A skill is a focused executor: receives context + task, executes, returns structured output.
"""

from __future__ import annotations

import asyncio
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


def extract_json_block(text: str) -> str:
    """Extract JSON from markdown code block if present, or return text as-is."""
    match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if match:
        return match.group(1).strip()
    return text.strip()


class SkillContext(BaseModel):
    """Context passed to a skill for execution."""

    task: str = Field(..., description="What this skill should accomplish")
    brief: Optional[Brief] = None
    messages: list[dict] = Field(default_factory=list)
    previous_outputs: dict[str, dict] = Field(default_factory=dict)
    constraints: list[FeedbackRule] = Field(default_factory=list)
    session_id: str = ""

    class Config:
        arbitrary_types_allowed = True


class SkillOutput(BaseModel):
    """Standardized output from any skill execution."""

    skill: str
    status: str = "COMPLETE"  # COMPLETE | FAILED
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

TABLES (comparisons, pricing, specs):
  Use standard Markdown pipe syntax — NEVER ASCII box-drawing tables:
  | Column A | Column B | Column C |
  |----------|----------|----------|
  | value    | value    | value    |

BAR CHARTS (budget breakdown, allocation, share by %):
  Always wrap in a plain ``` code block. Use ONLY this exact format:
  ```
  ┌─────────────────────────────────────────┐
  │  BUDGET BREAKDOWN                       │
  ╠═════════════════════════════════════════╣
  │  35%  MiniApp Development               │
  │  25%  Voucher System                    │
  │  15%  ZNS / Ads                         │
  └─────────────────────────────────────────┘
  ```
  NEVER use █ block characters. NEVER put % at end of line. NEVER nest a box inside another box.

INFO BOXES (game mechanics, form wireframes, step-by-step flows, feature descriptions):
  Always wrap in a plain ``` code block. Use ONLY this exact format:
  ```
  ┌─────────────────────────────────────────┐
  │  TITLE HERE                             │
  ├─────────────────────────────────────────┤
  │  🎮 Section heading:                    │
  │  • Bullet item                          │
  │  □ Checkbox item                        │
  └─────────────────────────────────────────┘
  ```
  Use ├──┤ separator (dashes, not ╠═╣ double-lines). ONE level of box only — NEVER nested boxes.

DIAGRAMS / USER FLOWS:
  Use Mermaid flowchart syntax inside ```mermaid fences.
  NEVER write a code block containing only a label (e.g. ```\\nMermaid User Journey\\n```).

TIMELINES:
  Use Mermaid gantt syntax inside ```mermaid fences.
  If a Mermaid gantt is not feasible, use a Markdown pipe table with columns: Phase | Duration | Deliverable.
"""

    def _build_system_prompt(self, constraints: list[FeedbackRule]) -> str:
        prompt = self._skill_content
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
                text = out.get("content") or out.get("summary", "")
                if text:
                    prev.append(f"### {skill_name}\n{text[:600]}")
            if prev:
                parts.append("## Previous Analysis\n" + "\n\n".join(prev))

        return "\n\n".join(parts)

    async def retrieve_reference_context(self, query: str, top_k: int = 3) -> str:
        """
        Retrieve relevant knowledge from the agent's reference/ directory via RAG.
        Returns a formatted context block to inject into the system prompt.
        This uses the same KB vector store that ingest_all_agents() populates at startup.
        """
        try:
            from repos.kb_repo import get_kb_repo
            kb = get_kb_repo()
            results = await kb.search(
                query,
                top_k=top_k,
                filters={"agent": self.name, "type": "knowledge"},
            )
            if not results:
                # Also try the agent name variations (e.g. market_strategy_agent)
                alt_name = self.name + "_agent"
                results = await kb.search(
                    query,
                    top_k=top_k,
                    filters={"agent": alt_name, "type": "knowledge"},
                )
            if results:
                parts = ["\n\n" + "=" * 60, "REFERENCE KNOWLEDGE:", "=" * 60]
                for r in results:
                    parts.append(f"\n[{r.source}]\n{r.content}")
                return "\n".join(parts)
        except Exception as e:
            print(f"Warning: KB reference search failed for {self.name}: {e}")
        return ""

    async def _call_llm(
        self,
        system: str,
        user_msg: str,
        history: list[dict],
        max_tokens: int = 2500,
        temperature: float = 0.4,
    ) -> str:
        """Call LLM (non-streaming) and return stripped response text."""
        from llm.greennode import get_llm_client

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
        # Run the synchronous OpenAI call in a thread pool so the event loop stays free
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, partial(client.create_completion, **call_kwargs))
        raw = response.choices[0].message.content or ""
        return strip_think_blocks(raw)

    @abstractmethod
    async def execute(self, context: SkillContext) -> SkillOutput:
        raise NotImplementedError
