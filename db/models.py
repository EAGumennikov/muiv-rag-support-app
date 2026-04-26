from __future__ import annotations

"""
ORM-модели SQL-слоя приложения.

В файле собраны основные сущности учебного веб-ресурса: пользователи, роли,
статьи базы знаний, сообщения обратной связи, история запросов и ответы RAG.
Набор таблиц сделан с запасом для следующего этапа, чтобы расширять проект
без смены архитектурной основы.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base


def utcnow() -> datetime:
    # Единая функция времени нужна, чтобы timestamp-поля всех моделей
    # создавались согласованно и не дублировали одну и ту же логику.
    return datetime.utcnow()


class Role(Base):
    # Роль нужна как отдельная сущность, чтобы позже поддержать
    # разграничение прав администратора, оператора и обычного пользователя.
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    user_roles: Mapped[list["UserRole"]] = relationship(back_populates="role")


class User(Base):
    # Пользователь связан с историей запросов и обратной связью,
    # чтобы закрытый контур показывал персональные данные сотрудника,
    # а администратор мог анализировать общую картину по системе.
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    email: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    user_roles: Mapped[list["UserRole"]] = relationship(back_populates="user")
    feedback_messages: Mapped[list["FeedbackMessage"]] = relationship(back_populates="user")
    search_queries: Mapped[list["SearchQuery"]] = relationship(back_populates="user")


class UserRole(Base):
    # Связь многие-ко-многим между пользователями и ролями.
    # Отдельная таблица позволяет назначать одному пользователю несколько ролей.
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uq_user_roles_user_role"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    user: Mapped["User"] = relationship(back_populates="user_roles")
    role: Mapped["Role"] = relationship(back_populates="user_roles")


class Article(Base):
    # Таблица статей хранит метаданные документов базы знаний в SQL-слое.
    # Она не заменяет исходный корпус, а добавляет управляемый прикладной слой.
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    doc_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    breadcrumbs_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    normalized_file: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    source_file: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    original_url: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    author: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    published_at_text: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    files: Mapped[list["ArticleFile"]] = relationship(back_populates="article")


class ArticleFile(Base):
    # Отдельная таблица файлов позволяет в будущем хранить несколько
    # представлений одной статьи: markdown, оригинал, экспорт и т.д.
    __tablename__ = "article_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id"), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), default="markdown", nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    article: Mapped["Article"] = relationship(back_populates="files")


class GlossaryTerm(Base):
    # Глоссарий выделен в отдельную таблицу, чтобы термины можно было
    # наполнять и редактировать независимо от шаблонов страниц.
    __tablename__ = "glossary_terms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    term: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    definition: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source_url: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class OnboardingPage(Base):
    # Таблица для будущего хранения шагов онбординга уже в БД, а не только в коде.
    __tablename__ = "onboarding_pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body_markdown: Mapped[str] = mapped_column(Text, default="", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class FaqItem(Base):
    # FAQ тоже вынесен в отдельную сущность, чтобы позже управлять
    # списком вопросов через административный интерфейс.
    __tablename__ = "faq_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question: Mapped[str] = mapped_column(String(500), nullable=False)
    answer_markdown: Mapped[str] = mapped_column(Text, default="", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class FeedbackMessage(Base):
    # Сообщения формы обратной связи — первая реальная пользовательская сущность,
    # которую проект уже сохраняет в SQL-базу. user_id остается nullable:
    # публичная форма должна работать и для неавторизованных посетителей.
    __tablename__ = "feedback_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="new", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    user: Mapped[User | None] = relationship(back_populates="feedback_messages")


class SearchQuery(Base):
    # Таблица хранит сам факт обращения к RAG-поиску:
    # исходный вопрос, базовые debug-метрики retrieval и время запроса.
    # Nullable user_id позволяет сохранить совместимость с публичным поиском.
    __tablename__ = "search_queries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(String(50), default="web", nullable=False)
    retrieved_chunks_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    used_chunks_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    debug_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    user: Mapped[User | None] = relationship(back_populates="search_queries")
    rag_answer: Mapped["RagAnswer"] = relationship(back_populates="search_query", uselist=False)


class RagAnswer(Base):
    # Ответ RAG отделен от вопроса в отдельную таблицу,
    # чтобы было удобнее расширять хранение истории и аналитики.
    __tablename__ = "rag_answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    search_query_id: Mapped[int] = mapped_column(ForeignKey("search_queries.id"), unique=True, nullable=False)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source_labels_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    search_query: Mapped["SearchQuery"] = relationship(back_populates="rag_answer")
    sources: Mapped[list["RagAnswerSource"]] = relationship(back_populates="rag_answer")


class RagAnswerSource(Base):
    # Эта таблица фиксирует, на каких источниках основан конкретный ответ.
    # Она особенно полезна для аудита и последующего анализа качества retrieval.
    __tablename__ = "rag_answer_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rag_answer_id: Mapped[int] = mapped_column(ForeignKey("rag_answers.id"), nullable=False)
    article_id: Mapped[int | None] = mapped_column(ForeignKey("articles.id"), nullable=True)
    doc_id: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    title: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    breadcrumbs_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    section_label: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    original_url: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    rag_answer: Mapped["RagAnswer"] = relationship(back_populates="sources")


class AuditLog(Base):
    # Упрощенный аудит фиксирует ключевые действия приложения,
    # например сохранение feedback или истории поиска.
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    entity_id: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class Setting(Base):
    # Таблица настроек нужна как задел на следующий этап,
    # когда часть параметров можно будет перенести из кода в БД.
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, default="", nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
