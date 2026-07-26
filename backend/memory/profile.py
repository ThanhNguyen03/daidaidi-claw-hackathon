"""
Profile Manager
================
Manages salesperson profiles with learning capabilities.

C.5 §4 / D.3: Style learning, question_frequency tracking,
frustration detection, history-based suggested answers.
"""

import uuid
from datetime import datetime
from typing import Optional

from schemas.state import SalespersonProfile, ProfileHistoryItem


class ProfileManager:
    """
    Manages salesperson profiles and learns from interactions.

    Learning mechanisms:
    - Style: terse | balanced | detailed (inferred from answer length)
    - question_frequency: useful_answers / total_questions_asked
    - Frustration detection: "why do you keep asking" lowers frequency
    - History: past choices used for suggested answers
    """

    # Style thresholds (characters in answer)
    STYLE_TERSE_MAX = 50
    STYLE_BALANCED_MAX = 200
    # Above 200 is "detailed"

    # Frustration triggers
    FRUSTRATION_PHRASES = [
        "why do you keep asking",
        "stop asking",
        "just answer",
        "don't ask me",
        "this is annoying",
        "why are you asking",
        "that's enough",
    ]

    def __init__(self):
        """Initialize the profile manager."""
        pass

    def create_profile(
        self,
        salesperson_id: str,
        display_name: Optional[str] = None,
    ) -> SalespersonProfile:
        """
        Create a new profile for a salesperson.

        Args:
            salesperson_id: Unique identifier
            display_name: Human-readable name

        Returns:
            New SalespersonProfile
        """
        return SalespersonProfile(
            salesperson_id=salesperson_id,
            display_name=display_name or salesperson_id,
            style="balanced",  # Default style
            question_frequency=1.0,  # Start optimistic
            preferences={},
            constraints=[],
            history=[],
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    def update_from_answer(
        self,
        profile: SalespersonProfile,
        question_text: str,
        answer: str,
        was_helpful: Optional[bool] = None,
    ) -> SalespersonProfile:
        """
        Update profile based on a question answer.

        Args:
            profile: Current profile
            question_text: The question that was answered
            answer: User's answer
            was_helpful: Optional explicit feedback

        Returns:
            Updated profile
        """
        # Update style based on answer length
        answer_length = len(answer.strip())

        if answer_length <= self.STYLE_TERSE_MAX:
            new_style = "terse"
        elif answer_length <= self.STYLE_BALANCED_MAX:
            new_style = "balanced"
        else:
            new_style = "detailed"

        # Blend styles (weighted average)
        style_weights = {"terse": 0.3, "balanced": 0.5, "detailed": 0.2}
        profile.style = self._blend_style(profile.style, new_style, style_weights)

        # Update question frequency
        # If user answered, that's a positive signal
        if answer_length > 0:
            total = profile.question_frequency * 10 + 1  # Approximate total asked
            if was_helpful is True:
                # Increase frequency
                profile.question_frequency = min(1.0, (total + 1) / (total + 2))
            elif was_helpful is False:
                # Decrease frequency
                profile.question_frequency = max(0.0, (total - 1) / (total + 2))
            # If was_helpful is None, keep roughly same

        # Add to history
        history_item = ProfileHistoryItem(
            case_id=f"q_{uuid.uuid4().hex[:8]}",
            summary=f"Q: {question_text[:50]}...",  # Use summary field
            question=question_text,
            answer=answer,
            helpful=was_helpful,
            timestamp=datetime.now().isoformat(),
        )
        profile.history.append(history_item)

        # Keep history bounded (last 50 items)
        if len(profile.history) > 50:
            profile.history = profile.history[-50:]

        profile.updated_at = datetime.now()
        return profile

    def detect_frustration(
        self,
        profile: SalespersonProfile,
        message: str,
    ) -> bool:
        """
        Detect user frustration in message.

        Args:
            profile: Current profile
            message: User's message

        Returns:
            True if frustration detected
        """
        message_lower = message.lower()

        for phrase in self.FRUSTRATION_PHRASES:
            if phrase in message_lower:
                # Lower question frequency on frustration
                profile.question_frequency = max(
                    0.1, profile.question_frequency - 0.2
                )
                profile.updated_at = datetime.now()
                return True

        return False

    def get_suggested_answer(
        self,
        profile: SalespersonProfile,
        question_key: str,
    ) -> Optional[str]:
        """
        Get a suggested answer based on history.

        Args:
            profile: Current profile
            question_key: Identifier for the question (e.g., "industry")

        Returns:
            Suggested answer if available, None otherwise
        """
        # Look for previous answers to similar questions
        for item in reversed(profile.history):
            if question_key.lower() in item.question.lower():
                # Return previous answer as suggestion
                return item.answer

        return None

    def _blend_style(
        self,
        current_style: str,
        new_style: str,
        weights: dict[str, float],
    ) -> str:
        """Blend two styles using weights."""
        # Simple approach: if new style appears consistently, switch
        # This is a simplified version - could be more sophisticated
        if new_style != current_style:
            # 30% chance to adopt new style on each occurrence
            import random

            if random.random() < weights.get(new_style, 0.3):
                return new_style

        return current_style

    def add_constraint(
        self,
        profile: SalespersonProfile,
        rule_id: str,
    ) -> SalespersonProfile:
        """
        Add a constraint rule to the profile.

        Args:
            profile: Current profile
            rule_id: ID of the feedback rule

        Returns:
            Updated profile
        """
        if rule_id not in profile.constraints:
            profile.constraints.append(rule_id)
            profile.updated_at = datetime.now()

        return profile

    def remove_constraint(
        self,
        profile: SalespersonProfile,
        rule_id: str,
    ) -> SalespersonProfile:
        """
        Remove a constraint rule from the profile.

        Args:
            profile: Current profile
            rule_id: ID of the feedback rule

        Returns:
            Updated profile
        """
        if rule_id in profile.constraints:
            profile.constraints.remove(rule_id)
            profile.updated_at = datetime.now()

        return profile

    def get_question_phrasing(
        self,
        profile: SalespersonProfile,
        base_question: str,
    ) -> str:
        """
        Adapt question phrasing based on user's style.

        Args:
            profile: User's profile
            base_question: The default question text

        Returns:
            Adapted question text
        """
        style = profile.style

        if style == "terse":
            # Make questions more direct
            if not base_question.endswith("?"):
                base_question += "?"
            return f"Quick: {base_question}"

        elif style == "detailed":
            # Add context to questions
            if not base_question.endswith("?"):
                base_question += "?"
            return f"Details help me help you: {base_question}"

        # Balanced - use as-is
        return base_question

    def get_answer_verbosity(
        self,
        profile: SalespersonProfile,
    ) -> str:
        """
        Determine how verbose agent answers should be.

        Returns:
            "terse", "balanced", or "detailed"
        """
        return profile.style


# =============================================================================
# Global Instance
# =============================================================================

_manager: Optional[ProfileManager] = None


def get_profile_manager() -> ProfileManager:
    """Get the global profile manager instance."""
    global _manager
    if _manager is None:
        _manager = ProfileManager()
    return _manager