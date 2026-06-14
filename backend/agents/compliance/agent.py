"""
Compliance Agent
================
Implements both advisory and reviewer modes for policy compliance.

Advisory Mode:
- Answers policy questions grounded in policy KB
- Triggered when user asks about policies

Reviewer Mode (pre_checkpoint_review hook):
- Reviews pending plans/quotes for compliance issues
- Attaches findings to checkpoints
- A "block" finding disables auto-approve

Policies are loaded from knowledge/ directory.
"""

import json
from typing import Any, Optional

from schemas.state import SalesCaseState, AgentOutput, Checkpoint
from agents.base import BaseAgent
from llm.greennode import get_llm_client
from agents.compliance.schema import CompliancePayload, ComplianceFinding


# Sample compliance policies (in production, load from knowledge/*.md)
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
    """
    Compliance agent with dual modes:
    - Advisory: Answer policy questions
    - Reviewer: Pre-checkpoint compliance review
    """

    def __init__(self, **kwargs):
        super().__init__(
            name="compliance",
            model_key="MODEL_COMPLIANCE",
            role_description="Policy compliance advisor and reviewer",
            **kwargs,
        )
        self._policies = POLICIES.copy()

    async def run(self, state: SalesCaseState) -> AgentOutput:
        """
        Execute the compliance agent.
        Determines mode based on state and executes accordingly.
        """
        # Check if this is a review request (has checkpoint to review)
        checkpoint = getattr(state, "checkpoint", None)
        if checkpoint:
            return await self.review_checkpoint(state, checkpoint)

        # Otherwise, run in advisory mode based on last message
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
        """
        Advisory mode: Answer policy questions from KB.
        """
        # Retrieve relevant policy knowledge
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

Respond in Vietnamese (Vietnamese if the user writes in Vietnamese).

Output as JSON:
{{
  "answer": "Your detailed answer...",
  "policy_references": ["policy name if applicable"],
  "requires_review": true/false (if this involves a specific deal/quote that needs compliance review)
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

            # Parse JSON
            try:
                json_start = result_text.find("{")
                json_end = result_text.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    result = json.loads(result_text[json_start:json_end])
                else:
                    result = {"answer": result_text}
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

    async def review_checkpoint(
        self, state: SalesCaseState, checkpoint: Checkpoint
    ) -> AgentOutput:
        """
        Reviewer mode: Check a pending checkpoint for compliance.
        """
        # Get the pending action details
        action = checkpoint.action
        preview = checkpoint.preview or {}

        # Check against policies
        findings = []

        # Check 1: Discount policy
        if action.type in ["generate_quote", "generate_pptx"]:
            # Look for discount in preview
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

        # Check 2: Payment terms
        if preview.get("payment_terms"):
            # Simple check - in production would be more sophisticated
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

        # Check 3: Contract length
        if preview.get("contract_months"):
            if preview["contract_months"] < self._policies["contract"]["min_contract_length_months"]:
                findings.append(
                    ComplianceFinding(
                        severity="warn",
                        policy_ref="contract.min_contract_length",
                        message=f"Contract length {preview['contract_months']} months is below minimum {self._policies['contract']['min_contract_length_months']} months",
                        suggestion=f"Recommend minimum {self._policies['contract']['min_contract_length_months']} month contract",
                    )
                )

        # Also run LLM-based review for more nuanced checks
        llm_findings = await self._llm_review(action, preview)
        findings.extend(llm_findings)

        # Determine overall status
        if any(f.severity == "block" for f in findings):
            overall = "block"
        elif any(f.severity == "warn" for f in findings):
            overall = "warn"
        else:
            overall = "ok"

        payload = CompliancePayload(
            findings=findings,
            overall=overall,
            summary=f"Found {len(findings)} compliance issues",
        )

        return AgentOutput(
            agent=self.name,
            status="COMPLETE",
            payload=payload.model_dump(),
            summary=payload.summary,
            confidence=0.85,
            needs=None,
            questions=[],
        )

    async def _llm_review(
        self, action: CheckpointAction, preview: dict[str, Any]
    ) -> list[ComplianceFinding]:
        """Use LLM for more nuanced compliance review."""
        kb_results = await self.retrieve_knowledge(
            f"compliance {action.type} {action.description}", top_k=3
        )

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

            # Parse
            json_start = result_text.find("{")
            json_end = result_text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                result = json.loads(result_text[json_start:json_end])
                findings_data = result.get("findings", [])
                return [ComplianceFinding(**f) for f in findings_data]
        except Exception:
            pass

        return []


# =============================================================================
# Global Instance
# =============================================================================

_compliance_agent: Optional[ComplianceAgent] = None


def get_compliance_agent() -> ComplianceAgent:
    """Get the compliance agent instance."""
    global _compliance_agent
    if _compliance_agent is None:
        _compliance_agent = ComplianceAgent()
    return _compliance_agent