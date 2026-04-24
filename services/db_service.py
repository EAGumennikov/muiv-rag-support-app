from __future__ import annotations

"""
Сервисный слой работы с SQL-базой приложения.

Модуль скрывает от остального кода детали ORM-операций: создание таблиц,
сохранение feedback, запись истории запросов и поддержку базовых справочников.
За счет этого Flask-маршруты и другие сервисы работают с понятными функциями,
а не с низкоуровневыми SQLAlchemy-вызовами.
"""

import json
from typing import Any

from sqlalchemy import func

from db.base import init_database, session_scope
from db.models import (
    Article,
    AuditLog,
    FeedbackMessage,
    FaqItem,
    GlossaryTerm,
    OnboardingPage,
    RagAnswer,
    RagAnswerSource,
    Role,
    SearchQuery,
    User,
    UserRole,
)


def initialize_database() -> None:
    # Явная функция инициализации нужна и для Flask-приложения, и для CLI-скрипта.
    init_database()


def upsert_article_reference(*, doc_id: str, title: str, breadcrumbs: list[str], normalized_file: str = "", source_file: str = "", original_url: str = "") -> int | None:
    # При сохранении истории ответов важно не плодить дубликаты статей.
    # Поэтому метаданные статьи добавляются по схеме upsert.
    if not doc_id:
        return None

    with session_scope() as session:
        article = _upsert_article_reference_in_session(
            session=session,
            doc_id=doc_id,
            title=title,
            breadcrumbs=breadcrumbs,
            normalized_file=normalized_file,
            source_file=source_file,
            original_url=original_url,
        )
        session.flush()
        return article.id


def write_audit_log(*, event_type: str, entity_type: str = "", entity_id: str = "", payload: dict[str, Any] | None = None) -> None:
    # Аудит пока реализован минимально, но уже позволяет видеть,
    # какие пользовательские действия были зафиксированы в системе.
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
    # Обратная связь сохраняется в прикладную таблицу и сразу возвращается
    # в виде словаря, чтобы маршрут мог при необходимости работать без ORM-объекта.
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


def save_search_interaction(*, question: str, result: dict[str, Any], channel: str = "web") -> dict[str, Any]:
    # Функция сохраняет весь след одного обращения к RAG:
    # вопрос, ответ, debug-метрики и список использованных источников.
    initialize_database()

    with session_scope() as session:
        search_query = SearchQuery(
            question_text=question.strip(),
            channel=channel,
            retrieved_chunks_count=int(result.get("debug", {}).get("retrieved_chunks", 0)),
            used_chunks_count=int(result.get("debug", {}).get("used_chunks", 0)),
            debug_json=json.dumps(result.get("debug", {}), ensure_ascii=False),
        )
        session.add(search_query)
        session.flush()

        rag_answer = RagAnswer(
            search_query_id=search_query.id,
            answer_text=result.get("answer", "").strip(),
            prompt_text=result.get("prompt", "").strip(),
            source_labels_json=json.dumps(result.get("source_labels", []), ensure_ascii=False),
        )
        session.add(rag_answer)
        session.flush()

        sources = result.get("sources", []) or []
        for index, source in enumerate(sources, start=1):
            # Для каждого источника пытаемся связать ответ с уже известной статьей,
            # чтобы история запросов была связана с каталогом документов.
            article = _upsert_article_reference_in_session(
                session=session,
                doc_id=(source.get("doc_id") or "").strip(),
                title=(source.get("title") or "").strip(),
                breadcrumbs=source.get("breadcrumbs") or [],
                original_url=(source.get("original_url") or "").strip(),
            )
            session.add(
                RagAnswerSource(
                    rag_answer_id=rag_answer.id,
                    article_id=article.id if article else None,
                    doc_id=(source.get("doc_id") or "").strip(),
                    title=(source.get("title") or "").strip(),
                    breadcrumbs_json=json.dumps(source.get("breadcrumbs") or [], ensure_ascii=False),
                    section_label=(source.get("section") or "").strip(),
                    original_url=(source.get("original_url") or "").strip(),
                    sort_order=index,
                )
            )

        session.flush()
        payload = {
            "search_query_id": search_query.id,
            "rag_answer_id": rag_answer.id,
            "sources_count": len(sources),
        }

    write_audit_log(
        event_type="search_interaction_saved",
        entity_type="search_query",
        entity_id=str(payload["search_query_id"]),
        payload={"sources_count": payload["sources_count"]},
    )
    return payload


def _upsert_article_reference_in_session(*, session, doc_id: str, title: str, breadcrumbs: list[str], normalized_file: str = "", source_file: str = "", original_url: str = "") -> Article | None:
    # Внутренняя версия upsert используется внутри уже открытой транзакции,
    # чтобы не плодить вложенные session_scope при сохранении истории ответа.
    if not doc_id:
        return None

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
        return article

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
    return article


def list_users_with_roles() -> list[dict[str, Any]]:
    # Список пользователей нужен для административной страницы управления доступом.
    with session_scope() as session:
        users = session.query(User).order_by(User.username.asc()).all()
        payload = []
        for user in users:
            roles = [
                role.code
                for role in (
                    session.query(Role)
                    .join(UserRole, UserRole.role_id == Role.id)
                    .filter(UserRole.user_id == user.id)
                    .order_by(Role.code.asc())
                    .all()
                )
            ]
            payload.append(
                {
                    "id": user.id,
                    "username": user.username,
                    "full_name": user.full_name,
                    "email": user.email,
                    "is_active": user.is_active,
                    "roles": roles,
                }
            )
        return payload


def list_roles_summary() -> list[dict[str, Any]]:
    with session_scope() as session:
        rows = (
            session.query(Role, func.count(UserRole.id))
            .outerjoin(UserRole, UserRole.role_id == Role.id)
            .group_by(Role.id)
            .order_by(Role.code.asc())
            .all()
        )
        return [
            {
                "code": role.code,
                "name": role.name,
                "description": role.description,
                "users_count": users_count,
            }
            for role, users_count in rows
        ]


def list_feedback_messages(limit: int = 20) -> list[dict[str, Any]]:
    with session_scope() as session:
        rows = (
            session.query(FeedbackMessage)
            .order_by(FeedbackMessage.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "name": row.name,
                "email": row.email,
                "topic": row.topic,
                "status": row.status,
                "created_at": row.created_at.isoformat(sep=" ", timespec="seconds"),
            }
            for row in rows
        ]


def list_recent_search_queries(limit: int = 20) -> list[dict[str, Any]]:
    with session_scope() as session:
        rows = (
            session.query(SearchQuery)
            .order_by(SearchQuery.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "question_text": row.question_text,
                "retrieved_chunks_count": row.retrieved_chunks_count,
                "used_chunks_count": row.used_chunks_count,
                "created_at": row.created_at.isoformat(sep=" ", timespec="seconds"),
            }
            for row in rows
        ]


def list_recent_rag_answers(limit: int = 20) -> list[dict[str, Any]]:
    with session_scope() as session:
        rows = (
            session.query(RagAnswer)
            .order_by(RagAnswer.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "answer_text": row.answer_text[:240] + ("..." if len(row.answer_text) > 240 else ""),
                "created_at": row.created_at.isoformat(sep=" ", timespec="seconds"),
            }
            for row in rows
        ]


def list_recent_audit_logs(limit: int = 20) -> list[dict[str, Any]]:
    with session_scope() as session:
        rows = (
            session.query(AuditLog)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "event_type": row.event_type,
                "entity_type": row.entity_type,
                "entity_id": row.entity_id,
                "created_at": row.created_at.isoformat(sep=" ", timespec="seconds"),
            }
            for row in rows
        ]


def get_admin_dashboard_stats() -> list[dict[str, Any]]:
    with session_scope() as session:
        return [
            {"label": "Пользователи", "value": session.query(func.count(User.id)).scalar() or 0},
            {"label": "Роли", "value": session.query(func.count(Role.id)).scalar() or 0},
            {"label": "Сообщения feedback", "value": session.query(func.count(FeedbackMessage.id)).scalar() or 0},
            {"label": "Поисковые запросы", "value": session.query(func.count(SearchQuery.id)).scalar() or 0},
            {"label": "Статьи", "value": session.query(func.count(Article.id)).scalar() or 0},
        ]


def get_content_statistics() -> list[dict[str, Any]]:
    with session_scope() as session:
        return [
            {"label": "Статьи", "value": session.query(func.count(Article.id)).scalar() or 0},
            {"label": "Термины глоссария", "value": session.query(func.count(GlossaryTerm.id)).scalar() or 0},
            {"label": "Страницы onboarding", "value": session.query(func.count(OnboardingPage.id)).scalar() or 0},
            {"label": "FAQ-элементы", "value": session.query(func.count(FaqItem.id)).scalar() or 0},
        ]
