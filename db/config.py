from __future__ import annotations

"""
Конфигурация SQL-подключения приложения.

Модуль определяет, где должна находиться SQLite-база по умолчанию и как
переопределить этот путь через переменные окружения. База намеренно вынесена
во внешний workdir, чтобы не смешивать код репозитория с runtime-данными.
"""

import os
from pathlib import Path


WORKDIR_DEFAULT = Path("~/Projects/muiv-rag-support-workdir").expanduser()
SQLITE_PATH_DEFAULT = WORKDIR_DEFAULT / "output" / "app" / "muiv_rag_support.sqlite3"


def get_database_url() -> str:
    # Если пользователь явно задал SQL URL, используем его.
    # Иначе работаем с локальной SQLite-базой в рабочем каталоге проекта.
    raw_url = os.environ.get("RAG_APP_DATABASE_URL", "").strip()
    if raw_url:
        return raw_url
    return f"sqlite:///{SQLITE_PATH_DEFAULT}"


def ensure_database_parent_dir(database_url: str | None = None) -> None:
    # Для SQLite нужно заранее создать каталог под файл БД.
    # Для внешних СУБД вроде PostgreSQL этот шаг не требуется.
    url = database_url or get_database_url()
    sqlite_prefix = "sqlite:///"
    if not url.startswith(sqlite_prefix):
        return

    raw_path = url[len(sqlite_prefix):]
    db_path = Path(raw_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
