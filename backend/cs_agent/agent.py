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
from datetime import datetime
from typing import AsyncGenerator

from schemas.state import SalesCaseState

# Tarot / fortune reading triggers → predict_agent
_PREDICT_TRIGGERS = [
    "tarot",
    "xem bói",
    "xem tarot",
    "bói",
    "boi",
    "dự đoán",
    "du doan",
    "fortune",
    "predict",
    "số phận",
    "so phan",
    "vận mệnh",
    "van menh",
    "xem vận",
    "xem van",
    "tử vi",
    "tu vi",
    "xem ngày",
    "xem ngay",
    "gieo quẻ",
    "gieo que",
    "rút bài",
    "rut bai",
    "bài tarot",
    "bai tarot",
    "xem cho mình",
    "xem cho minh",
    "vận hôm nay",
    "van hom nay",
    "tình duyên",
    "tinh duyen",
    "tài lộc",
    "tai loc",
    "sự nghiệp",
    "su nghiep",
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

    def _choose_skill(self, message: str):
        msg_lower = message.lower()
        for trigger in _PREDICT_TRIGGERS:
            if trigger in msg_lower:
                return self._get_predict_skill(), "predict_agent"
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
            "timestamp": datetime.now().isoformat(),
        })

        skill, skill_name = self._choose_skill(message)

        # Emit agent status: thinking
        yield {"type": "agent_status", "agent": skill_name, "status": "thinking"}

        from skills.base import SkillContext
        context = SkillContext(
            task=message,
            messages=state.messages[:-1],  # exclude the just-appended user msg
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
            "timestamp": datetime.now().isoformat(),
        })
        state.summary = f"CS: {message[:40]}... -> {skill_name}"
