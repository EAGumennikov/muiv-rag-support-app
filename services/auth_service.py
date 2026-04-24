from __future__ import annotations

"""
Сервис аутентификации и ролевого доступа.

Модуль отвечает за три связанные задачи:
1. подготовку ролей и демонстрационных учетных записей;
2. проверку логина и пароля;
3. служебные helper/decorator-функции для Flask-маршрутов.

В результате публичный контур остается открытым, а закрытые страницы могут
опираться на единый слой проверки прав без дублирования логики в app.py.
"""

import os
from dataclasses import dataclass
from functools import wraps
from typing import Callable, Iterable

from flask import abort, g, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from db.base import session_scope
from db.models import Role, User, UserRole
from services.db_service import initialize_database, write_audit_log


ROLE_SUPPORT_USER = "support_user"
ROLE_KNOWLEDGE_EDITOR = "knowledge_editor"
ROLE_ADMIN = "admin"

SESSION_USER_ID_KEY = "current_user_id"


@dataclass(frozen=True)
class CurrentUser:
    """Легковесное представление текущего пользователя для Flask-контекста."""

    id: int
    username: str
    full_name: str
    email: str
    is_active: bool
    roles: tuple[str, ...]

    @property
    def display_name(self) -> str:
        return self.full_name or self.username

    def has_role(self, *role_codes: str) -> bool:
        return any(code in self.roles for code in role_codes)


def get_role_definitions() -> list[dict[str, str]]:
    # Роли фиксируются в одном месте, чтобы их можно было использовать
    # и при seed-инициализации, и в проверках прав доступа.
    return [
        {
            "code": ROLE_SUPPORT_USER,
            "name": "Специалист поддержки",
            "description": "Доступ к рабочим пользовательским функциям и личному кабинету.",
        },
        {
            "code": ROLE_KNOWLEDGE_EDITOR,
            "name": "Редактор базы знаний",
            "description": "Доступ к контентным разделам редактирования и служебным материалам.",
        },
        {
            "code": ROLE_ADMIN,
            "name": "Администратор",
            "description": "Полный доступ к административному контуру приложения.",
        },
    ]


def ensure_roles_exist() -> None:
    initialize_database()

    with session_scope() as session_db:
        for role_data in get_role_definitions():
            role = session_db.query(Role).filter(Role.code == role_data["code"]).one_or_none()
            if role is None:
                session_db.add(Role(**role_data))


def ensure_demo_users(*, reset_passwords: bool = False) -> list[dict[str, str]]:
    # Демонстрационные пользователи создаются только для локальной проверки.
    # Их пароли можно переопределить через переменные окружения.
    initialize_database()
    ensure_roles_exist()

    demo_users = [
        {
            "username": "admin",
            "full_name": "Администратор системы",
            "email": "admin@example.local",
            "password": _demo_password("RAG_DEMO_ADMIN_PASSWORD", "admin_demo_123"),
            "roles": [ROLE_ADMIN],
        },
        {
            "username": "editor",
            "full_name": "Редактор базы знаний",
            "email": "editor@example.local",
            "password": _demo_password("RAG_DEMO_EDITOR_PASSWORD", "editor_demo_123"),
            "roles": [ROLE_KNOWLEDGE_EDITOR],
        },
        {
            "username": "support",
            "full_name": "Специалист поддержки",
            "email": "support@example.local",
            "password": _demo_password("RAG_DEMO_SUPPORT_PASSWORD", "support_demo_123"),
            "roles": [ROLE_SUPPORT_USER],
        },
    ]

    with session_scope() as session_db:
        role_map = {role.code: role for role in session_db.query(Role).all()}

        for user_data in demo_users:
            user = session_db.query(User).filter(User.username == user_data["username"]).one_or_none()
            if user is None:
                user = User(
                    username=user_data["username"],
                    full_name=user_data["full_name"],
                    email=user_data["email"],
                    password_hash=generate_password_hash(user_data["password"]),
                    is_active=True,
                )
                session_db.add(user)
                session_db.flush()
            else:
                if reset_passwords:
                    user.password_hash = generate_password_hash(user_data["password"])
                if not user.full_name:
                    user.full_name = user_data["full_name"]
                if not user.email:
                    user.email = user_data["email"]
                user.is_active = True

            existing_role_codes = {
                item.role.code
                for item in session_db.query(UserRole).filter(UserRole.user_id == user.id).all()
                if item.role
            }
            for role_code in user_data["roles"]:
                if role_code not in existing_role_codes:
                    session_db.add(UserRole(user_id=user.id, role_id=role_map[role_code].id))

    return demo_users


def authenticate_user(username: str, password: str) -> CurrentUser | None:
    # Проверка авторизации выполняется по username и password_hash.
    # При невалидных данных функция возвращает None, а не исключение.
    if not username or not password:
        return None

    with session_scope() as session_db:
        user = session_db.query(User).filter(User.username == username.strip()).one_or_none()
        if user is None or not user.is_active:
            return None
        if not check_password_hash(user.password_hash, password):
            return None
        return _build_current_user(session_db, user)


def get_current_user(user_id: int | None) -> CurrentUser | None:
    if not user_id:
        return None

    with session_scope() as session_db:
        user = session_db.query(User).filter(User.id == user_id, User.is_active.is_(True)).one_or_none()
        if user is None:
            return None
        return _build_current_user(session_db, user)


def login_user(user: CurrentUser) -> None:
    session[SESSION_USER_ID_KEY] = user.id
    write_audit_log(
        event_type="user_logged_in",
        entity_type="user",
        entity_id=str(user.id),
        payload={"username": user.username, "roles": list(user.roles)},
    )


def logout_user() -> None:
    user_id = session.pop(SESSION_USER_ID_KEY, None)
    if user_id:
        write_audit_log(
            event_type="user_logged_out",
            entity_type="user",
            entity_id=str(user_id),
        )


def current_user_from_context() -> CurrentUser | None:
    return getattr(g, "current_user", None)


def login_required(view: Callable):
    # Декоратор защищает маршруты личного кабинета и рабочих функций.
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if current_user_from_context() is None:
            return redirect(url_for("login_page", next=request.path))
        return view(*args, **kwargs)

    return wrapped_view


def roles_required(*role_codes: str):
    # Декоратор проверяет не только факт входа, но и наличие нужной роли.
    def decorator(view: Callable):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            user = current_user_from_context()
            if user is None:
                return redirect(url_for("login_page", next=request.path))
            if not user.has_role(*role_codes):
                abort(403)
            return view(*args, **kwargs)

        return wrapped_view

    return decorator


def role_label(role_code: str) -> str:
    mapping = {item["code"]: item["name"] for item in get_role_definitions()}
    return mapping.get(role_code, role_code)


def user_primary_role_label(user: CurrentUser | None) -> str:
    if user is None or not user.roles:
        return ""
    return role_label(user.roles[0])


def user_has_any_role(user: CurrentUser | None, role_codes: Iterable[str]) -> bool:
    if user is None:
        return False
    return any(role in user.roles for role in role_codes)


def _build_current_user(session_db, user: User) -> CurrentUser:
    role_codes = [
        role.code
        for role in (
            session_db.query(Role)
            .join(UserRole, UserRole.role_id == Role.id)
            .filter(UserRole.user_id == user.id)
            .order_by(Role.code.asc())
            .all()
        )
    ]
    return CurrentUser(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        email=user.email,
        is_active=user.is_active,
        roles=tuple(role_codes),
    )


def _demo_password(env_name: str, default_value: str) -> str:
    return os.environ.get(env_name, default_value).strip() or default_value
