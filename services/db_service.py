from __future__ import annotations

import json
from typing import Any

from db.base import init_database, session_scope
from db.models import Article, AuditLog, FeedbackMessage, RagAnswer, RagAnswerSource, SearchQuery


def initialize_database() -> None:
    init_database()


def upsert_article_reference(*, doc_id: str, title: str, breadcrumbs: list[str], normalized_file: str = "", source_file: str = "", original_url: str = "") -> int | None:
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


def save_search_interaction(*, question: str, result: dict[str, Any], channel: str = "web") -> dict[str, Any]:
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
