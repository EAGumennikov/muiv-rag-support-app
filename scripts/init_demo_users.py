#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт инициализации демонстрационных пользователей и ролей.

Он нужен для локальной проверки контура доступа без открытой регистрации.
Скрипт создает роли и тестовые учетные записи, а также при необходимости
может сбросить их пароли в учебное состояние.
"""

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parent
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

from services.auth_service import ensure_demo_users


def main() -> None:
    parser = argparse.ArgumentParser(description="Создание тестовых пользователей и ролей")
    parser.add_argument(
        "--reset-passwords",
        action="store_true",
        help="Сбросить пароли демонстрационных пользователей к значениям из seed-скрипта",
    )
    args = parser.parse_args()

    demo_users = ensure_demo_users(reset_passwords=args.reset_passwords)
    print("Демонстрационные пользователи подготовлены:")
    for user in demo_users:
        print(f"- {user['username']} / {user['password']} / роли: {', '.join(user['roles'])}")


if __name__ == "__main__":
    main()
