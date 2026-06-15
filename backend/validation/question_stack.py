"""
Question Stack
==============
Implements the QuestionStack mechanism for C.5 §2.
Handles batching, prioritization, answer mapping, and re-validation.
"""

import uuid
from typing import Optional
from datetime import datetime

from schemas.state import Question, Brief

# =============================================================================
# QuestionStack
# =============================================================================


class QuestionStack:
    """
    Manages a stack of questions to ask the user.
    C.5 §2: Batches questions, prioritizes, maps answers.
    """

    def __init__(self):
        self.items: list[Question] = []

    def push(self, questions: list[Question]) -> None:
        """
        Add questions to the stack.
        Deduplicates against already-asked questions.
        """
        existing_ids = {q.id for q in self.items}

        for question in questions:
            # Skip if already in stack
            if question.id in existing_ids:
                continue

            # Track when first asked
            question.last_asked_at = datetime.now()
            self.items.append(question)

    def next_batch(self) -> list[Question]:
        """
        Get the next batch of questions to ask.
        C.5 §2: Returns unanswered, sorted by priority, mandatory first.
        """
        # Filter unanswered
        unanswered = [q for q in self.items if not q.answered]

        # Sort: mandatory first (lower priority number = higher priority), then by asked_count
        unanswered.sort(key=lambda q: (not q.is_mandatory, q.priority, q.asked_count))

        return unanswered

    def get_unanswered_count(self) -> int:
        """Get count of unanswered questions."""
        return sum(1 for q in self.items if not q.answered)

    def has_mandatory_unanswered(self) -> bool:
        """Check if there are any mandatory unanswered questions."""
        return any(q for q in self.items if q.is_mandatory and not q.answered)

    def clear_answered(self) -> None:
        """Remove answered questions from the stack."""
        self.items = [q for q in self.items if not q.answered]

    def get_by_id(self, question_id: str) -> Optional[Question]:
        """Get a question by ID."""
        for q in self.items:
            if q.id == question_id:
                return q
        return None

    def to_list(self) -> list[dict]:
        """Convert to list of dicts for serialization."""
        return [q.model_dump() for q in self.items]


# =============================================================================
# QuestionManager
# =============================================================================


class QuestionManager:
    """
    Manages the full question-answer lifecycle.
    C.5 §2: Creates questions, maps answers, triggers re-validation.
    """

    # Required fields by mode (for generating questions)
    REQUIRED_FIELDS = {
        "planning": ["industry", "goal"],
        "execute": ["industry", "budget_vnd", "goal"],
        "chat": [],
        "brainstorm": [],
    }

    # Optional fields by mode
    OPTIONAL_FIELDS = {
        "planning": ["timeline", "target_audience"],
        "execute": ["timeline", "target_audience", "constraints"],
        "chat": [],
        "brainstorm": [],
    }

    # Default assumptions for optional fields
    DEFAULT_ASSUMPTIONS = {
        "timeline": "within 3 months",
        "target_audience": "general audience",
        "constraints": "none specified",
        "budget_vnd": "industry median (approximately 150M VND)",
    }

    def __init__(self):
        self.stack = QuestionStack()

    def generate_questions_from_validation(
        self,
        brief: Brief,
        mode: str,
        validation_missing: list[str],
        validation_ambiguities: list,
    ) -> list[Question]:
        """
        Generate questions from validation report.
        C.5 §2: Creates Question objects for missing/ambiguous fields.
        """
        questions = []

        # Generate questions for missing required fields
        for field in validation_missing:
            if field in self.REQUIRED_FIELDS.get(mode, []):
                question = self._create_question_for_field(
                    field=field, is_mandatory=True, brief=brief, mode=mode
                )
                if question:
                    questions.append(question)

        # Generate questions for missing optional fields
        for field in self.OPTIONAL_FIELDS.get(mode, []):
            value = getattr(brief, field, None)
            if not value:
                question = self._create_question_for_field(
                    field=field, is_mandatory=False, brief=brief, mode=mode
                )
                if question:
                    questions.append(question)

        # Add questions for ambiguities
        for amb in validation_ambiguities:
            if hasattr(amb, "field"):
                question = self._create_ambiguity_question(amb)
                if question:
                    questions.append(question)

        # Sort: mandatory first
        questions.sort(key=lambda q: (not q.is_mandatory, q.priority))

        # Deduplicate by target_field - keep first occurrence only
        seen_fields = set()
        unique_questions = []
        for q in questions:
            if q.target_field not in seen_fields:
                seen_fields.add(q.target_field)
                unique_questions.append(q)

        return unique_questions

    def _create_question_for_field(
        self, field: str, is_mandatory: bool, brief: Brief, mode: str
    ) -> Optional[Question]:
        """Create a question for a specific field."""

        # Question templates
        field_questions = {
            "industry": "What industry sector are you targeting? (e.g., F&B, Retail, Tech)",
            "budget_vnd": "What is your budget for this project? (in VND)",
            "goal": "What is the main goal or objective?",
            "timeline": "What is your timeline or deadline?",
            "target_audience": "Who is your target audience?",
            "constraints": "Are there any specific constraints we should know about?",
        }

        if field not in field_questions:
            return None

        # Get assumption for optional fields
        assumption = None
        if not is_mandatory:
            assumption = self.DEFAULT_ASSUMPTIONS.get(field)

        return Question(
            id=f"q_{field}_{uuid.uuid4().hex[:6]}",
            text=field_questions[field],
            priority=1 if is_mandatory else 2,
            is_mandatory=is_mandatory,
            assumption=assumption,
            target_field=field,
            asked_count=0,
            last_asked_at=None,
            answered=False,
            answer=None,
            was_helpful=None,
        )

    def _create_ambiguity_question(self, ambiguity) -> Optional[Question]:
        """Create a question to resolve an ambiguity."""

        return Question(
            id=f"q_amb_{uuid.uuid4().hex[:6]}",
            text=f"I noticed '{ambiguity.field}' could mean: {', '.join(ambiguity.interpretations[:2])}. Which one applies?",
            priority=1,  # Ambiguity is high priority
            is_mandatory=True,
            assumption=None,  # No assumption for ambiguity - need user input
            target_field=ambiguity.field,
            asked_count=0,
            last_asked_at=None,
            answered=False,
            answer=None,
            was_helpful=None,
        )

    def map_answers(self, answers: dict[str, str], brief: Brief) -> Brief:
        """
        C.5 §2: Map user answers to brief fields.
        Updates both the Question.answer and the Brief fields.
        """
        for question_id, answer_text in answers.items():
            question = self.stack.get_by_id(question_id)
            if question:
                # Mark question as answered
                question.answer = answer_text
                question.answered = True
                question.asked_count += 1

                # Map to brief field
                target_field = question.target_field
                if target_field and answer_text:
                    # Convert answer to appropriate type
                    brief = self._convert_and_set_field(
                        brief, target_field, answer_text
                    )

        return brief

    def map_free_text_answer(self, free_text: str, brief: Brief) -> Brief:
        """
        C.5 §5: Map free-text answer to appropriate fields.
        Uses LLM-assisted mapping when user answers in natural language.
        """
        # Simple keyword-based mapping for now
        # In production, would use LLM to parse

        free_text_lower = free_text.lower()

        # Industry detection
        industries = [
            "f&b",
            "food",
            " beverage",
            "retail",
            "tech",
            "technology",
            "healthcare",
            "education",
            "finance",
            "manufacturing",
        ]
        for ind in industries:
            if ind in free_text_lower:
                brief.industry = ind.title() if ind != "f&b" else "F&B"
                break

        # Budget detection
        import re

        budget_match = re.search(
            r"(\d+)\s*(triệu|million|billion|tỷ)?", free_text_lower
        )
        if budget_match:
            amount = int(budget_match.group(1))
            unit = budget_match.group(2) or "triệu"

            if unit in ["triệu", "million"]:
                brief.budget_vnd = amount * 1_000_000
            elif unit in ["billion", "tỷ"]:
                brief.budget_vnd = amount * 1_000_000_000

        # Goal detection
        if "launch" in free_text_lower or "ra mắt" in free_text_lower:
            brief.goal = "product launch"
        elif "tăng trưởng" in free_text_lower or "growth" in free_text_lower:
            brief.goal = "growth"

        # Mark any matching questions as answered
        for question in self.stack.items:
            if question.answered:
                continue

            target_field = question.target_field
            if target_field == "industry" and brief.industry:
                question.answer = brief.industry
                question.answered = True
            elif target_field == "budget_vnd" and brief.budget_vnd:
                question.answer = str(brief.budget_vnd)
                question.answered = True
            elif target_field == "goal" and brief.goal:
                question.answer = brief.goal
                question.answered = True

        return brief

    def _convert_and_set_field(self, brief: Brief, field: str, value: str) -> Brief:
        """Convert answer string to appropriate type and set on Brief."""

        if field == "budget_vnd":
            # Parse budget (e.g., "150 triệu" -> 150000000)
            import re

            match = re.search(r"(\d+(?:\.\d+)?)", value)
            if match:
                amount = float(match.group(1))
                if "triệu" in value.lower() or "million" in value.lower():
                    brief.budget_vnd = int(amount * 1_000_000)
                elif "tỷ" in value.lower() or "billion" in value.lower():
                    brief.budget_vnd = int(amount * 1_000_000_000)
                else:
                    # Assume VND
                    brief.budget_vnd = int(amount)
        elif field == "industry":
            brief.industry = value
        elif field == "goal":
            brief.goal = value
        elif field == "timeline":
            brief.timeline = value
        elif field == "target_audience":
            brief.target_audience = value
        elif field == "constraints":
            brief.constraints = [value] if value else []

        return brief

    def skip_optional(self, question_id: str) -> None:
        """
        C.5 §6: Skip an optional question.
        Records the assumption as implicit approval.
        """
        question = self.stack.get_by_id(question_id)
        if question and not question.is_mandatory:
            question.answer = f"[SKIPPED - assuming: {question.assumption}]"
            question.answered = True

    def get_question_card_data(self) -> list[dict]:
        """
        Get questions formatted for the frontend question card.
        C.5 §5: Returns structured data for the question card UI.
        """
        batch = self.stack.next_batch()

        return [
            {
                "id": q.id,
                "text": q.text,
                "priority": q.priority,
                "is_mandatory": q.is_mandatory,
                "assumption": q.assumption,
                "target_field": q.target_field,
            }
            for q in batch
        ]


# =============================================================================
# Module-level Functions
# =============================================================================

_question_manager: Optional[QuestionManager] = None


def get_question_manager() -> QuestionManager:
    """Get the question manager singleton."""
    global _question_manager
    if _question_manager is None:
        _question_manager = QuestionManager()
    return _question_manager
