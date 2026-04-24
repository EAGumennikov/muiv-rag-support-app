from __future__ import annotations

import json
from typing import Any

from db.base import init_database, session_scope
from db.models import Article, AuditLog, FeedbackMessage


def initialize_database() -> None:
    init_database()


def upsert_article_reference(*, doc_id: str, title: str, breadcrumbs: list[str], normalized_file: str = "", source_file: str = "", original_url: str = "") -> int | None:
    if not doc_id:
        return None

    with session_scope() as session:
        article = session.query(Article).filter(Article.doc_id == doc_id).one_or_none()
        if article is None:
            article = Article(
                doc_id=doc_id,
                title=title or doc_id,
                breadcrumbs_json=json.dumps(breadcrumbs or [], ensure_ascii=False),
                normalized_file=normalized_file or "",
                source_file=source_file or "",
                original_url=original_url or "",
            )
            session.add(article)
            session.flush()
            return article.id

        if title and not article.title:
            article.title = title
        if breadcrumbs and article.breadcrumbs_json == "[]":
            article.breadcrumbs_json = json.dumps(breadcrumbs, ensure_ascii=False)
        if normalized_file and not article.normalized_file:
            article.normalized_file = normalized_file
        if source_file and not article.source_file:
            article.source_file = source_file
        if original_url and not article.original_url:
            article.original_url = original_url
        session.flush()
        return article.id


def write_audit_log(*, event_type: str, entity_type: str = "", entity_id: str = "", payload: dict[str, Any] | None = None) -> None:
    with session_scope() as session:
        session.add(
            AuditLog(
                event_type=event_type,
                entity_type=entity_type,
                entity_id=entity_id,
                payload_json=json.dumps(payload or {}, ensure_ascii=False),
            )
        )


def save_feedback_message(*, name: str, email: str, topic: str, message: str, status: str = "new") -> dict[str, Any]:
    initialize_database()

    with session_scope() as session:
        feedback = FeedbackMessage(
            name=name.strip(),
            email=email.strip(),
            topic=topic.strip(),
            message=message.strip(),
            status=status,
        )
        session.add(feedback)
        session.flush()

        payload = {
            "id": feedback.id,
            "created_at": feedback.created_at.isoformat(),
            "name": feedback.name,
            "email": feedback.email,
            "topic": feedback.topic,
            "message": feedback.message,
            "status": feedback.status,
        }

    write_audit_log(
        event_type="feedback_saved",
        entity_type="feedback_message",
        entity_id=str(payload["id"]),
        payload={"topic": payload["topic"], "email": payload["email"]},
    )
    return payload
