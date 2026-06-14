"""
Account Agent - Real Implementation
====================================
Handles pricing, quotations, and account-related matters.
Uses hybrid pricing: deterministic rate-card lookup + LLM estimate for custom features.

Integrates with:
- KB/RAG for product knowledge
- Rate card for deterministic pricing
- LLM for custom feature estimation
"""

import os
import json
import re
from typing import Any, Optional
from datetime import datetime, timedelta

from schemas.state import SalesCaseState, AgentOutput
from agents.base import BaseAgent
from llm.greennode import get_llm_client


# =============================================================================
# Rate Card
# =============================================================================

# Demo rate card - in production, load from knowledge/rate_card.md/.csv
RATE_CARD = {
    "platform_license": {
        "name": "Platform License",
        "unit": "year",
        "tiers": {
            "starter": 50000000,
            "professional": 100000000,
            "enterprise": 200000000,
        },
    },
    "implementation": {
        "name": "Implementation",
        "unit": "one-time",
        "tiers": {
            "basic": 30000000,
            "standard": 50000000,
            "premium": 80000000,
        },
    },
    "support": {
        "name": "Support Package",
        "unit": "year",
        "tiers": {
            "standard": 12000000,
            "premium": 24000000,
            "24x7": 48000000,
        },
    },
    "training": {
        "name": "Training",
        "unit": "day",
        "price": 8000000,
    },
    "custom_development": {
        "name": "Custom Development",
        "unit": "hour",
        "price": 2000000,
    },
}


def lookup_rate_card(item_name: str, tier: Optional[str] = None) -> Optional[dict]:
    """
    Look up a deterministic price from the rate card.

    Args:
        item_name: Name of the item (normalized)
        tier: Optional tier (e.g., "starter", "professional")

    Returns:
        Dict with price info or None if not found
    """
    # Normalize item name
    item_key = item_name.lower().replace(" ", "_").replace("-", "_")

    # Exact match first
    if item_key in RATE_CARD:
        item = RATE_CARD[item_key]
        if tier and "tiers" in item:
            if tier.lower() in item["tiers"]:
                return {
                    "name": item["name"],
                    "price": item["tiers"][tier.lower()],
                    "unit": item["unit"],
                    "tier": tier,
                    "is_estimate": False,
                }
        # Return first tier if no specific tier requested
        if "tiers" in item:
            first_tier = list(item["tiers"].keys())[0]
            return {
                "name": item["name"],
                "price": item["tiers"][first_tier],
                "unit": item["unit"],
                "tier": first_tier,
                "is_estimate": False,
            }
        # Flat price item
        return {
            "name": item["name"],
            "price": item.get("price", 0),
            "unit": item["unit"],
            "is_estimate": False,
        }

    # Fuzzy match
    for key, item in RATE_CARD.items():
        if item_key in key or key in item_key:
            return lookup_rate_card(key, tier)

    return None


async def estimate_custom_feature(
    feature_description: str,
    context: dict[str, Any],
) -> dict:
    """
    Use LLM to estimate pricing for custom features not on the rate card.

    Args:
        feature_description: Description of the custom feature
        context: Additional context (industry, requirements, etc.)

    Returns:
        Dict with estimated price and reasoning
    """
    client = get_llm_client("account")

    prompt = f"""You are a pricing expert for a software solutions company.
Based on the following custom feature request, provide a cost estimate.

Feature: {feature_description}

Context:
- Industry: {context.get('industry', 'Not specified')}
- Company size: {context.get('company_size', 'Not specified')}
- Timeline: {context.get('timeline', 'Not specified')}

Provide your estimate in VND (Vietnamese Dong) with:
1. Estimated effort (hours or days)
2. Hourly/daily rate applied
3. Total estimated cost
4. Confidence level (high/medium/low)
5. Key assumptions

Be realistic and conservative. If uncertain, state so.
"""

    try:
        response = client.create_completion(
            messages=[{"role": "user", "content": prompt}],
            stream=False,
            temperature=0.3,
            max_tokens=1000,
        )

        estimate_text = response.choices[0].message.content if response.choices else ""

        # Try to extract a numeric estimate
        vnd_pattern = r"(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(?:VND|đ|dong)"
        matches = re.findall(vnd_pattern, estimate_text.replace(".", "").replace(",", ""))

        estimated_price = 0
        if matches:
            # Take the largest number as the total
            estimated_price = max(int(m.replace(",", "")) for m in matches)

        return {
            "description": feature_description,
            "estimated_price": estimated_price,
            "estimate_text": estimate_text,
            "is_estimate": True,  # Always flagged as estimate
            "confidence": "medium",
        }

    except Exception as e:
        return {
            "description": feature_description,
            "estimated_price": 0,
            "estimate_text": f"Could not generate estimate: {str(e)}",
            "is_estimate": True,
            "confidence": "low",
        }


# =============================================================================
# Account Agent Implementation
# =============================================================================

class AccountAgent(BaseAgent):
    """
    Real Account agent with hybrid pricing and KB integration.
    """

    def __init__(self, **kwargs):
        super().__init__(
            name="account",
            model_key="MODEL_ACCOUNT",
            role_description="Pricing and quotation specialist",
            **kwargs,
        )

    async def run(self, state: SalesCaseState) -> AgentOutput:
        """
        Execute the account agent's task.
        Generates pricing based on rate card and KB knowledge.
        """
        # Get the brief for context
        brief = state.brief
        if not brief:
            return AgentOutput(
                agent=self.name,
                status="NEEDS_INPUT",
                payload={},
                summary="No brief provided for pricing",
                confidence=0.0,
                questions=[],
            )

        # Retrieve relevant knowledge from KB
        kb_results = await self.retrieve_knowledge(
            f"pricing {brief.industry or ''} {brief.goal or ''}", top_k=3
        )

        # Format knowledge context
        kb_context = self.format_knowledge_context(kb_results)

        # Build the pricing request
        pricing_items = []
        custom_features = []

        # Check brief for specific requirements
        requirements = brief.specific_requirements or []

        for req in requirements:
            # Try rate card first
            rate_lookup = lookup_rate_card(req)
            if rate_lookup:
                pricing_items.append(rate_lookup)
            else:
                # Custom feature - needs LLM estimate
                custom_features.append(req)

        # Use LLM to generate the quote
        client = get_llm_client(self.name)

        prompt = f"""You are the Account Agent for a Sales Assistant.

Your role is to prepare pricing proposals and quotations.

## Current Brief
- Industry: {brief.industry or 'Not specified'}
- Budget: {brief.budget_vnd or 'Not specified'} VND
- Goal: {brief.goal or 'Not specified'}
- Timeline: {brief.timeline or 'Not specified'}

## Requirements to quote:
{chr(10).join(f"- {req}" for req in requirements) if requirements else "- General consultation"}

{kb_context}

## Rate Card (deterministic prices):
{json.dumps(RATE_CARD, indent=2, ensure_ascii=False)}

## Your Task
1. Identify which items can be priced from the rate card (deterministic)
2. For custom features not on the rate card, note them as estimates
3. Prepare a quotation with:
   - Itemized pricing in VND
   - Subtotals per category
   - Total amount
   - Validity period (30 days from today)
   - Payment terms
4. If budget is specified, compare and note if quote exceeds budget
5. Flag any custom/estimate items clearly as "ESTIMATE"

Respond in Vietnamese (Vietnamese if the user writes in Vietnamese).

Output as JSON with this structure:
{{
  "quote_id": "Q-YYYY-NNN",
  "items": [{{"name": "...", "price": NNN, "unit": "...", "is_estimate": false}}],
  "subtotal": NNN,
  "total_vnd": NNN,
  "valid_until": "YYYY-MM-DD",
  "payment_terms": "...",
  "exceeds_budget": true/false,
  "notes": []
}}
"""

        try:
            response = client.create_completion(
                messages=[{"role": "user", "content": prompt}],
                stream=False,
                temperature=0.3,
                max_tokens=2000,
            )

            result_text = response.choices[0].message.content if response.choices else "{}"

            # Try to parse JSON from response
            try:
                # Find JSON in response
                json_start = result_text.find("{")
                json_end = result_text.rfind("}") + 1

                if json_start >= 0 and json_end > json_start:
                    result = json.loads(result_text[json_start:json_end])
                else:
                    result = {"error": "Could not parse quote", "raw": result_text}
            except json.JSONDecodeError:
                result = {"error": "Invalid JSON", "raw": result_text}

            # Ensure quote_id
            if "quote_id" not in result:
                result["quote_id"] = f"Q-{datetime.now().year}-{datetime.now().strftime('%m%d')}-{datetime.now().strftime('%H%M')}"

            # Validate quote has required fields
            if "items" not in result:
                result["items"] = pricing_items

            if "total_vnd" not in result:
                result["total_vnd"] = sum(
                    item.get("price", 0) for item in result.get("items", [])
                )

            # Calculate confidence based on KB and rate card coverage
            rate_card_coverage = len(pricing_items) / max(len(requirements), 1)
            confidence = min(0.9, 0.5 + (rate_card_coverage * 0.4))

            if kb_results:
                confidence = min(0.95, confidence + 0.1)

            return AgentOutput(
                agent=self.name,
                status="COMPLETE",
                payload=result,
                summary=f"Quote prepared: {result.get('total_vnd', 0):,.0f} VND",
                confidence=confidence,
                needs=None,
                questions=[],
            )

        except Exception as e:
            return AgentOutput(
                agent=self.name,
                status="FAILED",
                payload={"error": str(e)},
                summary=f"Failed to generate quote: {str(e)}",
                confidence=0.0,
                needs=None,
                questions=[],
            )


# =============================================================================
# Global Instance
# =============================================================================

_account_agent: Optional[AccountAgent] = None


def get_account_agent() -> AccountAgent:
    """Get the account agent instance."""
    global _account_agent
    if _account_agent is None:
        _account_agent = AccountAgent()
    return _account_agent