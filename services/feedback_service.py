from __future__ import annotations

"""
Тонкая обертка над сохранением обратной связи.

Сервис специально оставлен простым: веб-маршрут обращается к нему, не зная,
в какой именно слой пишутся данные. Раньше это был файловый JSONL, теперь SQL.
Такой переход показывает, как можно менять инфраструктуру без ломки маршрутов.
"""

from typing import Dict

from services.db_service import save_feedback_message


def save_feedback(*, name: str, email: str, topic: str, message: str, user_id: int | None = None) -> Dict:
    # user_id передается только для авторизованных пользователей.
    # Публичная форма сохраняет прежнее поведение и оставляет связь пустой.
    return save_feedback_message(
        name=name,
        email=email,
        topic=topic,
        message=message,
        user_id=user_id,
    )
