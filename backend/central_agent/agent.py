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
_RECENT_HISTORY_WINDOW = 20
_SYNTHESIS_HISTORY_WINDOW = 12


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

CLARIFY only when ALL three are true simultaneously:
  1. No ASSISTANT turn appears in Conversation History (first-ever response)
  2. No industry/sector mentioned anywhere (message or accumulated brief)
  3. No goal/objective mentioned anywhere (message or accumulated brief)

EXECUTE in every other situation — ongoing conversation, partial brief, any business context.
When in doubt → EXECUTE. Skills handle incomplete info with reasonable assumptions.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 2 — MATCH BRIEF TO SKILLS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Available skills (name: description):
{skill_catalog}

For each skill above, ask: "Does the user's brief or current request genuinely need this?"
Select a skill only if YES. Do not select a skill just because it's common or safe.

Read the FULL context — Conversation History + Accumulated Brief + Current Message.
The current message is the primary signal for which skills to select:
  → Specific ask ("nói về pháp lý", "userflow chi tiết hơn") → pick only matching skills
  → Broad brief covering multiple areas → pick all skills that match those areas
  → "proposal", "tổng hợp lại" → proposal_assembler (alone, last group, explicit request only)

Write a SPECIFIC task for every selected skill — reference the brand, objective, TA, and
exactly what aspect of the brief that skill should address. Vague tasks produce vague output.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 3 — OUTPUT (valid JSON only, no markdown fences)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Skills in the same array run in parallel. Arrays run sequentially.
proposal_assembler must be alone in the last array if included.

Case A — clarify:
{{"brief_update": {{"industry": null, "goal": null, "target_audience": null, "budget_vnd": null, "timeline": null, "additional_context": null}}, "needs_clarification": true, "clarification_message": "<1-3 warm questions in user's language>"}}

Case B — execute:
{{"brief_update": {{"industry": "<or null>", "goal": "<or null>", "target_audience": "<or null>", "budget_vnd": null, "timeline": null, "additional_context": null}}, "needs_clarification": false, "skill_plan": [[{{"skill": "<name>", "task": "<specific task>"}}]]}}"""


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
    _SEQUENTIAL = {"proposal_assembler"}

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
            plan.append([{"skill": "proposal_assembler",
                           "task": f"Reassemble proposal incorporating: {task_short}"}])
        return plan

    # Default: run all core skills
    return [[
        {"skill": s, "task": f"Analyze and provide insights for: {task_short}"}
        for s in core_skills
    ]]


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

    async def run(
        self, state: SalesCaseState, message: str
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Process a user message.
        Step 1: Casual check → greet if casual
        Step 2: Assess brief + plan → either clarify or execute
        Step 3A: If clarification needed → stream questions and stop
        Step 3B: If ready → execute skills in parallel
        Step 4: Synthesize and stream final response
        """

        # Step 1: Quick check — is this just a greeting/casual chat?
        if self._is_casual(message):
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

        # Step 3A: Brief incomplete → ask clarifying questions
        if assessment.get("needs_clarification"):
            clarification_msg = (
                assessment.get("clarification_message")
                or self._fallback_clarification(message)
            )
            yield {"type": "content", "content": clarification_msg}
            state.messages.append({
                "role": "assistant", "content": clarification_msg,
                "agent": "central_agent", "timestamp": datetime.now().isoformat(),
            })
            yield {"type": "done"}
            return

        # Step 3B: Brief clear → execute skills
        skill_plan: list[list[dict]] = assessment.get("skill_plan") or []
        if not skill_plan:
            skill_plan = _build_contextual_skill_plan(state, message)

        skill_registry = get_skill_registry()
        all_outputs: dict[str, SkillOutput] = {}

        def _safe_field(v: Any, field: str, default: Any) -> Any:
            """Safely read a field from either a dict or an object (handles old DB records)."""
            if isinstance(v, dict):
                return v.get(field, default) or default
            return getattr(v, field, default) or default

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
                    task=task_desc,
                    brief=state.brief,
                    # Keep a wider rolling window here because the session transcript
                    # is the primary source of cross-turn context for re-entrant skills.
                    messages=state.messages[-_RECENT_HISTORY_WINDOW:],
                    previous_outputs=merged_previous,
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

        # Step 4: Synthesize final response
        if all_outputs:
            async for event in self._synthesize(state, message, all_outputs):
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
            print(f"[CentralAgent] Assessment LLM failed ({e}), defaulting to execute mode")
            return {
                "brief_update": {},
                "needs_clarification": False,
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
        registry = get_skill_registry()
        skill_catalog = "\n".join(
            f"  {name}: {desc}"
            for name, desc in registry.descriptions().items()
        )
        system_prompt = _PLANNING_SYSTEM_TEMPLATE.format(skill_catalog=skill_catalog)

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
                max_tokens=1500,
                stream=False,
            ),
        )

        raw = response.choices[0].message.content or "{}"
        raw = strip_think_blocks(raw)
        raw = extract_json_block(raw)

        result = json.loads(raw)

        # Guard: if prior ASSISTANT turns exist, never re-clarify.
        prior_assistant_turns = [m for m in state.messages if m.get("role") == "assistant"]
        if prior_assistant_turns and result.get("needs_clarification"):
            result["needs_clarification"] = False

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

        return result

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

        # Detect whether this is the first response or a targeted follow-up.
        # Prior assistant turns = this is a follow-up; the user already has the full picture.
        is_followup = any(m.get("role") == "assistant" for m in state.messages)

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
  Use ONLY this format — one item per line, percentage first:
  35%  MiniApp Development
  25%  Voucher System
  15%  ZNS/Ads
  Wrap in a box like:
  ┌─────────────────────────────────────────┐
  │  BUDGET BREAKDOWN                       │
  ╠═════════════════════════════════════════╣
  │  35%  MiniApp Development               │
  │  25%  Voucher System                    │
  │  15%  ZNS/Ads                           │
  └─────────────────────────────────────────┘
  NEVER use █ block characters for bars.

DIAGRAMS (user flows, architecture):
  Use Mermaid in a ```mermaid block. Copy AS-IS from specialist outputs.
  NEVER write placeholder code blocks containing only a label like "Mermaid Gantt" or "Mermaid User Journey".
  If no Mermaid code is available, describe the flow as a numbered list instead.

TIMELINES / GANTT:
  Use Mermaid gantt syntax in a ```mermaid block. Copy AS-IS from specialist outputs.
  If no gantt code is available, use a Markdown table with Phase | Duration | Description columns."""

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

OUTPUT FORMAT GUIDE — follow these exactly so the UI renders correctly:

TABLES: Use Markdown pipe tables (| col | col |) — NEVER ASCII box-drawing tables.
BAR CHARTS: Use "NN%  Label" format one per line inside a ┌─╠═─┘ box — NEVER █ block chars.
DIAGRAMS: Copy ```mermaid blocks AS-IS from the analysis. If none available, use a numbered list.
TIMELINES: Copy ```mermaid gantt blocks AS-IS. If none, use a Markdown table (Phase | Duration | Description)."""

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
        queue: asyncio.Queue = asyncio.Queue(maxsize=512)
        _DONE = object()

        def _stream_worker() -> None:
            try:
                stream = client.create_completion(
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user_msg},
                    ],
                    temperature=0.5,
                    stream=True,
                )
                for chunk in stream:
                    loop.call_soon_threadsafe(queue.put_nowait, chunk)
            except Exception as exc:
                loop.call_soon_threadsafe(queue.put_nowait, exc)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, _DONE)

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
        state.validation_status = "READY"
        state.question_stack = []
        return AgentOutput(
            agent="central_agent", status="COMPLETE", payload={},
            summary="Ready to proceed.", confidence=0.9, questions=[],
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
