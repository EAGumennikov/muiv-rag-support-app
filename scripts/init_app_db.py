#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CLI-скрипт для явной инициализации SQL-базы приложения.

Скрипт нужен для локального учебного запуска: он создает таблицы заранее,
не заставляя пользователя сначала открывать веб-приложение. При этом логика
создания таблиц остается общей и берется из сервисного SQL-слоя.
"""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parent
# Добавляем корень репозитория в sys.path, чтобы скрипт можно было запускать
# напрямую как отдельный CLI-инструмент, а не только как пакетный модуль.
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

from db.config import get_database_url
from services.db_service import initialize_database


def main() -> None:
    # Скрипт только инициализирует таблицы и сообщает, какой URL БД используется.
    initialize_database()
    print(f"База данных инициализирована: {get_database_url()}")


if __name__ == "__main__":
    main()
