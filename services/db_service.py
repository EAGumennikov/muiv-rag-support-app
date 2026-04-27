from __future__ import annotations

"""
Сервисный слой работы с SQL-базой приложения.

Модуль скрывает от остального кода детали ORM-операций: создание таблиц,
сохранение feedback, запись истории запросов и поддержку базовых справочников.
За счет этого Flask-маршруты и другие сервисы работают с понятными функциями,
а не с низкоуровневыми SQLAlchemy-вызовами.
"""

import json
from datetime import date, datetime, time
from typing import Any

from sqlalchemy import func, inspect, text

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
    ensure_personalization_columns()


def ensure_personalization_columns() -> None:
    # create_all не изменяет уже существующие таблицы SQLite, поэтому для
    # учебного прототипа добавляем новые nullable-колонки аккуратным ALTER.
    # Nullable-поля не ломают старые записи и сохраняют публичные сценарии.
    from db.base import get_engine

    engine = get_engine()
    inspector = inspect(engine)
    planned_columns = {
        "feedback_messages": "user_id",
        "search_queries": "user_id",
    }

    with engine.begin() as connection:
        for table_name, column_name in planned_columns.items():
            existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
            if column_name not in existing_columns:
                connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} INTEGER"))


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


def save_feedback_message(*, name: str, email: str, topic: str, message: str, status: str = "new", user_id: int | None = None) -> dict[str, Any]:
    # Обратная связь сохраняется в прикладную таблицу и сразу возвращается
    # в виде словаря, чтобы маршрут мог при необходимости работать без ORM-объекта.
    initialize_database()

    with session_scope() as session:
        feedback = FeedbackMessage(
            user_id=user_id,
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
            "user_id": feedback.user_id,
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
        payload={"topic": payload["topic"], "email": payload["email"], "user_id": payload["user_id"]},
    )
    return payload


def save_search_interaction(*, question: str, result: dict[str, Any], channel: str = "web", user_id: int | None = None) -> dict[str, Any]:
    # Функция сохраняет весь след одного обращения к RAG:
    # вопрос, ответ, debug-метрики и список использованных источников.
    initialize_database()

    with session_scope() as session:
        search_query = SearchQuery(
            user_id=user_id,
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
            "user_id": search_query.user_id,
        }

    write_audit_log(
        event_type="search_interaction_saved",
        entity_type="search_query",
        entity_id=str(payload["search_query_id"]),
        payload={"sources_count": payload["sources_count"], "user_id": payload["user_id"]},
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


def list_feedback_messages(limit: int = 20, user_id: int | None = None) -> list[dict[str, Any]]:
    with session_scope() as session:
        query = session.query(FeedbackMessage).outerjoin(User, FeedbackMessage.user_id == User.id)
        if user_id is not None:
            query = query.filter(FeedbackMessage.user_id == user_id)
        rows = query.order_by(FeedbackMessage.created_at.desc()).limit(limit).all()
        return [
            {
                "id": row.id,
                "user_id": row.user_id,
                "username": row.user.username if row.user else "",
                "name": row.name,
                "email": row.email,
                "topic": row.topic,
                "message": row.message,
                "status": row.status,
                "created_at": row.created_at.isoformat(sep=" ", timespec="seconds"),
            }
            for row in rows
        ]


def list_recent_search_queries(limit: int = 20, user_id: int | None = None) -> list[dict[str, Any]]:
    with session_scope() as session:
        query = session.query(SearchQuery).outerjoin(User, SearchQuery.user_id == User.id)
        if user_id is not None:
            query = query.filter(SearchQuery.user_id == user_id)
        rows = query.order_by(SearchQuery.created_at.desc()).limit(limit).all()
        return [
            {
                "id": row.id,
                "user_id": row.user_id,
                "username": row.user.username if row.user else "",
                "question_text": row.question_text,
                "retrieved_chunks_count": row.retrieved_chunks_count,
                "used_chunks_count": row.used_chunks_count,
                "created_at": row.created_at.isoformat(sep=" ", timespec="seconds"),
            }
            for row in rows
        ]


def count_user_search_queries_for_day(user_id: int, target_day: date | None = None) -> int:
    # Дневной лимит RAG считается по уже сохраненной SQL-истории.
    # Такой подход не требует внешнего rate-limit сервиса и работает в demo-контуре.
    day = target_day or date.today()
    day_start = datetime.combine(day, time.min)
    day_end = datetime.combine(day, time.max)

    with session_scope() as session:
        return (
            session.query(func.count(SearchQuery.id))
            .filter(
                SearchQuery.user_id == user_id,
                SearchQuery.created_at >= day_start,
                SearchQuery.created_at <= day_end,
            )
            .scalar()
            or 0
        )


def list_recent_rag_answers(limit: int = 20, user_id: int | None = None) -> list[dict[str, Any]]:
    with session_scope() as session:
        query = session.query(RagAnswer).join(SearchQuery, RagAnswer.search_query_id == SearchQuery.id)
        if user_id is not None:
            query = query.filter(SearchQuery.user_id == user_id)
        rows = query.order_by(RagAnswer.created_at.desc()).limit(limit).all()
        return [
            {
                "id": row.id,
                "search_query_id": row.search_query_id,
                "question_text": row.search_query.question_text if row.search_query else "",
                "username": row.search_query.user.username if row.search_query and row.search_query.user else "",
                "answer_text": row.answer_text[:240] + ("..." if len(row.answer_text) > 240 else ""),
                "created_at": row.created_at.isoformat(sep=" ", timespec="seconds"),
            }
            for row in rows
        ]


def get_rag_answer_export_payload(rag_answer_id: int) -> dict[str, Any] | None:
    # Экспорт ответа требует больше данных, чем карточка в кабинете:
    # исходный вопрос, владельца, полный текст ответа и перечень источников.
    # Служебные поля вроде prompt_text наружу не отдаются.
    with session_scope() as session:
        answer = session.query(RagAnswer).filter(RagAnswer.id == rag_answer_id).one_or_none()
        if answer is None:
            return None

        query = answer.search_query
        sources = [
            {
                "title": source.title or source.doc_id,
                "breadcrumbs": json.loads(source.breadcrumbs_json or "[]"),
                "section_label": source.section_label,
                "original_url": source.original_url,
                "doc_id": source.doc_id,
            }
            for source in sorted(answer.sources, key=lambda item: item.sort_order)
        ]
        return {
            "id": answer.id,
            "answer_text": answer.answer_text,
            "created_at": answer.created_at.isoformat(sep=" ", timespec="seconds"),
            "question_text": query.question_text if query else "",
            "query_created_at": query.created_at.isoformat(sep=" ", timespec="seconds") if query else "",
            "user_id": query.user_id if query else None,
            "username": query.user.username if query and query.user else "",
            "sources": sources,
        }


def list_user_history_export_rows(user_id: int) -> list[dict[str, Any]]:
    # Пользовательская выгрузка строится только по текущему user_id.
    # Это не административный сценарий, поэтому чужие записи сюда не попадают.
    with session_scope() as session:
        rows = (
            session.query(SearchQuery)
            .filter(SearchQuery.user_id == user_id)
            .order_by(SearchQuery.created_at.desc())
            .all()
        )
        return [
            {
                "created_at": row.created_at.isoformat(sep=" ", timespec="seconds"),
                "question_text": row.question_text,
                "retrieved_chunks_count": row.retrieved_chunks_count,
                "used_chunks_count": row.used_chunks_count,
                "has_answer": "Да" if row.rag_answer else "Нет",
                "answer_excerpt": _excerpt(row.rag_answer.answer_text if row.rag_answer else "", 260),
            }
            for row in rows
        ]


def list_feedback_export_rows() -> list[dict[str, Any]]:
    # Административная выгрузка feedback содержит прикладные поля обращения,
    # но не включает внутренние идентификаторы файлов или технические пути.
    with session_scope() as session:
        rows = (
            session.query(FeedbackMessage)
            .outerjoin(User, FeedbackMessage.user_id == User.id)
            .order_by(FeedbackMessage.created_at.desc())
            .all()
        )
        return [
            {
                "created_at": row.created_at.isoformat(sep=" ", timespec="seconds"),
                "username": row.user.username if row.user else "",
                "name": row.name,
                "email": row.email,
                "topic": row.topic,
                "message": row.message,
                "message_excerpt": _excerpt(row.message, 320),
                "status": row.status,
            }
            for row in rows
        ]


def list_search_history_export_rows() -> list[dict[str, Any]]:
    # Общая история нужна только администратору, поэтому сервис возвращает
    # все записи, включая публичные запросы без пользователя.
    with session_scope() as session:
        rows = (
            session.query(SearchQuery)
            .outerjoin(User, SearchQuery.user_id == User.id)
            .order_by(SearchQuery.created_at.desc())
            .all()
        )
        return [
            {
                "created_at": row.created_at.isoformat(sep=" ", timespec="seconds"),
                "username": row.user.username if row.user else "",
                "question_text": row.question_text,
                "retrieved_chunks_count": row.retrieved_chunks_count,
                "used_chunks_count": row.used_chunks_count,
                "has_answer": "Да" if row.rag_answer else "Нет",
                "answer_excerpt": _excerpt(row.rag_answer.answer_text if row.rag_answer else "", 260),
            }
            for row in rows
        ]


def get_admin_statistics_export_payload() -> dict[str, Any]:
    # Статистическая выгрузка собирает агрегаты для отчета администратора:
    # счетчики сущностей, распределение feedback по статусам и свежий аудит.
    with session_scope() as session:
        feedback_status_rows = (
            session.query(FeedbackMessage.status, func.count(FeedbackMessage.id))
            .group_by(FeedbackMessage.status)
            .order_by(FeedbackMessage.status.asc())
            .all()
        )
        return {
            "summary": [
                {"metric": "Пользователи", "value": session.query(func.count(User.id)).scalar() or 0},
                {"metric": "Роли", "value": session.query(func.count(Role.id)).scalar() or 0},
                {"metric": "Сообщения feedback", "value": session.query(func.count(FeedbackMessage.id)).scalar() or 0},
                {"metric": "Поисковые запросы", "value": session.query(func.count(SearchQuery.id)).scalar() or 0},
                {"metric": "RAG-ответы", "value": session.query(func.count(RagAnswer.id)).scalar() or 0},
            ],
            "feedback_statuses": [
                {"status": status, "count": count}
                for status, count in feedback_status_rows
            ],
            "audit": [
                {
                    "created_at": row.created_at.isoformat(sep=" ", timespec="seconds"),
                    "event_type": row.event_type,
                    "entity_type": row.entity_type,
                    "entity_id": row.entity_id,
                }
                for row in (
                    session.query(AuditLog)
                    .order_by(AuditLog.created_at.desc())
                    .limit(30)
                    .all()
                )
            ],
        }


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


def _excerpt(text: str, limit: int) -> str:
    # В табличных выгрузках длинные ответы и обращения лучше показывать
    # кратким фрагментом, чтобы XLSX оставался читаемым.
    value = " ".join((text or "").split())
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def get_admin_dashboard_stats() -> list[dict[str, Any]]:
    with session_scope() as session:
        return [
            {"label": "Пользователи", "value": session.query(func.count(User.id)).scalar() or 0},
            {"label": "Роли", "value": session.query(func.count(Role.id)).scalar() or 0},
            {"label": "Сообщения feedback", "value": session.query(func.count(FeedbackMessage.id)).scalar() or 0},
            {"label": "Поисковые запросы", "value": session.query(func.count(SearchQuery.id)).scalar() or 0},
            {"label": "RAG-ответы", "value": session.query(func.count(RagAnswer.id)).scalar() or 0},
            {"label": "Статьи", "value": session.query(func.count(Article.id)).scalar() or 0},
        ]


def get_user_dashboard_stats(user_id: int) -> list[dict[str, Any]]:
    # Кабинет сотрудника показывает только данные текущей учетной записи.
    # Такое ограничение реализует базовое разграничение между пользователем и админом.
    with session_scope() as session:
        return [
            {"label": "Мои вопросы", "value": session.query(func.count(SearchQuery.id)).filter(SearchQuery.user_id == user_id).scalar() or 0},
            {
                "label": "Мои ответы",
                "value": (
                    session.query(func.count(RagAnswer.id))
                    .join(SearchQuery, RagAnswer.search_query_id == SearchQuery.id)
                    .filter(SearchQuery.user_id == user_id)
                    .scalar()
                    or 0
                ),
            },
            {"label": "Мои обращения", "value": session.query(func.count(FeedbackMessage.id)).filter(FeedbackMessage.user_id == user_id).scalar() or 0},
        ]


def get_feedback_message(feedback_id: int) -> dict[str, Any] | None:
    # Детальная карточка нужна администратору для просмотра полного текста
    # обращения и изменения статуса без отдельного CRUD-интерфейса.
    with session_scope() as session:
        row = session.query(FeedbackMessage).filter(FeedbackMessage.id == feedback_id).one_or_none()
        if row is None:
            return None
        return {
            "id": row.id,
            "user_id": row.user_id,
            "username": row.user.username if row.user else "",
            "name": row.name,
            "email": row.email,
            "topic": row.topic,
            "message": row.message,
            "status": row.status,
            "created_at": row.created_at.isoformat(sep=" ", timespec="seconds"),
        }


def update_feedback_status(*, feedback_id: int, status: str, admin_user_id: int) -> bool:
    # Статусы фиксируются в сервисном слое, чтобы маршрут не принимал
    # произвольные значения и не размазывал правила обработки обращений.
    allowed_statuses = {"new", "in_progress", "resolved", "rejected"}
    if status not in allowed_statuses:
        return False

    with session_scope() as session:
        feedback = session.query(FeedbackMessage).filter(FeedbackMessage.id == feedback_id).one_or_none()
        if feedback is None:
            return False
        feedback.status = status

    write_audit_log(
        event_type="feedback_status_updated",
        entity_type="feedback_message",
        entity_id=str(feedback_id),
        payload={"status": status, "admin_user_id": admin_user_id},
    )
    return True


def list_recent_answer_sources(limit: int = 20) -> list[dict[str, Any]]:
    # Редактору знаний важны не все ответы целиком, а документы,
    # которые реально использовались как основание RAG-выдачи.
    with session_scope() as session:
        rows = (
            session.query(RagAnswerSource)
            .order_by(RagAnswerSource.id.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "doc_id": row.doc_id,
                "title": row.title or row.doc_id,
                "section_label": row.section_label,
                "original_url": row.original_url,
            }
            for row in rows
        ]


def get_content_statistics() -> list[dict[str, Any]]:
    with session_scope() as session:
        return [
            {"label": "Статьи", "value": session.query(func.count(Article.id)).scalar() or 0},
            {"label": "Термины глоссария", "value": session.query(func.count(GlossaryTerm.id)).scalar() or 0},
            {"label": "Страницы onboarding", "value": session.query(func.count(OnboardingPage.id)).scalar() or 0},
            {"label": "FAQ-элементы", "value": session.query(func.count(FaqItem.id)).scalar() or 0},
        ]
