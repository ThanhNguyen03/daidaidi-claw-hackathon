"""
Client Simulator Agent
======================
Adversarial proposal reviewer that stress-tests the deck from a client
perspective and returns concrete objections, weak points, and risks.
"""

from __future__ import annotations

import os
from typing import Optional

from agents.base import BaseAgent
from llm.greennode import get_llm_client
from schemas.state import AgentOutput, SalesCaseState


class ClientSimulatorAgent(BaseAgent):
    def __init__(self, **kwargs):
        _here = os.path.dirname(os.path.abspath(__file__))
        super().__init__(
            name="client_simulator",
            model_key="MODEL_CLIENT_SIMULATOR",
            role_description="Adversarial client simulator and proposal reviewer",
            prompt_path=os.path.join(_here, "SKILL.md"),
            knowledge_dir=os.path.join(_here, "reference"),
            skills_dir=os.path.join(_here, "reference"),
            **kwargs,
        )

    def _latest_user_message(self, state: SalesCaseState) -> str:
        for msg in reversed(state.messages):
            if msg.get("role") == "user":
                return msg.get("content", "")
        return ""

    def _gather_context(self, state: SalesCaseState) -> dict:
        outputs = state.outputs or {}
        return {
            "market_strategy": outputs.get("market_strategy").payload if outputs.get("market_strategy") else {},
            "product_solution": outputs.get("product_solution").payload if outputs.get("product_solution") else {},
            "design": outputs.get("design").payload if outputs.get("design") else {},
            "compliance": outputs.get("compliance").payload if outputs.get("compliance") else {},
        }

    def _fallback_review(self, state: SalesCaseState) -> dict:
        context = self._gather_context(state)
        brief = state.brief
        objections = []
        weak_points = []
        risks = []
        recommendations = []

        product = context.get("product_solution") or {}
        design = context.get("design") or {}
        market = context.get("market_strategy") or {}

        if not product:
            objections.append({"text": "Phần giải pháp / pricing chưa đủ rõ để đánh giá ROI.", "severity": "high"})
            weak_points.append("Thiếu cấu trúc giải pháp hoặc pricing breakdown cụ thể")
            risks.append("Client sẽ dừng ở bước pricing nếu không thấy line-item rõ ràng")

        if not design:
            objections.append({"text": "Không có wireframe / slide flow cụ thể nên khó tin tưởng proposal.", "severity": "medium"})
            weak_points.append("Thiếu mạch trình bày trực quan và flow triển khai")

        if not market:
            objections.append({"text": "Chưa thấy luận điểm thị trường / case study đủ mạnh.", "severity": "medium"})
            weak_points.append("Thiếu social proof và positioning")

        if brief and brief.budget_vnd and product.get("pricing_breakdown", {}).get("total_vnd"):
            total = product["pricing_breakdown"]["total_vnd"]
            if total > brief.budget_vnd:
                objections.append({"text": "Giá vượt ngân sách dự kiến.", "severity": "high"})
                risks.append("Budget mismatch")
                recommendations.append("Tách scope thành base package và add-on tùy chọn")

        scores = {
            "clarity": 3 if design else 2,
            "credibility": 3 if market else 2,
            "value_prop": 3 if product else 2,
            "pricing": 3 if product else 1,
        }

        recommendations.extend([
            "Rút gọn luận điểm thành 3 gạch đầu dòng dễ pitch",
            "Thêm một downside scenario để giảm nghi ngại ROI",
            "Làm rõ phần nào là included, phần nào là pending confirmation",
        ])

        return {
            "objections": objections,
            "weak_points": weak_points,
            "risks": risks,
            "scores": scores,
            "recommendations": recommendations,
        }

    async def run(self, state: SalesCaseState) -> AgentOutput:
        context = self._gather_context(state)
        user_message = self._latest_user_message(state)

        if not any(context.values()):
            return AgentOutput(
                agent=self.name,
                status="NEEDS_INPUT",
                payload={"missing_context": ["market_strategy", "product_solution", "design"]},
                summary="Need proposal context or generated artifacts before simulating client objections.",
                confidence=0.9,
                needs=None,
                questions=[],
            )

        query = " ".join([
            "client simulator",
            state.brief.industry if state.brief and state.brief.industry else "",
            state.brief.goal if state.brief and state.brief.goal else "",
            user_message,
        ]).strip()
        rag_context = await self.build_required_skill_context(query, skill_top_k=2, knowledge_top_k=3)
        system_prompt = self.system_prompt + rag_context

        prompt = f"""You are a skeptical client reviewing a sales proposal.

Use only the provided context and internal references. Be adversarial but constructive.
Do not invent product claims beyond the proposal inputs.

Proposal context:
{context}

User message:
{user_message or 'No extra message provided'}

Return JSON with:
- objections: list of objects with text and severity (high|medium|low)
- weak_points: list of concrete weaknesses
- risks: list of deal-killing or pitch-risk items
- scores: object with clarity, credibility, value_prop, pricing scores from 1 to 5
- recommendations: actionable fixes
"""

        try:
            client = get_llm_client(self.name)
            response = client.create_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                stream=False,
                temperature=0.4,
                max_tokens=1800,
            )
            content = response.choices[0].message.content if response.choices else ""
            if content:
                return AgentOutput(
                    agent=self.name,
                    status="COMPLETE",
                    payload={
                        "review": content,
                        "rag_used": bool(rag_context),
                        "context_keys": [k for k, v in context.items() if v],
                    },
                    summary="Client simulation completed",
                    confidence=0.85 if rag_context else 0.7,
                    needs=None,
                    questions=[],
                )
        except Exception:
            pass

        fallback = self._fallback_review(state)
        return AgentOutput(
            agent=self.name,
            status="COMPLETE",
            payload={
                **fallback,
                "rag_used": bool(rag_context),
                "context_keys": [k for k, v in context.items() if v],
                "mode": "fallback",
            },
            summary="Client simulation completed with fallback review",
            confidence=0.75,
            needs=None,
            questions=[],
        )


_instance: Optional[ClientSimulatorAgent] = None


def get_client_simulator_agent() -> ClientSimulatorAgent:
    global _instance
    if _instance is None:
        _instance = ClientSimulatorAgent()
    return _instance
