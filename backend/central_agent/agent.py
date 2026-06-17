"""
Central Agent
=============
Single entry point that:
1. Parses the user message and extracts brief fields
2. Picks relevant skills based on message content (keyword + LLM)
3. Executes all chosen skills in parallel
4. Streams a synthesized final response

Design principles:
- NEVER block on missing info -- always execute with what we have
- If planning LLM call fails, fall back to running all core skills
- Skills run concurrently; synthesis streams tokens as they arrive
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import datetime
from functools import partial
from typing import Any, AsyncGenerator, Optional

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

_SKILL_TIMEOUT_S = 150  # per-skill wall-clock timeout; emit failed event instead of hanging


# ---------------------------------------------------------------------------
# Planning prompt
# ---------------------------------------------------------------------------

_PLANNING_SYSTEM = """You are the AdtimaBox Sales AI planning engine.
Given a user message, return a JSON object with:
1. Extracted brief fields (use null for anything not mentioned)
2. Which skills to call and what task to give each

Available skills:
- market_strategy: market analysis, campaign ideas, audience insight, Zalo strategy, case studies
- product_solution: MiniApp architecture, pricing/quote, CShub packages, integration design, userflow
- compliance: Zalo policy, PDPL, advertising law, risk flags
- client_simulator: buyer objections, competitor defense, pitch coaching
- design: wireframes, UI screens, Mermaid diagrams

Rules:
- ALWAYS set ready_to_execute: true -- never block on missing info
- For any sales brief or campaign request, ALWAYS include at least market_strategy and product_solution
- Include compliance if campaign involves data collection or advertising
- Group skills that can run in parallel in the same sub-array
- task string: be specific and include all context from the message so skill can run without extra info

Return ONLY valid JSON, no markdown fences:
{
  "brief_update": {
    "industry": null,
    "goal": null,
    "target_audience": null,
    "budget_vnd": null,
    "timeline": null,
    "additional_context": null
  },
  "ready_to_execute": true,
  "skill_plan": [
    [
      {"skill": "market_strategy", "task": "<detailed task>"},
      {"skill": "product_solution", "task": "<detailed task>"},
      {"skill": "compliance", "task": "<detailed task>"}
    ]
  ]
}"""


# ---------------------------------------------------------------------------
# Keyword-based fallback skill picker
# ---------------------------------------------------------------------------

def _pick_skills_from_message(message: str) -> list[dict[str, str]]:
    """Fallback: pick skills by keyword scan without LLM."""
    msg = message.lower()
    skills = []

    # Always include market_strategy for any sales/campaign mention
    if any(w in msg for w in ["brief", "campaign", "chien dich", "chien luoc", "market", "strategy",
                               "idea", "y tuong", "zalo", "brand", "audience", "ta:", "target"]):
        skills.append({"skill": "market_strategy", "task": f"Analyze and develop market strategy for this request: {message[:500]}"})

    # Product solution for pricing/solution/proposal/userflow mentions
    if any(w in msg for w in ["proposal", "bao gia", "bao gi", "price", "gia", "quote", "solution",
                               "product", "miniapp", "mini app", "userflow", "flow", "package"]):
        skills.append({"skill": "product_solution", "task": f"Develop product solution, pricing, and userflow for: {message[:500]}"})

    # Compliance for data/privacy/advertising mentions
    if any(w in msg for w in ["data", "collect", "thu thap", "pdpl", "policy", "compliance",
                               "legal", "advertising", "quang cao", "zalo oa"]):
        skills.append({"skill": "compliance", "task": f"Check compliance requirements for: {message[:500]}"})

    # Design for wireframe/UI/screen mentions
    if any(w in msg for w in ["wireframe", "design", "ui", "screen", "man hinh", "giao dien", "figma"]):
        skills.append({"skill": "design", "task": f"Design wireframes/UI for: {message[:500]}"})

    # Client simulator for objection/competitor mentions
    if any(w in msg for w in ["objection", "competitor", "pitch", "client sim", "simulate"]):
        skills.append({"skill": "client_simulator", "task": f"Simulate client perspective for: {message[:500]}"})

    # Default: if nothing matched, run the core three
    if not skills:
        skills = [
            {"skill": "market_strategy", "task": f"Analyze and provide market insights for: {message[:500]}"},
            {"skill": "product_solution", "task": f"Develop solution and pricing for: {message[:500]}"},
        ]

    return skills


class CentralAgent:
    """Central agent: classify intent, extract brief, dispatch skills, synthesize."""

    def __init__(self):
        self.name = "central_agent"
        self.model_key = "MODEL_CENTRAL_AGENT"

    @property
    def model_path(self) -> str:
        return os.getenv(self.model_key, os.getenv("MODEL_SALES_ORCHESTRATOR", "minimax/minimax-m2.5"))

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def run(
        self, state: SalesCaseState, message: str
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Process a user message. Always executes skills -- never blocks on missing info."""

        # Step 1: Quick check -- is this just a greeting/casual chat?
        if self._is_casual(message):
            response = await self._casual_reply(message)
            yield {"type": "content", "content": response}
            state.messages.append({
                "role": "assistant", "content": response,
                "agent": "central_agent", "timestamp": datetime.now().isoformat(),
            })
            yield {"type": "done"}
            return

        # Step 2: Plan (LLM extracts brief + picks skills) with fallback
        plan = await self._plan_with_fallback(state, message)
        self._apply_brief_update(state, plan.get("brief_update") or {})

        skill_plan: list[list[dict]] = plan.get("skill_plan") or []
        if not skill_plan:
            # Hard fallback -- keyword-based skill selection
            skill_plan = [_pick_skills_from_message(message)]

        # Step 3: Execute all skill groups
        skill_registry = get_skill_registry()
        all_outputs: dict[str, SkillOutput] = {}

        for group in skill_plan:
            if not group:
                continue

            tasks: dict[asyncio.Task, str] = {}
            for item in group:
                skill_name = item.get("skill", "")
                task_desc = item.get("task", message)
                skill = skill_registry.get(skill_name)
                if not skill:
                    print(f"[CentralAgent] Skill not found: {skill_name}, skipping")
                    continue
                ctx = SkillContext(
                    task=task_desc,
                    brief=state.brief,
                    messages=state.messages[-8:],
                    previous_outputs={
                        k: {"content": v.content, "summary": v.summary, "payload": v.payload}
                        for k, v in all_outputs.items()
                    },
                    constraints=state.constraints,
                    session_id=state.session_id,
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

        # Step 4: Synthesize final response
        if all_outputs:
            async for event in self._synthesize(state, message, all_outputs):
                yield event
        else:
            yield {"type": "content", "content": "Xin loi, cac skill khong tra ve ket qua. Vui long thu lai."}

        yield {"type": "done"}

    # ------------------------------------------------------------------
    # Planning
    # ------------------------------------------------------------------

    async def _plan_with_fallback(self, state: SalesCaseState, message: str) -> dict[str, Any]:
        """Call planning LLM. On any failure, return a keyword-based fallback plan."""
        try:
            return await self._plan(state, message)
        except Exception as e:
            print(f"[CentralAgent] Planning LLM failed ({e}), using keyword fallback")
            return {
                "brief_update": {},
                "ready_to_execute": True,
                "skill_plan": [_pick_skills_from_message(message)],
            }

    async def _plan(self, state: SalesCaseState, message: str) -> dict[str, Any]:
        """Single LLM call: extract brief fields + pick skills."""
        from llm.greennode import get_llm_client

        client = get_llm_client("central_agent")

        brief_block = self._format_brief(state.brief)
        history_block = self._format_history(state.messages[-4:])

        user_prompt = ""
        if history_block:
            user_prompt += f"## Conversation History\n{history_block}\n\n"
        if brief_block and brief_block != "No brief yet.":
            user_prompt += f"## Current Brief\n{brief_block}\n\n"
        user_prompt += f"## User Message\n{message}\n\nReturn JSON planning decision (ready_to_execute must be true)."

        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            partial(
                client.create_completion,
                messages=[
                    {"role": "system", "content": _PLANNING_SYSTEM},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=1200,
                stream=False,
            ),
        )

        raw = response.choices[0].message.content or "{}"
        raw = strip_think_blocks(raw)
        raw = extract_json_block(raw)

        result = json.loads(raw)
        # Safety: always force ready_to_execute = true
        result["ready_to_execute"] = True
        # Safety: ensure skill_plan exists
        if not result.get("skill_plan"):
            result["skill_plan"] = [_pick_skills_from_message(message)]
        return result

    # ------------------------------------------------------------------
    # Synthesis
    # ------------------------------------------------------------------

    async def _synthesize(
        self,
        state: SalesCaseState,
        original_message: str,
        skill_outputs: dict[str, SkillOutput],
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream a synthesized final response from all skill outputs."""
        from llm.greennode import get_llm_client
        from main import _ThinkFilter

        outputs_block = "\n\n".join(
            f"### {name}\n{out.content}"
            for name, out in skill_outputs.items()
            if out.content
        )
        if not outputs_block.strip():
            return

        system = """You are the AdtimaBox Sales AI — final proposal writer.
Given specialist analysis from multiple skill modules, assemble ONE cohesive proposal document.

Language rule: Match the user's language. Vietnamese brief → respond fully in Vietnamese.

Output structure (use ALL sections that have relevant content):
1. **Tóm tắt đề xuất** — 3–4 sentence executive summary: what we recommend and why
2. **Phân tích chiến lược** — key strategic insights, market context, consumer insight (paragraphs + bullets)
3. **Giải pháp Zalo** — the recommended solution with user journey (include any Mermaid diagrams from skills AS-IS)
4. **Báo giá ước tính** — pricing table if available
5. **Compliance & lưu ý pháp lý** — any policy notes (only if compliance skill flagged something)
6. **Bước tiếp theo** — 3–5 concrete next steps

Format rules:
- Mix narrative paragraphs WITH bullet points WITH tables — never make the entire response tables only
- Preserve any Mermaid diagram blocks (```mermaid ... ```) from skill outputs exactly as-is
- Use ## for section headers, ### for sub-sections
- Be specific to this brief/brand — no generic filler
- Do NOT mention "skill", "agent", "module", or internal pipeline names"""

        user_msg = (
            f"## Original Request\n{original_message}\n\n"
            f"## Specialist Outputs\n{outputs_block}\n\n"
            "Assemble into a complete proposal document following the structure above."
        )

        client = get_llm_client("central_agent")
        try:
            stream = client.create_completion(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.5,
                stream=True,
            )
        except Exception as e:
            print(f"[CentralAgent] Synthesis stream failed: {e}")
            # Fallback: emit skill outputs directly
            for name, out in skill_outputs.items():
                if out.content:
                    yield {"type": "content", "content": f"\n\n## {name.replace('_', ' ').title()}\n{out.content}"}
            return

        tf = _ThinkFilter()
        accumulated = ""

        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                token = chunk.choices[0].delta.content
                for kind, text in tf.push(token):
                    if kind == "think_start":
                        yield {"type": "thinking_start"}
                    elif kind == "think_end":
                        yield {"type": "thinking_end"}
                    elif kind == "content" and text:
                        accumulated += text
                        yield {"type": "content", "content": text}

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
    # Casual chat
    # ------------------------------------------------------------------

    _CASUAL_PATTERNS = re.compile(
        r"^(hi|hello|hey|xin chao|chao|chao ban|ok|okay|cam on|thank|thanks|"
        r"good morning|good afternoon|good evening|buoi sang|buoi chieu|buoi toi)[\s!.?]*$",
        re.IGNORECASE,
    )

    def _is_casual(self, message: str) -> bool:
        stripped = message.strip()
        return bool(self._CASUAL_PATTERNS.match(stripped)) and len(stripped) < 40

    async def _casual_reply(self, message: str) -> str:
        return (
            "Xin chao! Minh la AdtimaBox Sales AI. "
            "Ban co the chia se brief hoac yeu cau cua ban, minh se phan tich va de xuat giai phap phu hop."
        )

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
        state.validation_status = "READY"
        state.question_stack = []
        return AgentOutput(
            agent="central_agent", status="COMPLETE", payload={},
            summary="Ready to proceed.", confidence=0.9, questions=[],
        )

    async def extract_desired_outputs(self, answer: str) -> list[str]:
        lower = answer.lower()
        outputs = []
        if any(w in lower for w in ["pptx", "powerpoint", "slide", "deck"]):
            outputs.append("pptx")
        if any(w in lower for w in ["figma", "wireframe", "wire", "ui"]):
            outputs.append("figma")
        if any(w in lower for w in ["flow", "diagram", "mermaid", "userflow"]):
            outputs.append("userflow")
        if any(w in lower for w in ["quote", "pricing", "price", "cost", "bao gia"]):
            outputs.append("quote")
        return outputs or ["pptx"]

    async def validate_before_dispatch(self, state: SalesCaseState):
        has_brief = bool(state.brief and (state.brief.industry or state.brief.goal))
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
            try:
                brief.budget_vnd = int(str(value).replace(",", "").replace(".", "").strip())
            except (ValueError, TypeError):
                pass
        elif field == "timeline" and not brief.timeline:
            brief.timeline = str(value)
        elif field == "additional_context":
            brief.additional_context = ((brief.additional_context or "") + " " + str(value)).strip()
        elif field == "specific_requirements" and isinstance(value, list):
            brief.specific_requirements = list(brief.specific_requirements or []) + value
        elif field == "constraints" and isinstance(value, list):
            brief.constraints = list(brief.constraints or []) + value

    async def _extract_brief_from_text(self, state: SalesCaseState, text: str) -> dict:
        from llm.greennode import get_llm_client
        client = get_llm_client("central_agent")
        try:
            response = client.create_completion(
                messages=[
                    {"role": "system", "content": "Extract brief fields from text. Return JSON only: industry, goal, target_audience, budget_vnd (number|null), timeline, additional_context."},
                    {"role": "user", "content": text},
                ],
                temperature=0.1, max_tokens=300, stream=False,
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
        for m in messages[-4:]:
            role = m.get("role", "")
            content = (m.get("content") or "")[:200]
            if role and content:
                lines.append(f"{role.upper()}: {content}")
        return "\n".join(lines)


_central_agent: Optional[CentralAgent] = None


def get_central_agent() -> CentralAgent:
    global _central_agent
    if _central_agent is None:
        _central_agent = CentralAgent()
    return _central_agent
