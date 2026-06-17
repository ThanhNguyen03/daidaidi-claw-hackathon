"""
Sales Orchestrator
==================
Primary control plane for the multi-agent sales workflow.

Responsibilities:
- Validate the brief without assuming missing context
- Ask targeted clarifying questions only when required
- Build the execution plan from the actual brief and desired output
- Dispatch to the best-fit specialist agents
- Preserve the anti-loop guard and session question stack

This module is the runtime source of truth for `sales_orchestrator`.
Legacy modules re-export from here for backward compatibility only.
"""

from __future__ import annotations

import json
import asyncio
import os
import uuid
from typing import Optional

from agents.registry import get_registry
from repos.kb_repo import get_kb_repo
from schemas.state import (
    AgentOutput,
    AgentTask,
    Brief,
    ExecutionPlan,
    NeedsRequest,
    Question,
    SalesCaseState,
)
from validation.question_stack import get_question_manager
from validation.validator import get_validation_service


DEFAULT_MAX_HOP_DEPTH = 4


class Orchestrator:
    """Central orchestrator for validation, planning, and routing."""

    def __init__(self, max_hop_depth: int = DEFAULT_MAX_HOP_DEPTH):
        self.name = "sales_orchestrator"
        self.role_description = "Supervisor that validates briefs, asks clarifying questions, and routes tasks to specialists"
        self.max_hop_depth = max_hop_depth

        # Load SKILL.md directly from file — always available, never depends on KB being populated
        _here = os.path.dirname(os.path.abspath(__file__))
        skill_path = os.path.join(_here, "SKILL.md")
        self._skill_content: str = ""
        try:
            with open(skill_path, "r", encoding="utf-8") as _f:
                self._skill_content = _f.read()
        except Exception as _e:
            print(f"Warning: Could not load orchestrator SKILL.md from {skill_path}: {_e}")

    async def _rag_search(
        self, query: str, doc_type: str, top_k: int
    ) -> list[object]:
        """Search the KB for orchestrator-specific skill/knowledge context."""
        try:
            kb = get_kb_repo()
            return await kb.search(
                query,
                top_k=top_k,
                filters={"agent": "sales_orchestrator", "type": doc_type},
            )
        except Exception as exc:
            print(f"Warning: KB {doc_type} search failed for sales_orchestrator: {exc}")
            return []

    async def build_required_skill_context(
        self,
        query: str,
        skill_top_k: int = 1,
        knowledge_top_k: int = 3,
    ) -> str:
        """Build orchestrator skill/knowledge context with at least one skill hit."""
        skills, knowledge = await asyncio.gather(
            self._rag_search(query, "skill", skill_top_k),
            self._rag_search(query, "knowledge", knowledge_top_k),
        )

        if not skills:
            print("Warning: No skill context retrieved for sales_orchestrator, falling back to knowledge-only context")

        parts: list[str] = []
        if skills:
            parts.append("\n\n" + "=" * 60)
            parts.append("RELEVANT SKILL / PROCEDURE:")
            parts.append("=" * 60)
            for r in skills:
                parts.append(f"\n[{r.source}]\n{r.content}")

        if knowledge:
            parts.append("\n\n" + "=" * 60)
            parts.append("RELEVANT KNOWLEDGE:")
            parts.append("=" * 60)
            for r in knowledge:
                parts.append(f"\n[{r.source}]\n{r.content}")

        return "\n".join(parts) if parts else ""

    def _latest_user_message(self, state: SalesCaseState) -> str:
        for msg in reversed(state.messages):
            if msg.get("role") == "user":
                return msg.get("content", "")
        return ""

    def _count_consecutive_casual_rounds(self, state: SalesCaseState) -> int:
        """Count consecutive casual-style assistant turns at the tail of history.

        A short assistant reply (< 200 chars, no structured content) is a proxy
        for a casual exchange.  We stop counting as soon as we see a substantive
        reply, so the result is the number of uninterrupted casual back-and-forths
        that happened *before* the current user message.
        """
        count = 0
        for msg in reversed(state.messages):
            role = msg.get("role", "")
            content = (msg.get("content") or "").strip()
            if role == "assistant":
                # Heuristic: short reply with no markdown structure → casual
                if len(content) < 220 and "\n\n" not in content and "##" not in content:
                    count += 1
                else:
                    break
        return count

    def _recent_conversation_snippet(self, state: SalesCaseState, n: int = 6) -> str:
        """Return the last n messages as a compact transcript for LLM context."""
        tail = state.messages[-n:] if len(state.messages) >= n else state.messages
        lines = []
        for msg in tail:
            role = msg.get("role", "user")
            content = (msg.get("content") or "").strip()[:300]
            lines.append(f"{role.upper()}: {content}")
        return "\n".join(lines)

    def _question_manager_for_state(self, state: SalesCaseState):
        question_manager = get_question_manager()
        question_manager.ensure_session(state.session_id)
        if state.question_stack:
            question_manager.restore_stack(state.question_stack)
        return question_manager

    def _orchestrator_agent(self):
        agent = get_registry().get("sales_orchestrator")
        if agent is None:
            raise RuntimeError("sales_orchestrator agent is not registered")
        return agent

    def _requirement_agent(self):
        agent = get_registry().get("requirement_elicitation")
        if agent is None:
            raise RuntimeError("requirement_elicitation agent is not registered")
        return agent

    def _brief_has_substance(self, brief: Optional[Brief]) -> bool:
        if not brief:
            return False

        has_structured = any(
            getattr(brief, field, None)
            for field in [
                "industry",
                "goal",
                "target_audience",
                "budget_vnd",
                "timeline",
                "specific_requirements",
                "constraints",
            ]
        )
        if has_structured:
            return True
        # Rich free-text context counts as substance (e.g. when extraction LLM failed)
        additional = getattr(brief, "additional_context", None) or ""
        return len(additional) > 50

    def _merge_brief(self, base: Optional[Brief], extracted: Brief) -> Brief:
        base = base or Brief()
        merged = base.model_dump(mode="python")
        extracted_data = extracted.model_dump(mode="python")

        for field, value in extracted_data.items():
            if value in (None, "", [], {}):
                continue
            if field in {"specific_requirements", "constraints"}:
                existing = list(merged.get(field) or [])
                for item in value:
                    if item not in existing:
                        existing.append(item)
                merged[field] = existing
            else:
                merged[field] = value

        return Brief.model_validate(merged)

    async def _classify_user_message(self, state: SalesCaseState) -> dict[str, str]:
        """Use the LLM to decide whether a message is casual chat or a sales request."""
        message = self._latest_user_message(state).strip()
        if not message:
            return {
                "intent": "casual_chat",
                "assistant_reply": "Hi, mình có thể giúp bạn bắt đầu một brief hoặc trả lời câu hỏi sales.",
            }

        # Use a dual-purpose query: routing classification + brand identity for potential greeting
        rag_context = await self.build_required_skill_context(
            f"Sales agent identity, company introduction, greeting user. Routing context: {message}",
            skill_top_k=1,
            knowledge_top_k=3,
        )
        client = get_validation_service().client

        casual_rounds = self._count_consecutive_casual_rounds(state)
        recent_convo = self._recent_conversation_snippet(state, n=6)

        context = []
        if state.brief:
            if self._brief_has_substance(state.brief):
                context.append("The session already contains a real brief.")
            elif state.brief.additional_context:
                context.append("The session only has raw additional_context so far.")

        suggest_rule = ""
        if casual_rounds >= 1:
            suggest_rule = (
                f"- IMPORTANT: The user has sent {casual_rounds} casual message(s) in a row without requesting "
                "any sales work. If this message is also casual_chat, naturally weave 2-3 concrete suggested "
                "starter questions into your reply (e.g. 'Bạn muốn lập brief cho chiến dịch nào?' or "
                "'Mình có thể giúp bạn tạo proposal cho dự án gì?'). Do NOT list them as a menu — "
                "integrate them organically into the reply. Keep the overall tone warm and inviting."
            )

        prompt = f"""
Classify the user's latest message for a sales assistant.

Return JSON only with:
{{
  "intent": "casual_chat" | "sales_request",
  "assistant_reply": "reply for casual_chat — see rules below, otherwise empty string",
  "reason": "brief explanation"
}}

Rules:
- casual_chat: greeting, thanks, small talk, one-line non-sales message, or anything not asking for sales help.
- sales_request: the user is asking for a brief, proposal, quote, deck, strategy, or providing project details.
- If the message is ambiguous but looks like a sales request, choose sales_request.
- For casual_chat assistant_reply: Use the company name, product, and agent persona from your system context to write a warm, on-brand reply. Introduce yourself naturally (e.g. AdtimaBox Sales Agent). Reply in the same language as the user's message. Keep it concise (1-3 sentences).
- Do not mention internal routing, pipeline stages, agent names, or layer names.
{suggest_rule}

Latest message:
{message}

Recent conversation (last few turns):
{recent_convo if recent_convo else "none"}

Session context:
{chr(10).join(context) if context else "none"}
"""

        # Use SKILL.md loaded from file as base system prompt — guaranteed available even when KB empty
        classify_system = self._skill_content or "You are a routing classifier for a sales assistant."
        if rag_context:
            classify_system = classify_system + "\n\n" + rag_context

        try:
            response = await client.async_create_completion(
                messages=[
                    {"role": "system", "content": classify_system},
                    {"role": "user", "content": prompt},
                ],
                stream=False,
                temperature=0.1,
                max_tokens=500,
            )
            content = response.choices[0].message.content if response.choices else "{}"
            if "```json" in content:
                content = content.split("```json", 1)[1].split("```", 1)[0]
            elif "```" in content:
                content = content.split("```", 1)[1].split("```", 1)[0]
            data = json.loads(content.strip() or "{}")
            intent = str(data.get("intent", "sales_request")).strip()
            if intent not in {"casual_chat", "sales_request"}:
                intent = "sales_request"
            return {
                "intent": intent,
                "assistant_reply": str(data.get("assistant_reply", "")).strip(),
                "reason": str(data.get("reason", "")).strip(),
            }
        except Exception as exc:
            print(f"Warning: message classification failed, defaulting to sales_request: {exc}")
            return {
                "intent": "sales_request",
                "assistant_reply": "",
                "reason": "classifier_error",
            }

    async def _extract_brief_from_message(self, message: str) -> Brief:
        """Use the LLM to extract a structured brief from free-form user text."""
        rag_context = await self.build_required_skill_context(
            f"Extract a structured sales brief from this user message.\nMessage: {message}",
            skill_top_k=1,
            knowledge_top_k=3,
        )
        client = get_validation_service().client
        system = (
            "You are a brief parser for a sales AI system. "
            "Extract structured campaign/sales brief data from the user message. "
            "Return ONLY a JSON object with these optional fields:\n"
            '{"industry": str|null, "goal": str|null, "target_audience": str|null, '
            '"budget_vnd": int|null, "timeline": str|null, '
            '"specific_requirements": [str], "constraints": [str], "additional_context": str|null}\n'
            "If a field is absent, use null or []. No markdown, no extra text."
        )

        try:
            response = await client.async_create_completion(
                messages=[
                    {"role": "system", "content": system + "\n\n" + rag_context},
                    {"role": "user", "content": f"Parse this brief:\n{message}"},
                ],
                stream=False,
                max_tokens=600,
                temperature=0.1,
            )
            raw = response.choices[0].message.content.strip() if response.choices else "{}"
        except Exception as exc:
            print(f"Warning: brief extraction LLM call failed: {exc}")
            return Brief(additional_context=message[:1000])

        if "```" in raw:
            raw = raw.split("```", 1)[1]
            if raw.startswith("json"):
                raw = raw[4:]

        try:
            data = json.loads(raw)
        except Exception:
            return Brief(additional_context=message[:1000])

        return Brief(
            industry=data.get("industry"),
            goal=data.get("goal"),
            target_audience=data.get("target_audience"),
            budget_vnd=data.get("budget_vnd"),
            timeline=data.get("timeline"),
            specific_requirements=data.get("specific_requirements") or [],
            constraints=data.get("constraints") or [],
            additional_context=data.get("additional_context"),
        )

    async def _extract_desired_outputs(self, message: str) -> list[str]:
        """Use the LLM to infer the requested output formats from user text."""
        rag_context = await self.build_required_skill_context(
            f"Infer requested deliverables from this user message.\nMessage: {message}",
            skill_top_k=1,
            knowledge_top_k=2,
        )
        client = get_validation_service().client
        prompt = f"""
Infer which deliverables the user wants from this message.

Return JSON only in this shape:
{{
  "outputs": ["pptx" | "figma" | "userflow" | "quote"]
}}

Rules:
- Include only outputs explicitly requested or clearly implied.
- Use an empty array if no deliverable is requested.
- Do not add any extra text.

Message:
{message}
"""

        try:
            response = await client.async_create_completion(
                messages=[
                    {
                        "role": "system",
                        "content": "You extract requested deliverables from sales chat.\n\n"
                        + rag_context,
                    },
                    {"role": "user", "content": prompt},
                ],
                stream=False,
                temperature=0.1,
                max_tokens=200,
            )
            content = response.choices[0].message.content if response.choices else "{}"
            if "```json" in content:
                content = content.split("```json", 1)[1].split("```", 1)[0]
            elif "```" in content:
                content = content.split("```", 1)[1].split("```", 1)[0]
            data = json.loads(content.strip() or "{}")
            outputs = []
            for item in data.get("outputs", []):
                item = str(item).strip().lower()
                if item in {"pptx", "figma", "userflow", "quote"} and item not in outputs:
                    outputs.append(item)
            return outputs
        except Exception as exc:
            print(f"Warning: desired output extraction failed: {exc}")
            return []

    async def extract_desired_outputs(self, message: str) -> list[str]:
        """Public wrapper for desired output inference."""
        return await self._extract_desired_outputs(message)

    async def _generate_questions(
        self,
        state: SalesCaseState,
        missing_fields: list[str],
        ambiguities: list,
    ) -> list[Question]:
        """Generate clarifying questions using orchestrator's SKILL.md + LLM reasoning."""
        if not missing_fields and not ambiguities:
            return []

        rag_context = await self.build_required_skill_context(
            f"Clarifying questions for sales brief missing: {', '.join(missing_fields)}",
            skill_top_k=1,
            knowledge_top_k=2,
        )
        system_prompt = self._skill_content or "You are a sales assistant orchestrator."
        if rag_context:
            system_prompt = system_prompt + "\n\n" + rag_context

        brief = state.brief
        message = self._latest_user_message(state) or ""

        brief_parts: list[str] = []
        if brief:
            for field in ["industry", "goal", "target_audience", "budget_vnd", "timeline"]:
                val = getattr(brief, field, None)
                if val:
                    brief_parts.append(f"{field}: {val}")
            if brief.additional_context:
                brief_parts.append(f"context: {brief.additional_context[:300]}")
        brief_summary = "\n".join(brief_parts) or "(no structured brief)"

        ambiguity_text = ""
        if ambiguities:
            ambiguity_text = "\nAmbiguous fields: " + ", ".join(
                getattr(a, "field", str(a)) for a in ambiguities
            )

        prompt = f"""Generate at most 3 concise clarifying questions to get the information needed to proceed with this sales brief.

Missing required fields: {", ".join(missing_fields)}
{ambiguity_text}

Current brief:
{brief_summary}

User's latest message:
{message[:500]}

Rules:
- Ask only what is truly blocking the next step. Fewer questions is better.
- Write questions in plain language, matching the user's language (Vietnamese or English).
- Do NOT mention internal terms: Layer, Gate, pipeline stages, agent names, or framework terms.
- Do NOT assume or invent values.

Return JSON only:
{{"questions": [{{"field": "...", "text": "...", "priority": 1, "is_mandatory": true, "options": null}}]}}
"""

        client = get_validation_service().client
        try:
            response = await client.async_create_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                stream=False,
                temperature=0.2,
                max_tokens=600,
            )
            content = response.choices[0].message.content if response.choices else "{}"
            if "```json" in content:
                content = content.split("```json", 1)[1].split("```", 1)[0]
            elif "```" in content:
                content = content.split("```", 1)[1].split("```", 1)[0]

            data = json.loads(content.strip() or "{}")
            questions: list[Question] = []
            for item in data.get("questions", [])[:3]:
                field = item.get("field")
                text = item.get("text")
                if not field or not text:
                    continue
                questions.append(
                    Question(
                        id=f"orchestrator_{field}",
                        text=text,
                        priority=int(item.get("priority", 1)),
                        is_mandatory=bool(item.get("is_mandatory", True)),
                        assumption=None,
                        target_field=field,
                        options=item.get("options"),
                    )
                )
            return questions
        except Exception as exc:
            print(f"Warning: orchestrator question generation failed: {exc}")
            return []

    async def validate_before_dispatch(
        self, state: SalesCaseState
    ) -> tuple[AgentOutput, bool]:
        """Validate the brief before dispatching any agent."""
        question_manager = self._question_manager_for_state(state)

        classification = await self._classify_user_message(state)
        if classification.get("intent") == "casual_chat":
            state.validation_status = "READY"
            return (
                AgentOutput(
                    agent="sales_orchestrator",
                    status="COMPLETE",
                    payload={
                        "intent": "casual_chat",
                        "assistant_reply": classification.get("assistant_reply", ""),
                        "reason": classification.get("reason", ""),
                    },
                    summary=classification.get(
                        "assistant_reply",
                        "Hi, mình có thể giúp bạn bắt đầu một brief hoặc trả lời câu hỏi sales.",
                    ),
                    confidence=0.9,
                ),
                False,
            )

        if not self._brief_has_substance(state.brief):
            # Seed raw user text as context instead of inventing structure.
            state.brief = await self._extract_brief_from_message(
                self._latest_user_message(state) or ""
            )

        if not state.desired_outputs:
            inferred_outputs = await self._extract_desired_outputs(
                self._latest_user_message(state) or ""
            )
            if inferred_outputs:
                state.desired_outputs = inferred_outputs

        validation_service = get_validation_service()
        validation_report = await validation_service.validate(
            brief=state.brief,
            profile=state.profile,
            mode=state.mode,
        )
        state.validation_report = validation_report
        state.validation_status = validation_report.status

        if validation_report.status == "BLOCKED":
            return (
                AgentOutput(
                    agent="sales_orchestrator",
                    status="FAILED",
                    payload={
                        "validation_status": "BLOCKED",
                        "missing_required": validation_report.missing_required,
                    },
                    summary="This request is out of scope. Please provide a valid sales brief.",
                    confidence=1.0,
                ),
                False,
            )

        if validation_report.status == "PENDING":
            # Questions are optional — generate them but still dispatch agents
            questions = await self._generate_questions(
                state,
                missing_fields=validation_report.missing_required or [],
                ambiguities=validation_report.ambiguities or [],
            )
            if questions:
                question_manager.stack.push(questions)
                state.question_stack = question_manager.stack.items
            else:
                state.question_stack = question_manager.stack.items

            if validation_report.missing_required:
                summary = f"Mình sẽ tiếp tục với thông tin hiện có. Bạn có thể bổ sung: {', '.join(validation_report.missing_required)}."
            else:
                summary = "Tiếp tục với thông tin hiện có."

            return (
                AgentOutput(
                    agent="sales_orchestrator",
                    status="NEEDS_INPUT",
                    payload={
                        "validation_status": "PENDING",
                        "missing_required": validation_report.missing_required,
                        "ambiguities": [amb.model_dump() for amb in validation_report.ambiguities],
                    },
                    summary=summary,
                    confidence=0.85,
                    questions=questions,
                ),
                True,  # still dispatch — questions are optional, not blocking
            )

        state.question_stack = question_manager.stack.items
        return (
            AgentOutput(
                agent="sales_orchestrator",
                status="COMPLETE",
                payload={"validation_status": "READY"},
                summary="Validation passed - proceeding with agent dispatch",
                confidence=1.0,
            ),
            True,
        )

    async def handle_validation_response(
        self, state: SalesCaseState, answers: dict[str, str]
    ) -> AgentOutput:
        """Apply user answers to the brief and revalidate."""
        question_manager = self._question_manager_for_state(state)
        if len(answers) == 1 and "free_text" in answers:
            extracted = await self._extract_brief_from_message(answers["free_text"])
            state.brief = self._merge_brief(state.brief, extracted)
        else:
            state.brief = question_manager.map_answers(answers, state.brief or Brief())

        validation_output, should_dispatch = await self.validate_before_dispatch(state)
        if should_dispatch:
            question_manager.stack.clear_answered()
            state.question_stack = question_manager.stack.items
        return validation_output

    async def handle_severity_gated_revalidation(
        self, state: SalesCaseState, old_brief: Brief
    ) -> tuple[AgentOutput, bool]:
        validation_service = get_validation_service()
        _report, should_revalidate = await validation_service.validate_with_severity(
            brief=state.brief,
            profile=state.profile,
            mode=state.mode,
            old_brief=old_brief,
        )

        if should_revalidate:
            return await self.validate_before_dispatch(state)

        return (
            AgentOutput(
                agent="sales_orchestrator",
                status="COMPLETE",
                payload={"revalidation": "skipped", "reason": "non-critical edit"},
                summary="Changes saved - no re-validation needed",
                confidence=1.0,
            ),
            True,
        )

    async def run(self, state: SalesCaseState) -> AgentOutput:
        """Validate, plan, and dispatch the next step."""
        validation_output, should_dispatch = await self.validate_before_dispatch(state)
        if not should_dispatch:
            return validation_output

        if not state.plan or not state.plan.tasks:
            state.plan = await self._create_execution_plan(state)

        if not state.plan.tasks:
            return AgentOutput(
                agent="sales_orchestrator",
                status="COMPLETE",
                payload={"summary": "All tasks completed"},
                summary="All agents have completed their work. Here's the summary:",
                confidence=1.0,
            )

        next_task = self._get_next_task(state)
        if next_task is None:
            return AgentOutput(
                agent="sales_orchestrator",
                status="COMPLETE",
                payload={"summary": "No more tasks to execute"},
                summary="All planned tasks have been executed.",
                confidence=1.0,
            )

        if next_task.agent_name in state.visited:
            if state.hop_depth >= self.max_hop_depth:
                return AgentOutput(
                    agent="sales_orchestrator",
                    status="FAILED",
                    payload={
                        "error": "max_hop_depth_exceeded",
                        "message": f"Maximum hop depth ({self.max_hop_depth}) reached",
                    },
                    summary=f"Cannot dispatch to {next_task.agent_name} - would exceed maximum hop depth. Please rephrase your request.",
                    confidence=1.0,
                )

            return AgentOutput(
                agent="sales_orchestrator",
                status="NEEDS_INPUT",
                payload={
                    "agent_requested": next_task.agent_name,
                    "already_visited": state.visited,
                },
                summary=f"You've already consulted {next_task.agent_name} in this session. Do you want to consult them again for updated insights?",
                confidence=0.9,
                questions=[
                    Question(
                        id=str(uuid.uuid4()),
                        text=f"Would you like to consult {next_task.agent_name} again?",
                        priority=1,
                        is_mandatory=False,
                        target_field="reuse_agent",
                    )
                ],
            )

        state.visited.append(next_task.agent_name)
        state.hop_depth += 1

        return AgentOutput(
            agent="sales_orchestrator",
            status="NEEDS_AGENT",
            payload={
                "next_task": next_task.model_dump(),
                "visited": state.visited,
                "hop_depth": state.hop_depth,
            },
            summary=f"Dispatching to {next_task.agent_name}...",
            confidence=0.9,
            needs=NeedsRequest(
                agent=next_task.agent_name,
                reason=next_task.task_description,
                context={"task": next_task.model_dump()},
            ),
        )

    async def _create_execution_plan(self, state: SalesCaseState) -> ExecutionPlan:
        """Use LLM reasoning to decide which agents to dispatch and in what order."""
        registry = get_registry()
        available_agents = [
            a for a in registry.all() if a.name != "sales_orchestrator"
        ]
        agent_descriptions = "\n".join(
            f"- {a.name}: {a.role_description}" for a in available_agents
        )

        message = self._latest_user_message(state) or ""
        brief_parts = []
        if state.brief:
            b = state.brief
            if b.industry: brief_parts.append(f"Industry: {b.industry}")
            if b.goal: brief_parts.append(f"Goal: {b.goal}")
            if b.target_audience: brief_parts.append(f"Target audience: {b.target_audience}")
            if b.budget_vnd: brief_parts.append(f"Budget: {b.budget_vnd:,} VND")
            if b.timeline: brief_parts.append(f"Timeline: {b.timeline}")
            if b.specific_requirements:
                brief_parts.append(f"Requirements: {', '.join(b.specific_requirements)}")
            if b.constraints:
                brief_parts.append(f"Constraints: {', '.join(b.constraints)}")
            if b.additional_context:
                brief_parts.append(f"Context: {b.additional_context[:300]}")
        brief_summary = "\n".join(brief_parts) if brief_parts else "(no structured brief yet)"
        desired_outputs = ", ".join(state.desired_outputs) if state.desired_outputs else "not specified"

        rag_context = await self.build_required_skill_context(
            f"Plan agent dispatch for: {message[:200]}",
            skill_top_k=1,
            knowledge_top_k=2,
        )

        prompt = f"""You are the orchestrator of a multi-agent sales assistant. Your only job here is to decide WHICH specialist agents to dispatch, in what order and grouping, based on what the user actually needs.

Available specialist agents:
{agent_descriptions}

User message: {message[:500]}

Brief summary:
{brief_summary}

Desired output formats: {desired_outputs}

Orchestrator skill context:
{rag_context}

Instructions:
1. Choose ONLY the agents genuinely needed for this request. Fewer is better when the request is narrow.
2. requirement_elicitation MUST always run first (parallel_group=1, is_critical=true).
3. Agents in the same parallel_group run concurrently. Higher group numbers run after lower ones.
4. Write a specific task_description per agent grounded in the actual brief, not generic descriptions.
5. Include design/client_simulator only when the user explicitly requests deliverables (pptx, deck, wireframe, userflow).

Return ONLY a JSON array — no markdown, no extra text:
[
  {{
    "agent_name": "requirement_elicitation",
    "task_description": "...",
    "parallel_group": 1,
    "is_critical": true
  }},
  ...
]
"""

        client = get_validation_service().client
        try:
            response = await client.async_create_completion(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a routing orchestrator for a multi-agent sales system. Return only valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                stream=False,
                temperature=0.1,
                max_tokens=800,
            )
            content = response.choices[0].message.content if response.choices else "[]"
            if "```json" in content:
                content = content.split("```json", 1)[1].split("```", 1)[0]
            elif "```" in content:
                content = content.split("```", 1)[1].split("```", 1)[0]

            raw_tasks = json.loads(content.strip() or "[]")
            tasks: list[AgentTask] = []
            for raw_task in raw_tasks:
                agent_name = str(raw_task.get("agent_name", "")).strip()
                if not agent_name or not registry.get(agent_name):
                    continue
                if any(t.agent_name == agent_name for t in tasks):
                    continue
                tasks.append(AgentTask(
                    agent_name=agent_name,
                    task_description=str(raw_task.get("task_description", f"Process request for {agent_name}")),
                    depends_on=[],
                    is_critical=bool(raw_task.get("is_critical", False)),
                    parallel_group=int(raw_task.get("parallel_group", 1)),
                ))

            if tasks:
                return ExecutionPlan(
                    tasks=tasks,
                    execution_mode="hybrid",
                    estimated_duration_minutes=len(tasks) * 3,
                )
        except Exception as exc:
            print(f"Warning: LLM execution plan failed, using default plan: {exc}")

        return self._create_default_execution_plan(state)

    def _create_default_execution_plan(self, state: SalesCaseState) -> ExecutionPlan:
        """Fallback hard-coded execution plan when LLM-based planning fails."""
        registry = get_registry()
        tasks: list[AgentTask] = []
        requested_outputs = set(state.desired_outputs or [])

        def _add(name: str, description: str, group: int, critical: bool = False):
            if registry.get(name) and not any(task.agent_name == name for task in tasks):
                tasks.append(
                    AgentTask(
                        agent_name=name,
                        task_description=description,
                        depends_on=[],
                        is_critical=critical,
                        parallel_group=group,
                    )
                )

        _add(
            "requirement_elicitation",
            "Translate the brief into a structured requirement summary, surface unknowns, and request missing context only when needed",
            group=1,
            critical=True,
        )
        _add(
            "market_strategy",
            "Industry mapping, pain point framing, solution package selection, and case-study RAG",
            group=2,
            critical=True,
        )
        _add(
            "compliance",
            "PDPL check, consent language, data collection rules, and risk flags",
            group=2,
        )
        _add(
            "product_solution",
            "Merged product solution, pricing reference, integration fit, and solution packaging",
            group=2,
        )

        if requested_outputs:
            _add(
                "design",
                "Wireframe and slide outline - deck structure, section order, visual hints",
                group=3,
            )
            _add(
                "client_simulator",
                "Simulate client pushback and flag weak points before AE review",
                group=4,
            )

        return ExecutionPlan(
            tasks=tasks,
            execution_mode="hybrid",
            estimated_duration_minutes=len(tasks) * 3,
        )

    def _get_next_task(self, state: SalesCaseState) -> Optional[AgentTask]:
        if not state.plan or not state.plan.tasks:
            return None
        for task in state.plan.tasks:
            if task.agent_name not in state.visited:
                return task
        return None

    def handle_agent_result(self, state: SalesCaseState, agent_output: AgentOutput) -> AgentOutput:
        state.outputs[agent_output.agent] = agent_output

        if agent_output.status == "FAILED":
            task = self._find_task_for_agent(state, agent_output.agent)
            if task and task.is_critical:
                return AgentOutput(
                    agent="sales_orchestrator",
                    status="FAILED",
                    payload={"failed_agent": agent_output.agent, "error": agent_output.summary},
                    summary=f"Critical agent {agent_output.agent} failed: {agent_output.summary}",
                    confidence=1.0,
                )

        if agent_output.status == "NEEDS_INPUT":
            return agent_output

        if agent_output.needs:
            if agent_output.needs.agent in state.visited:
                return AgentOutput(
                    agent="sales_orchestrator",
                    status="NEEDS_INPUT",
                    payload={
                        "original_request": agent_output.needs.model_dump(),
                        "already_visited": state.visited,
                    },
                    summary=f"Cannot fulfill request to consult {agent_output.needs.agent} - this agent has already been consulted in this session. Would you like to continue without additional input from them?",
                    confidence=0.9,
                    questions=[
                        Question(
                            id=str(uuid.uuid4()),
                            text=f"Should I proceed without consulting {agent_output.needs.agent} again?",
                            priority=1,
                            is_mandatory=False,
                            target_field="proceed_without_agent",
                        )
                    ],
                )
            state.visited.append(agent_output.needs.agent)

        return self.run(state)

    def _find_task_for_agent(self, state: SalesCaseState, agent_name: str) -> Optional[AgentTask]:
        if not state.plan:
            return None
        for task in state.plan.tasks:
            if task.agent_name == agent_name:
                return task
        return None


_sales_orchestrator: Optional[Orchestrator] = None


def get_sales_orchestrator() -> Orchestrator:
    global _sales_orchestrator
    if _sales_orchestrator is None:
        _sales_orchestrator = Orchestrator()
    return _sales_orchestrator


def get_orchestrator() -> Orchestrator:
    return get_sales_orchestrator()
