"""
Central Agent
=============
Single central intelligence that:
1. Classifies user intent (casual chat vs sales task)
2. Elicits requirements when brief is incomplete
3. Plans and dispatches to specialized skills
4. Synthesizes skill outputs into a coherent response

Replaces the multi-agent orchestration with a cleaner skill-based model.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import uuid
from datetime import datetime
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


# ---------------------------------------------------------------------------
# Planning prompt helper
# ---------------------------------------------------------------------------

_PLANNING_SYSTEM = _CENTRAL_SKILL + """

---

## Output Format

Return ONLY valid JSON (no markdown wrapping). Choose ONE of these schemas:

### If the message is casual chat or a greeting:
{
  "type": "casual_chat",
  "response": "<warm, natural response in user's language>"
}

### If information is missing before skills can execute:
{
  "type": "sales_task",
  "brief_update": {
    "industry": null,
    "goal": null,
    "target_audience": null,
    "budget_vnd": null,
    "timeline": null,
    "specific_requirements": [],
    "constraints": [],
    "additional_context": null
  },
  "ready_to_execute": false,
  "questions": [
    {
      "id": "q_<field>",
      "text": "<user-friendly question in user's language>",
      "target_field": "<brief field name>",
      "is_mandatory": true
    }
  ]
}

### If the brief is complete enough to execute skills:
{
  "type": "sales_task",
  "brief_update": {
    "industry": "<if extracted from message>",
    "goal": "<if extracted>",
    "target_audience": "<if extracted>",
    "budget_vnd": <number or null>,
    "timeline": "<if extracted>",
    "specific_requirements": [],
    "constraints": [],
    "additional_context": "<if extracted>"
  },
  "ready_to_execute": true,
  "skill_plan": [
    [
      {"skill": "<skill_name>", "task": "<specific task description for this skill>"}
    ],
    [
      {"skill": "<skill_name>", "task": "<specific task description>"}
    ]
  ]
}

Rules:
- brief_update: only include fields that were mentioned in the current message; use null for others
- questions: max 3, only the most blocking ones, in user's language
- skill_plan: group parallel skills in same sub-array; skills needing prior output in later groups
- task: be specific — include industry, goal, context so skill can execute without additional context
"""


class CentralAgent:
    """
    Central agent that coordinates all skill dispatch and conversation management.
    """

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
        """
        Process a user message and yield SSE event dicts.
        Caller wraps events in _sse_data() before sending to client.
        """
        # Step 1: Plan (single LLM call)
        try:
            plan = await self._plan(state, message)
        except Exception as e:
            print(f"[CentralAgent] Planning failed: {e}")
            yield {"type": "content", "content": "Xin lỗi, đã xảy ra lỗi. Bạn vui lòng thử lại."}
            yield {"type": "done"}
            return

        # Step 2: Handle casual chat
        if plan.get("type") == "casual_chat":
            response = plan.get("response", "")
            if response:
                yield {"type": "content", "content": response}
                state.messages.append({
                    "role": "assistant",
                    "content": response,
                    "agent": "central_agent",
                    "timestamp": datetime.now().isoformat(),
                })
            yield {"type": "done"}
            return

        # Step 3: Update brief from extracted info
        self._apply_brief_update(state, plan.get("brief_update") or {})

        # Step 4: Handle needs-questions
        if not plan.get("ready_to_execute"):
            questions = plan.get("questions") or []
            if questions:
                # Store questions in state
                q_objects = []
                for q_data in questions:
                    q = Question(
                        id=q_data.get("id", f"q_{uuid.uuid4().hex[:6]}"),
                        text=q_data.get("text", ""),
                        target_field=q_data.get("target_field", "additional_context"),
                        is_mandatory=q_data.get("is_mandatory", True),
                        priority=1,
                    )
                    q_objects.append(q)
                state.question_stack = q_objects
                yield {
                    "type": "question_card",
                    "questions": [q.model_dump() for q in q_objects],
                }
            else:
                yield {
                    "type": "content",
                    "content": "Mình cần thêm thông tin để hỗ trợ bạn tốt hơn. Bạn có thể chia sẻ thêm về yêu cầu không?",
                }
            yield {"type": "done"}
            return

        # Step 5: Execute skills
        skill_plan = plan.get("skill_plan") or []
        if not skill_plan:
            yield {"type": "content", "content": "Mình chưa xác định được yêu cầu cụ thể. Bạn có thể mô tả chi tiết hơn?"}
            yield {"type": "done"}
            return

        skill_registry = get_skill_registry()
        all_outputs: dict[str, SkillOutput] = {}

        for group_idx, group in enumerate(skill_plan):
            if not group:
                continue
            tasks = []
            for item in group:
                skill_name = item.get("skill")
                task_desc = item.get("task", "")
                skill = skill_registry.get(skill_name)
                if not skill:
                    print(f"[CentralAgent] Skill not found: {skill_name}")
                    continue

                context = SkillContext(
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
                tasks.append((skill_name, skill.execute(context)))

            if not tasks:
                continue

            # Emit status — thinking
            for skill_name, _ in tasks:
                yield {"type": "agent_status", "agent": skill_name, "status": "thinking"}

            results = await asyncio.gather(*[t for _, t in tasks], return_exceptions=True)

            for (skill_name, _), result in zip(tasks, results):
                if isinstance(result, Exception):
                    print(f"[CentralAgent] Skill {skill_name} raised: {result}")
                    yield {"type": "agent_status", "agent": skill_name, "status": "failed"}
                    continue

                skill_out: SkillOutput = result
                all_outputs[skill_name] = skill_out

                # Store in state.outputs as AgentOutput (for checkpoint compat)
                state.outputs[skill_name] = AgentOutput(
                    agent=skill_name,
                    status="COMPLETE" if skill_out.status == "COMPLETE" else "FAILED",
                    payload=skill_out.payload,
                    summary=skill_out.summary,
                    confidence=skill_out.confidence,
                )

                yield {"type": "agent_status", "agent": skill_name, "status": "completed"}

                if skill_out.content:
                    yield {"type": "agent_message", "agent": skill_name, "content": skill_out.content}

        # Step 6: Synthesize final response
        if all_outputs:
            async for event in self._synthesize(state, message, all_outputs):
                yield event

        yield {"type": "done"}

    # ------------------------------------------------------------------
    # Planning
    # ------------------------------------------------------------------

    async def _plan(self, state: SalesCaseState, message: str) -> dict[str, Any]:
        """Single LLM call: classify → extract → plan skills."""
        from llm.greennode import get_llm_client

        client = get_llm_client("sales_orchestrator")

        brief_block = self._format_brief(state.brief)
        history_block = self._format_history(state.messages[-8:])

        user_prompt = ""
        if history_block:
            user_prompt += f"## Conversation History\n{history_block}\n\n"
        if brief_block:
            user_prompt += f"## Current Brief\n{brief_block}\n\n"
        if state.question_stack:
            answered = [q for q in state.question_stack if q.answered]
            if answered:
                ans_block = "\n".join(f"- {q.target_field}: {q.answer}" for q in answered)
                user_prompt += f"## Answered Questions\n{ans_block}\n\n"
        user_prompt += f"## User Message\n{message}\n\nReturn JSON planning decision."

        response = client.create_completion(
            messages=[
                {"role": "system", "content": _PLANNING_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=1500,
            stream=False,
        )

        raw = response.choices[0].message.content or "{}"
        raw = strip_think_blocks(raw)
        raw = extract_json_block(raw)

        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"[CentralAgent] JSON parse failed: {e}\nRaw: {raw[:300]}")
            # Fallback: treat as casual chat
            return {"type": "casual_chat", "response": raw[:500] or "Mình hiểu yêu cầu của bạn. Bạn có thể cung cấp thêm thông tin về chiến dịch không?"}

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

        if not skill_outputs:
            return

        outputs_block = ""
        for skill_name, out in skill_outputs.items():
            if out.content:
                outputs_block += f"\n\n### {skill_name}\n{out.content}"

        if not outputs_block.strip():
            return

        system = """You are the AdtimaBox Sales Agent synthesizer.
Given the outputs from specialized skills, create a single coherent, well-structured response.
- Use markdown with headers and bullet points
- Match the user's language (Vietnamese if they wrote in Vietnamese)
- Highlight key insights, recommendations, and next steps
- Be concise but comprehensive — no padding, no filler text
- Do not mention skill names or internal pipeline details"""

        user_msg = f"## Original Request\n{original_message}\n\n## Skill Outputs{outputs_block}\n\nSynthesize into a single comprehensive response."

        client = get_llm_client("sales_orchestrator")
        stream = client.create_completion(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.6,
            max_tokens=3000,
            stream=True,
        )

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
    # Validation response handling (for /chat/answer endpoint)
    # ------------------------------------------------------------------

    async def handle_validation_response(
        self, state: SalesCaseState, answers: dict[str, str]
    ) -> AgentOutput:
        """Map user answers back to brief fields and clear answered questions."""
        if not state.brief:
            state.brief = Brief()

        for q in state.question_stack:
            if q.id in answers and answers[q.id]:
                q.mark_answered(answers[q.id])
                self._apply_field(state.brief, q.target_field, answers[q.id])

        # Handle free_text: use LLM to map to brief
        free_text = answers.get("free_text")
        if free_text:
            self._apply_brief_update(state, await self._extract_brief_from_text(state, free_text))

        # Check if all mandatory questions answered
        unanswered_mandatory = [
            q for q in state.question_stack
            if q.is_mandatory and not q.answered
        ]
        if unanswered_mandatory:
            state.validation_status = "PENDING"
            return AgentOutput(
                agent="central_agent",
                status="NEEDS_INPUT",
                payload={},
                summary=f"{len(unanswered_mandatory)} question(s) still pending",
                confidence=0.5,
                questions=unanswered_mandatory,
            )

        state.validation_status = "READY"
        state.question_stack = []
        return AgentOutput(
            agent="central_agent",
            status="COMPLETE",
            payload={},
            summary="All questions answered. Ready to proceed.",
            confidence=0.9,
            questions=[],
        )

    async def extract_desired_outputs(self, answer: str) -> list[str]:
        """Extract desired output types from user answer."""
        answer_lower = answer.lower()
        outputs = []
        if any(w in answer_lower for w in ["pptx", "powerpoint", "slide", "presentation", "deck"]):
            outputs.append("pptx")
        if any(w in answer_lower for w in ["figma", "design", "ui", "wireframe", "wire"]):
            outputs.append("figma")
        if any(w in answer_lower for w in ["flow", "diagram", "mermaid", "userflow", "user flow"]):
            outputs.append("userflow")
        if any(w in answer_lower for w in ["quote", "pricing", "price", "cost", "budget", "quotation", "báo giá"]):
            outputs.append("quote")
        return outputs or ["pptx"]

    async def validate_before_dispatch(self, state: SalesCaseState):
        """Lightweight validation check (for skip_question endpoint compat)."""
        has_industry = bool(state.brief and state.brief.industry)
        has_goal = bool(state.brief and state.brief.goal)
        mandatory_unanswered = [
            q for q in state.question_stack if q.is_mandatory and not q.answered
        ]
        should_dispatch = has_industry and has_goal and not mandatory_unanswered
        if should_dispatch:
            state.validation_status = "READY"
        output = AgentOutput(
            agent="central_agent",
            status="COMPLETE" if should_dispatch else "NEEDS_INPUT",
            payload={},
            summary="Ready" if should_dispatch else "Needs more information",
            confidence=0.9 if should_dispatch else 0.5,
            questions=state.question_stack if not should_dispatch else [],
        )
        return output, should_dispatch

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _apply_brief_update(self, state: SalesCaseState, brief_update: dict) -> None:
        if not brief_update:
            return
        if not state.brief:
            state.brief = Brief()
        b = state.brief
        for field, value in brief_update.items():
            if value is not None:
                self._apply_field(b, field, value)

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
            brief.additional_context = (brief.additional_context or "") + " " + str(value)
        elif field == "specific_requirements" and isinstance(value, list):
            brief.specific_requirements = list(brief.specific_requirements or []) + value
        elif field == "constraints" and isinstance(value, list):
            brief.constraints = list(brief.constraints or []) + value

    async def _extract_brief_from_text(self, state: SalesCaseState, text: str) -> dict:
        """Use LLM to extract brief fields from free text."""
        from llm.greennode import get_llm_client

        client = get_llm_client("sales_orchestrator")
        brief_block = self._format_brief(state.brief)

        response = client.create_completion(
            messages=[
                {"role": "system", "content": "Extract brief fields from text. Return JSON only with keys: industry, goal, target_audience, budget_vnd (number or null), timeline, specific_requirements (array), constraints (array), additional_context."},
                {"role": "user", "content": f"Current brief:\n{brief_block}\n\nNew text:\n{text}\n\nReturn JSON with only newly mentioned fields."},
            ],
            temperature=0.1,
            max_tokens=500,
            stream=False,
        )
        raw = strip_think_blocks(response.choices[0].message.content or "{}")
        raw = extract_json_block(raw)
        try:
            return json.loads(raw)
        except Exception:
            return {}

    @staticmethod
    def _format_brief(brief: Optional[Brief]) -> str:
        if not brief:
            return "No brief yet."
        parts = []
        if brief.industry:
            parts.append(f"Industry: {brief.industry}")
        if brief.goal:
            parts.append(f"Goal: {brief.goal}")
        if brief.target_audience:
            parts.append(f"Audience: {brief.target_audience}")
        if brief.budget_vnd:
            parts.append(f"Budget: {brief.budget_vnd:,} VND")
        if brief.timeline:
            parts.append(f"Timeline: {brief.timeline}")
        if brief.additional_context:
            parts.append(f"Context: {brief.additional_context}")
        return "\n".join(parts) if parts else "No brief yet."

    @staticmethod
    def _format_history(messages: list[dict]) -> str:
        lines = []
        for m in messages[-6:]:
            role = m.get("role", "")
            content = m.get("content", "")[:200]
            if role and content:
                lines.append(f"{role.upper()}: {content}")
        return "\n".join(lines)


_central_agent: Optional[CentralAgent] = None


def get_central_agent() -> CentralAgent:
    global _central_agent
    if _central_agent is None:
        _central_agent = CentralAgent()
    return _central_agent
