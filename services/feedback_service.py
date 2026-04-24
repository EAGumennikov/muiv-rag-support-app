from __future__ import annotations

"""
Тонкая обертка над сохранением обратной связи.

Сервис специально оставлен простым: веб-маршрут обращается к нему, не зная,
в какой именно слой пишутся данные. Раньше это был файловый JSONL, теперь SQL.
Такой переход показывает, как можно менять инфраструктуру без ломки маршрутов.
"""

from typing import Dict

from services.db_service import save_feedback_message


def save_feedback(*, name: str, email: str, topic: str, message: str) -> Dict:
    # Интерфейс функции сохранен прежним, чтобы форма /feedback продолжала
    # работать без изменений во Flask-маршруте и шаблонах.
    return save_feedback_message(
        name=name,
        email=email,
        topic=topic,
        message=message,
    )
