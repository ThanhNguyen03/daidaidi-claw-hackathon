"""
Question Stack
==============
Implements the QuestionStack mechanism for C.5 §2.
Handles batching, prioritization, answer mapping, and re-validation.
"""

import re
from datetime import datetime
from typing import Optional

from schemas.state import Question, Brief


class QuestionStack:
    """
    Manages a stack of questions to ask the user.
    C.5 §2: Batches questions, prioritizes, maps answers.
    """

    def __init__(self):
        self.items: list[Question] = []

    def push(self, questions: list[Question]) -> None:
        existing_ids = {q.id for q in self.items}
        existing_targets = {q.target_field for q in self.items}

        for question in questions:
            if question.id in existing_ids or question.target_field in existing_targets:
                continue
            question.last_asked_at = datetime.now()
            self.items.append(question)
            existing_ids.add(question.id)
            existing_targets.add(question.target_field)

    def next_batch(self) -> list[Question]:
        unanswered = [q for q in self.items if not q.answered]
        unanswered.sort(key=lambda q: (not q.is_mandatory, q.priority, q.asked_count))
        return unanswered

    def get_unanswered_count(self) -> int:
        return sum(1 for q in self.items if not q.answered)

    def has_mandatory_unanswered(self) -> bool:
        return any(q for q in self.items if q.is_mandatory and not q.answered)

    def clear_answered(self) -> None:
        self.items = [q for q in self.items if not q.answered]

    def get_by_id(self, question_id: str) -> Optional[Question]:
        for q in self.items:
            if q.id == question_id:
                return q
        return None

    def to_list(self) -> list[dict]:
        return [q.model_dump() for q in self.items]


class QuestionManager:
    """
    Manages the full question-answer lifecycle.
    C.5 §2: Creates questions, maps answers, triggers re-validation.
    """

    def __init__(self):
        self.stack = QuestionStack()
        self._session_id: Optional[str] = None

    def ensure_session(self, session_id: str) -> None:
        if self._session_id != session_id:
            self.stack = QuestionStack()
            self._session_id = session_id

    def restore_stack(self, items: list[Question]) -> None:
        restored: list[Question] = []
        for item in items:
            if isinstance(item, Question):
                restored.append(item)
            else:
                restored.append(Question.model_validate(item))
        self.stack.items = restored

    def map_answers(self, answers: dict[str, str], brief: Brief) -> Brief:
        for question_id, answer_text in answers.items():
            question = self.stack.get_by_id(question_id)
            if question:
                question.answer = answer_text
                question.answered = True
                question.asked_count += 1

                target_field = question.target_field
                if target_field and answer_text:
                    brief = self._convert_and_set_field(brief, target_field, answer_text)

        return brief

    def map_free_text_answer(self, free_text: str, brief: Brief) -> Brief:
        free_text_lower = free_text.lower()

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

        budget_match = re.search(r"(\d+)\s*(triệu|million|billion|tỷ)?", free_text_lower)
        if budget_match:
            amount = int(budget_match.group(1))
            unit = budget_match.group(2) or "triệu"
            if unit in ["triệu", "million"]:
                brief.budget_vnd = amount * 1_000_000
            elif unit in ["billion", "tỷ"]:
                brief.budget_vnd = amount * 1_000_000_000

        if "launch" in free_text_lower or "ra mắt" in free_text_lower:
            brief.goal = "product launch"
        elif "tăng trưởng" in free_text_lower or "growth" in free_text_lower:
            brief.goal = "growth"

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
        if field == "budget_vnd":
            match = re.search(r"(\d+(?:\.\d+)?)", value)
            if match:
                amount = float(match.group(1))
                if "triệu" in value.lower() or "million" in value.lower():
                    brief.budget_vnd = int(amount * 1_000_000)
                elif "tỷ" in value.lower() or "billion" in value.lower():
                    brief.budget_vnd = int(amount * 1_000_000_000)
                else:
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
        question = self.stack.get_by_id(question_id)
        if question and not question.is_mandatory:
            question.answer = "[SKIPPED]"
            question.answered = True

    def get_question_card_data(self) -> list[dict]:
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


_question_manager: Optional[QuestionManager] = None


def get_question_manager() -> QuestionManager:
    global _question_manager
    if _question_manager is None:
        _question_manager = QuestionManager()
    return _question_manager
