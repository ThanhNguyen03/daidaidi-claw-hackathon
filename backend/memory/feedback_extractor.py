"""
Feedback Extractor
==================
Extracts typed feedback rules from user utterances.

D.2: Classify user utterance as rule | preference | fact,
build FeedbackRule with type, scope, rule, source_quote, active.
"""

import re
import uuid
from datetime import datetime
from typing import Optional
from enum import Enum

from schemas.state import FeedbackRule


class FeedbackType(Enum):
    """Types of feedback that can be extracted."""
    NEGATIVE_CONSTRAINT = "NEGATIVE_CONSTRAINT"  # "don't do X"
    POSITIVE_CONSTRAINT = "POSITIVE_CONSTRAINT"  # "always do X"
    PREFERENCE = "PREFERENCE"  # "I prefer X"
    FACT = "FACT"  # "X is true about my business"


class FeedbackExtractor:
    """
    Extracts structured feedback rules from natural language.

    Patterns detected:
    - "don't suggest/mention/offer X" → NEGATIVE_CONSTRAINT
    - "always do X" / "make sure to X" → POSITIVE_CONSTRAINT
    - "I prefer X" / "I like X" → PREFERENCE
    - "my industry is X" / "we sell X" → FACT
    """

    # Patterns for feedback extraction
    NEGATIVE_PATTERNS = [
        r"don't\s+(suggest|mention|offer|show|bring\s+up|recommend)\s+(.+?)(?:\.|$)",
        r"never\s+(.+?)(?:\.|$)",
        r"stop\s+(.+?ing)(?:\.|$)",
        r"no\s+(.+?)(?:\.|$)",
        r"avoid\s+(.+?ing)(?:\.|$)",
        r"(?:please\s+)?don't\s+(.+?)(?:\.|$)",
        r"(?:please\s+)?never\s+(.+?)(?:\.|$)",
    ]

    POSITIVE_PATTERNS = [
        r"always\s+(.+?)(?:\.|$)",
        r"(?:you\s+)?should\s+(.+?)(?:\.|$)",
        r"make\s+sure\s+to\s+(.+?)(?:\.|$)",
        r"(?:please\s+)?do\s+(.+?)(?:\.|$)",
    ]

    PREFERENCE_PATTERNS = [
        r"i\s+(prefer|like|love|don't\s+like|hate)\s+(.+?)(?:\.|$)",
        r"my\s+(?:preferred|favorite)\s+(?:is|was)\s+(.+?)(?:\.|$)",
        r"i\s+(?:usually|always)\s+(choose|use|go\s+with)\s+(.+?)(?:\.|$)",
    ]

    # Scope mapping: keywords to agent scopes
    SCOPE_KEYWORDS = {
        "discount": ["product_solution", "sales_orchestrator"],
        "price": ["product_solution", "sales_orchestrator"],
        "pricing": ["product_solution", "sales_orchestrator"],
        "quotation": ["product_solution", "sales_orchestrator"],
        "quote": ["product_solution", "sales_orchestrator"],
        "tech": ["sales_orchestrator"],
        "technical": ["sales_orchestrator"],
        "solution": ["product_solution", "sales_orchestrator"],
        "design": ["design"],
        "wireframe": ["design"],
        "market": ["market_strategy"],
        "strategy": ["market_strategy"],
        "adtima": ["product_solution", "sales_orchestrator"],
        "requirement": ["requirement_elicitation"],
        "requirements": ["requirement_elicitation"],
        "compliance": ["compliance"],
        "policy": ["compliance"],
        "brief": ["sales_orchestrator"],
        "question": ["sales_orchestrator"],
    }

    def __init__(self):
        """Initialize the feedback extractor."""
        self._compile_patterns()

    def _compile_patterns(self):
        """Compile regex patterns for efficiency."""
        self._negative_patterns = [re.compile(p, re.IGNORECASE) for p in self.NEGATIVE_PATTERNS]
        self._positive_patterns = [re.compile(p, re.IGNORECASE) for p in self.POSITIVE_PATTERNS]
        self._preference_patterns = [re.compile(p, re.IGNORECASE) for p in self.PREFERENCE_PATTERNS]

    def extract(self, message: str, context: Optional[dict] = None) -> Optional[FeedbackRule]:
        """
        Extract a feedback rule from user message.

        Args:
            message: The user's message to analyze
            context: Optional context (session info, salesperson_id, etc.)

        Returns:
            FeedbackRule if extraction successful, None otherwise
        """
        message = message.strip()
        if not message:
            return None

        # Try each pattern type
        # Negative constraints ("don't do X")
        for pattern in self._negative_patterns:
            match = pattern.search(message)
            if match:
                action = match.group(1).strip() if match.lastindex >= 1 else ""
                target = match.group(2).strip() if match.lastindex >= 2 else ""

                rule_text = f"Never {action} {target}".strip()
                scope = self._infer_scope(target)

                return FeedbackRule(
                    rule_id=f"rule_{uuid.uuid4().hex[:12]}",
                    salesperson_id=context.get("salesperson_id", "unknown") if context else "unknown",
                    type="NEGATIVE_CONSTRAINT",
                    scope=scope,
                    rule=rule_text,
                    source_quote=message,
                    active=True,
                    created_at=datetime.now(),
                )

        # Positive constraints ("always do X")
        for pattern in self._positive_patterns:
            match = pattern.search(message)
            if match:
                action = match.group(1).strip()
                rule_text = f"Always {action}".strip()
                scope = self._infer_scope(action)

                return FeedbackRule(
                    rule_id=f"rule_{uuid.uuid4().hex[:12]}",
                    salesperson_id=context.get("salesperson_id", "unknown") if context else "unknown",
                    type="POSITIVE_CONSTRAINT",
                    scope=scope,
                    rule=rule_text,
                    source_quote=message,
                    active=True,
                    created_at=datetime.now(),
                )

        # Preferences ("I prefer X")
        for pattern in self._preference_patterns:
            match = pattern.search(message)
            if match:
                preference_type = match.group(1).strip().lower()
                target = match.group(2).strip() if match.lastindex >= 2 else ""

                if "don't like" in preference_type or "hate" in preference_type:
                    rule_text = f"Never suggest {target}".strip()
                    rule_type = "NEGATIVE_CONSTRAINT"
                else:
                    rule_text = f"Prefer {target}".strip()
                    rule_type = "PREFERENCE"

                scope = self._infer_scope(target)

                return FeedbackRule(
                    rule_id=f"rule_{uuid.uuid4().hex[:12]}",
                    salesperson_id=context.get("salesperson_id", "unknown") if context else "unknown",
                    type=rule_type,
                    scope=scope,
                    rule=rule_text,
                    source_quote=message,
                    active=True,
                    created_at=datetime.now(),
                )

        return None

    def _infer_scope(self, text: str) -> list[str]:
        """Infer which agents the rule applies to based on keywords."""
        text_lower = text.lower()
        scopes = set()

        for keyword, scope_list in self.SCOPE_KEYWORDS.items():
            if keyword in text_lower:
                scopes.update(scope_list)

        # Default to orchestrator if no specific scope found
        if not scopes:
            scopes.add("sales_orchestrator")

        return sorted(list(scopes))

    def is_feedback_message(self, message: str) -> bool:
        """
        Quick check if a message appears to contain feedback.
        Used to decide whether to run full extraction.
        """
        message_lower = message.lower()

        feedback_indicators = [
            "don't", "never", "stop", "avoid", "always", "should",
            "prefer", "like", "love", "hate", "my preference",
            "i wish", "please do", "please don't", "don't suggest",
        ]

        return any(indicator in message_lower for indicator in feedback_indicators)


# =============================================================================
# Global Instance
# =============================================================================

_extractor: Optional[FeedbackExtractor] = None


def get_feedback_extractor() -> FeedbackExtractor:
    """Get the global feedback extractor instance."""
    global _extractor
    if _extractor is None:
        _extractor = FeedbackExtractor()
    return _extractor
