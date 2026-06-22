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


# ---------------------------------------------------------------------------
# Assessment + Planning prompt
# ---------------------------------------------------------------------------

_PLANNING_SYSTEM = """You are the AdtimaBox Sales AI — requirement assessment and planning engine.

Given the conversation and current brief, decide ONE of two actions:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ACTION A — CLARIFY (needs_clarification: true)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Use ONLY when BOTH of these are completely unknown:
  1. Industry / business sector of the brand
  2. Primary business objective (what outcome does the client want?)

When clarifying, prioritize questions from LAYER 0 (current state) first:
  • Does the brand have any existing loyalty / CRM / engagement program? What platform?
  • What does the current customer journey look like today? What are the key actors?
  • What is the single biggest pain point in the current flow?

Then LAYER 1 (objective) if needed:
  • Primary goal: acquire new leads / retain customers / increase purchase frequency / collect data / brand awareness?
  • What does success look like in 3–6 months?
  • Long-term loyalty platform or short-term campaign?

Rules for clarification:
  - Max 3 questions per turn — prioritize the most blocking unknowns
  - Write the message in the SAME LANGUAGE as the user's message
  - Warm and consultative tone — NOT interrogative. Group questions naturally
  - Do NOT ask about pricing, packages, or solutions in this phase

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ACTION B — EXECUTE (needs_clarification: false)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Use when ANY of these are true:
  • Industry or business sector is mentioned (FMCG, pharma, F&B, retail, finance…)
  • Goal is stated, even vaguely (loyalty, data collection, campaign, awareness…)
  • User mentions any Zalo product (ZNS, MiniApp, OA, ZBS, CShub)
  • User asks for pricing, proposal, strategy, wireframe, or analysis directly
  • Brief already has industry OR goal from previous turns
  • Message contains enough business context (50+ words describing a business problem)
  • User is continuing a conversation with clarification answers

When in doubt → EXECUTE. Skills handle missing info with reasonable assumptions.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AVAILABLE SKILLS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- market_strategy: market analysis, competitive landscape, consumer insight, case studies
- product_solution: package/pricing matching, MiniApp flow design, integration architecture, quotations
- compliance: Zalo platform policy, PDPL, Vietnamese advertising law, risk classification
- client_simulator: buyer objections, competitor defense, pitch coaching
- design: wireframes, Mermaid user flow diagrams, screen specifications, integration assessment
- proposal_assembler: final synthesis — assembles all skill outputs into a complete client-ready proposal document

Dispatch rules:
  - ALWAYS include market_strategy + product_solution for any sales or campaign request
  - Add compliance when: data collection, advertising content, pharma/FMCG health claims
  - Add client_simulator ONLY when user explicitly requests objection prep or pitch simulation
  - Add design ONLY when user explicitly requests wireframes, user flow diagrams, or solution design
  - Add proposal_assembler ONLY as a FINAL step after other skills complete — when user asks for a full proposal, presentation deck, or complete pitch document. MUST run after market_strategy + product_solution (not in parallel with them)
  - Group independent skills in the same parallel sub-array; proposal_assembler must be in its own sequential step

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT — return ONLY valid JSON, no markdown fences:

Case A (clarify):
{
  "brief_update": {"industry": null, "goal": null, "target_audience": null, "budget_vnd": null, "timeline": null, "additional_context": null},
  "needs_clarification": true,
  "clarification_message": "<warm message with 1-3 questions in user's language>"
}

Case B (execute):
{
  "brief_update": {"industry": null, "goal": null, "target_audience": null, "budget_vnd": null, "timeline": null, "additional_context": null},
  "needs_clarification": false,
  "skill_plan": [
    [{"skill": "market_strategy", "task": "<specific task>"}, {"skill": "product_solution", "task": "<specific task>"}],
    [{"skill": "proposal_assembler", "task": "<assemble full proposal from above outputs>"}]
  ]
}

Note: skill_plan is a list of parallel groups. Skills in the same group run concurrently. proposal_assembler MUST always be in its own group AFTER analysis skills."""


# ---------------------------------------------------------------------------
# Keyword-based fallback skill picker
# ---------------------------------------------------------------------------

def _pick_skills_from_message(message: str) -> list[list[dict[str, str]]]:
    """Fallback: pick skills by keyword scan without LLM. Returns a complete skill_plan."""
    msg = message.lower()
    first_group: list[dict[str, str]] = []

    if any(w in msg for w in ["brief", "campaign", "chien dich", "chien luoc", "market", "strategy",
                               "idea", "y tuong", "zalo", "brand", "audience", "ta:", "target",
                               "loyalty", "crm", "engagement"]):
        first_group.append({"skill": "market_strategy", "task": f"Analyze and develop market strategy for this request: {message[:500]}"})

    if any(w in msg for w in ["bao gia", "bao gi", "price", "gia", "quote", "solution",
                               "product", "miniapp", "mini app", "userflow", "flow", "package",
                               "cshub", "pricing", "tier"]):
        first_group.append({"skill": "product_solution", "task": f"Develop product solution, pricing, and userflow for: {message[:500]}"})

    if any(w in msg for w in ["data", "collect", "thu thap", "pdpl", "policy", "compliance",
                               "legal", "advertising", "quang cao", "zalo oa", "pharma", "duoc"]):
        first_group.append({"skill": "compliance", "task": f"Check compliance requirements for: {message[:500]}"})

    if any(w in msg for w in ["wireframe", "design", "ui", "screen", "man hinh", "giao dien", "figma",
                               "userflow", "flow diagram", "mermaid"]):
        first_group.append({"skill": "design", "task": f"Design solution and user flow for: {message[:500]}"})

    if any(w in msg for w in ["objection", "competitor", "pitch", "client sim", "simulate", "phan tich doi thu"]):
        first_group.append({"skill": "client_simulator", "task": f"Simulate client perspective for: {message[:500]}"})

    if not first_group:
        first_group = [
            {"skill": "market_strategy", "task": f"Analyze and provide market insights for: {message[:500]}"},
            {"skill": "product_solution", "task": f"Develop solution and pricing for: {message[:500]}"},
        ]

    plan: list[list[dict[str, str]]] = [first_group]

    # proposal_assembler runs as a final sequential step when a full proposal is explicitly requested
    if any(w in msg for w in ["full proposal", "de xuat day du", "presentation", "deck", "pitch deck",
                               "ban de xuat", "tong hop", "assemble", "complete proposal"]):
        plan.append([{"skill": "proposal_assembler", "task": f"Assemble complete client proposal from all skill outputs for: {message[:500]}"}])

    return plan


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
            skill_plan = _pick_skills_from_message(message)

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
                "skill_plan": _pick_skills_from_message(message),
            }

    async def _plan(self, state: SalesCaseState, message: str) -> dict[str, Any]:
        """Single LLM call: assess brief completeness, extract fields, decide clarify or execute."""
        from llm.greennode import get_llm_client

        client = get_llm_client("central_agent")

        brief_block = self._format_brief(state.brief)
        history_block = self._format_history(state.messages[-8:])

        user_prompt = ""
        if history_block:
            user_prompt += f"## Conversation History\n{history_block}\n\n"
        if brief_block and brief_block != "No brief yet.":
            user_prompt += f"## Current Brief\n{brief_block}\n\n"
        user_prompt += f"## Latest User Message\n{message}\n\nReturn assessment JSON."

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
                max_tokens=1500,
                stream=False,
            ),
        )

        raw = response.choices[0].message.content or "{}"
        raw = strip_think_blocks(raw)
        raw = extract_json_block(raw)

        result = json.loads(raw)

        # Safety: if skill_plan is empty in execute mode, add keyword fallback
        if not result.get("needs_clarification") and not result.get("skill_plan"):
            result["skill_plan"] = _pick_skills_from_message(message)

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
        _TOKEN_TIMEOUT = 60.0

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
        for m in messages[-8:]:
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
