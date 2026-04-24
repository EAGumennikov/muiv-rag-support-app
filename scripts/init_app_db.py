#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parent
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

from db.config import get_database_url
from services.db_service import initialize_database


def main() -> None:
    initialize_database()
    print(f"База данных инициализирована: {get_database_url()}")


if __name__ == "__main__":
    main()
