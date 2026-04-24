from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict


def feedback_storage_path() -> Path:
    raw_path = os.environ.get("RAG_FEEDBACK_STORAGE_PATH", "").strip()
    if raw_path:
        return Path(os.path.expanduser(raw_path))
    return Path("/tmp/muiv-rag-support-feedback.jsonl")


def save_feedback(*, name: str, email: str, topic: str, message: str) -> Dict:
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "name": name.strip(),
        "email": email.strip(),
        "topic": topic.strip(),
        "message": message.strip(),
        # Позже этот объект можно будет записывать не в JSONL, а в SQL-таблицу обращений.
        "status": "new",
    }

    storage_path = feedback_storage_path()
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    with open(storage_path, "a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=False) + "\n")

    return payload
