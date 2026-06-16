"""
Compliance Policy Agent
=======================
Migrated compliance controller for advisory and reviewer modes.
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional

from agents.base import BaseAgent
from llm.greennode import get_llm_client
from schemas.state import AgentOutput, Checkpoint, SalesCaseState
from agents.compliance_policy_agent.schema import ComplianceFinding, CompliancePayload


POLICIES = {
    "discount": {
        "max_discount_percent": 20,
        "requires_approval_above": 15,
        "competitor_client_discount": "requires_approval",
    },
    "payment": {
        "min_advance_percent": 30,
        "max_credit_days": 90,
        "requires_deposit_for_custom": True,
    },
    "contract": {
        "min_contract_length_months": 12,
        "auto_renewal": "allowed_with_notice",
    },
}


class ComplianceAgent(BaseAgent):
    def __init__(self, **kwargs):
        _here = os.path.dirname(os.path.abspath(__file__))
        super().__init__(
            name="compliance",
            model_key="MODEL_COMPLIANCE",
            role_description="Policy compliance advisor and reviewer",
            prompt_path=os.path.join(_here, "SKILL.md"),
            knowledge_dir=os.path.join(_here, "reference"),
            skills_dir=os.path.join(_here, "reference"),
            **kwargs,
        )
        self._policies = POLICIES.copy()

    async def run(self, state: SalesCaseState) -> AgentOutput:
        checkpoint = getattr(state, "checkpoint", None)
        if checkpoint:
            return await self.review_checkpoint(state, checkpoint)

        messages = state.messages
        if messages:
            last_message = messages[-1].get("content", "")
            return await self.advisory_query(last_message, state)

        return AgentOutput(
            agent=self.name,
            status="COMPLETE",
            payload={"message": "Compliance agent ready"},
            summary="Ready for policy queries",
            confidence=1.0,
            needs=None,
            questions=[],
        )

    async def advisory_query(self, query: str, state: SalesCaseState) -> AgentOutput:
        kb_results = await self.retrieve_knowledge(query, top_k=5)
        kb_context = self.format_knowledge_context(kb_results)
        client = get_llm_client(self.name)

        prompt = f"""You are the Compliance Agent for a Sales Assistant.
Your role is to answer policy questions based on company policy knowledge.

## User Question
{query}

## Relevant Policy Knowledge
{kb_context}

## Company Policies
{json.dumps(self._policies, indent=2, ensure_ascii=False)}

## Your Task
1. Answer the user's policy question based on the knowledge provided
2. If the answer requires additional context, state so
3. Reference specific policy sections when applicable
4. If the question is about something not covered by policies, say so

Respond in Vietnamese if the user writes in Vietnamese.

Output as JSON:
{{
  "answer": "Your detailed answer...",
  "policy_references": ["policy name if applicable"],
  "requires_review": true/false
}}
"""
        try:
            response = client.create_completion(
                messages=[{"role": "user", "content": prompt}],
                stream=False,
                temperature=0.3,
                max_tokens=1000,
            )
            result_text = response.choices[0].message.content if response.choices else "{}"
            try:
                json_start = result_text.find("{")
                json_end = result_text.rfind("}") + 1
                result = json.loads(result_text[json_start:json_end]) if json_start >= 0 and json_end > json_start else {"answer": result_text}
            except json.JSONDecodeError:
                result = {"answer": result_text}

            return AgentOutput(
                agent=self.name,
                status="COMPLETE",
                payload=result,
                summary=result.get("answer", "Policy query answered")[:100],
                confidence=0.8 if kb_results else 0.5,
                needs=None,
                questions=[],
            )
        except Exception as e:
            return AgentOutput(
                agent=self.name,
                status="FAILED",
                payload={"error": str(e)},
                summary=f"Failed to answer policy query: {str(e)}",
                confidence=0.0,
                needs=None,
                questions=[],
            )

    async def review_checkpoint(self, state: SalesCaseState, checkpoint: Checkpoint) -> AgentOutput:
        action = checkpoint.action
        preview = checkpoint.preview or {}
        findings: list[ComplianceFinding] = []

        if action.type in ["generate_quote", "generate_pptx"]:
            discount = preview.get("discount_percent") or preview.get("discount", 0)
            if discount > self._policies["discount"]["max_discount_percent"]:
                findings.append(
                    ComplianceFinding(
                        severity="block",
                        policy_ref="discount.max_discount_percent",
                        message=f"Discount of {discount}% exceeds maximum {self._policies['discount']['max_discount_percent']}%",
                        suggestion=f"Reduce discount to {self._policies['discount']['max_discount_percent']}% or below",
                    )
                )
            elif discount > self._policies["discount"]["requires_approval_above"]:
                findings.append(
                    ComplianceFinding(
                        severity="warn",
                        policy_ref="discount.requires_approval_above",
                        message=f"Discount of {discount}% requires approval (above {self._policies['discount']['requires_approval_above']}%)",
                        suggestion="Ensure appropriate approval is obtained",
                    )
                )

        if preview.get("payment_terms"):
            credit_days = preview.get("credit_days", 0)
            if credit_days > self._policies["payment"]["max_credit_days"]:
                findings.append(
                    ComplianceFinding(
                        severity="block",
                        policy_ref="payment.max_credit_days",
                        message=f"Credit period of {credit_days} days exceeds maximum {self._policies['payment']['max_credit_days']} days",
                        suggestion=f"Reduce credit to {self._policies['payment']['max_credit_days']} days or less",
                    )
                )

        if preview.get("contract_months") and preview["contract_months"] < self._policies["contract"]["min_contract_length_months"]:
            findings.append(
                ComplianceFinding(
                    severity="warn",
                    policy_ref="contract.min_contract_length",
                    message=f"Contract length {preview['contract_months']} months is below minimum {self._policies['contract']['min_contract_length_months']} months",
                    suggestion=f"Recommend minimum {self._policies['contract']['min_contract_length_months']} month contract",
                )
            )

        llm_findings = await self._llm_review(action, preview)
        findings.extend(llm_findings)
        overall = "block" if any(f.severity == "block" for f in findings) else "warn" if any(f.severity == "warn" for f in findings) else "ok"
        payload = CompliancePayload(findings=findings, overall=overall, summary=f"Found {len(findings)} compliance issues")

        return AgentOutput(
            agent=self.name,
            status="COMPLETE",
            payload=payload.model_dump(),
            summary=payload.summary,
            confidence=0.85,
            needs=None,
            questions=[],
        )

    async def _llm_review(self, action: Checkpoint, preview: dict[str, Any]) -> list[ComplianceFinding]:
        kb_results = await self.retrieve_knowledge(f"compliance {action.type} {action.description}", top_k=3)
        if not kb_results:
            return []
        kb_context = self.format_knowledge_context(kb_results)
        client = get_llm_client(self.name)
        prompt = f"""You are a compliance reviewer. Check if the following action/preview violates any company policies.

## Action
Type: {action.type}
Description: {action.description}

## Preview Data
{json.dumps(preview, indent=2, ensure_ascii=False)}

## Policy Knowledge
{kb_context}

## Company Policies
{json.dumps(self._policies, indent=2, ensure_ascii=False)}

Analyze the action for potential compliance issues. Return any findings as JSON:
{{
  "findings": [
    {{
      "severity": "warn|block|info",
      "policy_ref": "policy name",
      "message": "description",
      "suggestion": "how to fix"
    }}
  ]
}}

If no issues found, return {{"findings": []}}.
"""
        try:
            response = client.create_completion(
                messages=[{"role": "user", "content": prompt}],
                stream=False,
                temperature=0.2,
                max_tokens=1000,
            )
            result_text = response.choices[0].message.content if response.choices else "{}"
            json_start = result_text.find("{")
            json_end = result_text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                result = json.loads(result_text[json_start:json_end])
                return [ComplianceFinding(**f) for f in result.get("findings", [])]
        except Exception:
            pass
        return []


_compliance_agent: Optional[ComplianceAgent] = None


def get_compliance_agent() -> ComplianceAgent:
    global _compliance_agent
    if _compliance_agent is None:
        _compliance_agent = ComplianceAgent()
    return _compliance_agent
