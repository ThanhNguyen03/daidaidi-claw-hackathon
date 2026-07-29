"""
CS Agent (Customer Service Orchestrator)
=========================================
Orchestrates cs_agent and predict_agent skills for CS mode.
Much simpler than the sales central agent — pure Q&A, no brief extraction,
no proposal pipeline, no checkpoint flow.

Routing logic:
- Default: cs_agent (handles sale-team support + bug intake for CSHub)
- Predict mode: predict_agent (tarot / fortune reading — fun feature)
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import AsyncGenerator

from schemas.state import SalesCaseState

# Triggers that route to predict_agent
_PREDICT_TRIGGERS = [
    # Tarot
    "tarot", "xem tarot", "bài tarot", "bai tarot", "rút bài", "rut bai",
    # General divination
    "xem bói", "bói", "boi", "bói toán", "boi toan",
    # Numerology (new)
    "thần số học", "than so hoc", "số học", "so hoc",
    "số đường đời", "so duong doi", "số vận mệnh", "so van menh",
    # Gieo quẻ / xin sâm (new)
    "gieo quẻ", "gieo que", "xin quẻ", "xin que",
    "xin sâm", "xin sam", "quẻ sâm", "que sam",
    "lắc ống", "lac ong",
    # Fate / fortune
    "số phận", "so phan", "vận mệnh", "van menh",
    "vận hôm nay", "van hom nay", "vận số", "van so",
    "xem vận", "xem van", "xem số", "xem so",
    # Topics
    "tình duyên", "tinh duyen", "tài lộc", "tai loc",
    "sự nghiệp", "su nghiep", "tử vi", "tu vi",
    # Casual divination phrasing
    "xem cho mình", "xem cho minh", "xem cho tao", "xem cho tui",
    "bói cho mình", "bói cho tao", "bói cho tui",
    "dự đoán", "du doan", "fortune", "predict",
    "xem ngày", "xem ngay", "hôm nay thế nào", "hom nay the nao",
]

# CS-specific keywords — if user is in predict context but message has these,
# re-route back to cs_agent
_CS_KEYWORDS = [
    "bug", "lỗi", "loi", "cshub", "zns", "oa", "mini app", "zalo",
    "ticket", "report", "báo cáo", "bao cao", "fix", "sửa", "sua",
    "hỗ trợ", "ho tro", "hướng dẫn", "huong dan", "cách dùng",
    "tính năng", "tinh nang", "api", "webhook", "config", "cấu hình",
]

_cs_agent_instance = None


def get_cs_agent() -> "CsAgent":
    global _cs_agent_instance
    if _cs_agent_instance is None:
        _cs_agent_instance = CsAgent()
    return _cs_agent_instance


class CsAgent:
    """
    Lightweight orchestrator for CS mode.
    Routes to cs_agent or predict_agent based on message intent.
    """

    def __init__(self):
        self._cs_skill = None
        self._predict_skill = None

    def _get_cs_skill(self):
        if self._cs_skill is None:
            from skills.cs_agent.skill import CsAgentSkill
            self._cs_skill = CsAgentSkill()
        return self._cs_skill

    def _get_predict_skill(self):
        if self._predict_skill is None:
            from skills.predict_agent.skill import PredictAgentSkill
            self._predict_skill = PredictAgentSkill()
        return self._predict_skill

    def _choose_skill(self, message: str, history: list | None = None):
        msg_lower = message.lower()

        # 1. Explicit predict trigger → always predict_agent
        for trigger in _PREDICT_TRIGGERS:
            if trigger in msg_lower:
                return self._get_predict_skill(), "predict_agent"

        # 2. Context continuity: if the last assistant turn used predict_agent
        #    AND this message has no CS-specific keywords, keep routing to
        #    predict_agent so follow-ups ("giải thích thêm", "bói lại", "đổi
        #    phương thức") don't accidentally fall through to cs_agent.
        if history:
            for msg in reversed(history):
                if msg.get("role") == "assistant":
                    if msg.get("agent") == "predict_agent":
                        # Still in predict session — re-route to cs only if the
                        # user is clearly asking a CS question
                        for kw in _CS_KEYWORDS:
                            if kw in msg_lower:
                                return self._get_cs_skill(), "cs_agent"
                        return self._get_predict_skill(), "predict_agent"
                    break  # last assistant was cs_agent → use default routing

        return self._get_cs_skill(), "cs_agent"

    async def run(
        self,
        state: SalesCaseState,
        message: str,
    ) -> AsyncGenerator[dict, None]:
        """
        Run CS agent: pick skill, execute, stream result.
        Yields SSE payload dicts (caller wraps them with _sse_data).
        """
        # Record user message
        state.messages.append({
            "role": "user",
            "content": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        history = state.messages[:-1]  # all messages except the one just appended
        skill, skill_name = self._choose_skill(message, history)

        # Emit agent status: thinking
        yield {"type": "agent_status", "agent": skill_name, "status": "thinking"}

        from skills.base import SkillContext

        # Each skill only receives history from its own turns to avoid cross-skill
        # context contamination (e.g. predict_agent seeing "Tôi là CSHub Assistant"
        # messages and following that persona instead of its own system prompt).
        if skill_name == "predict_agent":
            skill_history = [
                m for m in history
                if m.get("role") == "user" or m.get("agent") == "predict_agent"
            ]
        else:
            skill_history = [
                m for m in history
                if m.get("role") == "user" or m.get("agent") == "cs_agent"
            ]

        context = SkillContext(
            task=message,
            messages=skill_history,
            session_id=state.session_id,
        )

        try:
            output = await asyncio.wait_for(skill.execute(context), timeout=120)
        except asyncio.TimeoutError:
            yield {"type": "agent_status", "agent": skill_name, "status": "failed"}
            yield {
                "type": "assistant_message",
                "agent": skill_name,
                "content": "Xin lỗi, quá thời gian chờ. Bạn thử lại nhé.",
            }
            return
        except Exception as e:
            yield {"type": "agent_status", "agent": skill_name, "status": "failed"}
            yield {
                "type": "assistant_message",
                "agent": skill_name,
                "content": f"Có lỗi xảy ra: {str(e)}",
            }
            return

        if output.status == "FAILED" or not output.content:
            yield {"type": "agent_status", "agent": skill_name, "status": "failed"}
            yield {
                "type": "assistant_message",
                "agent": skill_name,
                "content": "Không tìm thấy thông tin phù hợp. Bạn thử diễn đạt lại câu hỏi nhé.",
            }
            return

        yield {"type": "agent_status", "agent": skill_name, "status": "completed"}

        # Stream content in chunks (simulate streaming for responsiveness)
        content = output.content
        chunk_size = 80
        for i in range(0, len(content), chunk_size):
            yield {"type": "content", "content": content[i:i + chunk_size]}
            await asyncio.sleep(0)  # yield event loop

        # Record assistant response in state
        state.messages.append({
            "role": "assistant",
            "content": content,
            "agent": skill_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        state.summary = f"CS: {message[:40]}... -> {skill_name}"
