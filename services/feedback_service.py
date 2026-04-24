from __future__ import annotations

from typing import Dict

from services.db_service import save_feedback_message


def save_feedback(*, name: str, email: str, topic: str, message: str) -> Dict:
    return save_feedback_message(
        name=name,
        email=email,
        topic=topic,
        message=message,
    )
