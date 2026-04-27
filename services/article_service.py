from __future__ import annotations

"""
Сервис пользовательской работы со статьями базы знаний.

Модуль отвечает за чтение метаданных статей из подготовленного корпуса,
сборку текста статьи из чанков, фильтрацию "мусорных" секций и подготовку
карточек источников для веб-интерфейса. Это позволяет не смешивать
представление пользовательских статей с техническими внутренними полями.
"""

import csv
import json
import os
import re
import unicodedata
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path
from typing import Dict, List
from urllib.parse import quote

from flask import abort

from scripts.common_paths import CHUNK_MAP_PATH_DEFAULT, INPUT_CHUNKS_DEFAULT


WORKDIR_PATH = Path(CHUNK_MAP_PATH_DEFAULT).expanduser().resolve().parents[2]
NORMALIZED_DIR_DEFAULT = WORKDIR_PATH / "output" / "normalized"
NORMALIZED_INDEX_DEFAULT = WORKDIR_PATH / "output" / "normalized_index.csv"

GENERIC_SECTIONS = {
    "",
    "раздел",
    "ответ",
    "секция",
    "вопрос",
    "окружение",
    "без раздела",
    "материал",
    "подробности",
}

FEATURED_DOC_IDS = [
    "263032388",
    "311338753",
    "311338890",
    "191106593",
    "365860560",
    "417762318",
]


def _normalize_text(value: str) -> str:
    # Для сравнения и отображения метаданных удобнее заранее убрать
    # лишние пробелы и переводы строк, которые часто встречаются в корпусе.
    return re.sub(r"\s+", " ", (value or "").strip())


def _public_doc_allowed(doc_id: str, title: str) -> bool:
    # В подготовленных данных встречаются служебные и битые артефакты вида ._*
    # Их нельзя показывать пользователю ни в каталоге, ни в источниках ответа.
    if not doc_id or doc_id.startswith("._") or doc_id.startswith(".__"):
        return False
    clean_title = _normalize_text(title)
    return bool(clean_title and not clean_title.startswith("._"))


def _display_title(title: str) -> str:
    # В корпусе часть заголовков содержит служебный префикс пространства.
    # Для карточек сайта показываем более короткое пользовательское название.
    title = _normalize_text(title)
    for prefix in ("База знаний : ", "База знаний: "):
        if title.startswith(prefix):
            title = title[len(prefix):].strip()
            break
    return title.lstrip("_").strip()


def is_meaningful_section(section: str) -> bool:
    # Не каждый заголовок секции полезен пользователю.
    # Здесь отсекаются слишком общие и технические значения вроде "Раздел" или "Ответ".
    cleaned = _normalize_text(section).lstrip("#").strip()
    if not cleaned:
        return False
    lowered = cleaned.lower()
    if lowered in GENERIC_SECTIONS:
        return False
    if lowered.startswith("раздел ") or lowered.startswith("секция "):
        return False
    if lowered in {"overview", "general", "details"}:
        return False
    if "техническ" in lowered or "служебн" in lowered:
        return False
    if len(cleaned) <= 2:
        return False
    return True


def _build_source_excerpt(chunk_text: str, section: str) -> str:
    # Краткая выдержка нужна для карточки источника: она помогает понять,
    # почему именно эта статья попала в ответ, не открывая документ целиком.
    text = (chunk_text or "").strip()
    if not text:
        return ""

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""

    cleaned_section = _normalize_text(section).lstrip("#").strip().lower()
    if lines:
        first_line = _normalize_text(lines[0]).lstrip("#").strip().lower()
        if cleaned_section and first_line == cleaned_section:
            lines = lines[1:]

    excerpt = _normalize_text(" ".join(lines))
    if len(excerpt) > 220:
        excerpt = excerpt[:217].rstrip() + "..."
    return excerpt


def _load_doc_index() -> Dict[str, Dict]:
    # Если рядом с нормализованными markdown-статьями есть CSV-индекс,
    # берем из него дополнительные поля: автора, дату и original_url.
    index: Dict[str, Dict] = {}
    index_path = NORMALIZED_INDEX_DEFAULT
    if not index_path.exists():
        return index

    with open(index_path, "r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            doc_id = row.get("doc_id", "").strip()
            if doc_id:
                index[doc_id] = row
    return index


def _merge_with_overlap(existing: str, incoming: str, max_overlap: int = 240) -> str:
    # При сборке статьи из чанков нужно аккуратно склеить соседние куски,
    # не дублируя общий текст в месте overlap.
    existing = existing.rstrip()
    incoming = incoming.lstrip()
    if not existing:
        return incoming
    if not incoming:
        return existing

    limit = min(len(existing), len(incoming), max_overlap)
    for size in range(limit, 20, -1):
        if existing[-size:] == incoming[:size]:
            return existing + incoming[size:]
    return existing + "\n\n" + incoming


def _strip_duplicate_heading(text: str, section_heading: str) -> str:
    # Чанк может начинаться с того же заголовка, который уже хранится
    # в его метаданных. Для пользовательской статьи такой дубль убираем.
    cleaned_section = _normalize_text(section_heading).lstrip("#").strip()
    if not cleaned_section:
        return text.strip()

    lines = text.strip().splitlines()
    if not lines:
        return ""

    first_line = _normalize_text(lines[0]).lstrip("#").strip()
    if first_line.lower() == cleaned_section.lower():
        return "\n".join(lines[1:]).strip()
    return text.strip()


@lru_cache(maxsize=1)
def get_documents_map() -> Dict[str, Dict]:
    # Карта документов кэшируется, потому что статьи часто переиспользуются:
    # в каталоге, на странице статьи, в карточках источников и при скачивании.
    documents: Dict[str, Dict] = OrderedDict()
    doc_index = _load_doc_index()

    with open(INPUT_CHUNKS_DEFAULT, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue

            row = json.loads(line)
            doc_id = row.get("doc_id", "").strip()
            title = row.get("title", "").strip()
            if not _public_doc_allowed(doc_id, title):
                continue

            doc = documents.setdefault(
                doc_id,
                {
                    "doc_id": doc_id,
                    "title": title,
                    "display_title": _display_title(title),
                    "breadcrumbs": row.get("breadcrumbs", []),
                    "normalized_file": row.get("normalized_file", "").strip(),
                    "source_file": row.get("source_file", "").strip(),
                    "author": "",
                    "date": "",
                    "original_url": "",
                    "chunks": [],
                },
            )
            extra = doc_index.get(doc_id, {})
            if extra:
                doc["author"] = extra.get("author", "").strip()
                doc["date"] = extra.get("date", "").strip()
                doc["original_url"] = extra.get("original_url", "").strip()

            doc["chunks"].append(row)

    for doc in documents.values():
        # Сначала сортируем чанки в естественном порядке документа,
        # а затем собираем две версии текста: полную и пользовательскую.
        doc["chunks"].sort(key=lambda chunk: (chunk.get("chunk_index", 0), chunk.get("chunk_part_in_section", 0)))
        doc["markdown_text"] = build_article_markdown(doc)
        doc["body_markdown_text"] = build_article_body_markdown(doc)
        doc["download_name"] = doc["normalized_file"] or f"{doc['doc_id']}.md"

    return documents


def get_documents_list(limit: int | None = None) -> List[Dict]:
    # Каталог статей сортируется по заголовку, чтобы пользователь видел
    # предсказуемый и стабильный список материалов.
    documents = list(get_documents_map().values())
    documents.sort(key=lambda item: item["title"].lower())
    if limit is None:
        return documents
    return documents[:limit]


def get_featured_documents(limit: int = 6) -> List[Dict]:
    # Главная страница не должна показывать первые алфавитные записи корпуса:
    # там часто встречаются служебные разделы и версии. Поэтому витрина
    # собирается из заранее выбранных прикладных материалов поддержки.
    documents_map = get_documents_map()
    featured = [documents_map[doc_id] for doc_id in FEATURED_DOC_IDS if doc_id in documents_map]
    if len(featured) >= limit:
        return featured[:limit]

    priority_words = (
        "принтер",
        "сеть",
        "dns",
        "пароль",
        "vpn",
        "rdp",
        "доступ",
        "учетн",
        "сертификат",
    )
    blocked_words = ("space details", "_topics", "без обновлений", ".net core", "2.12.", "1.7.")
    for document in documents_map.values():
        haystack = (document["title"] + " " + " > ".join(document.get("breadcrumbs", []))).lower()
        if document in featured:
            continue
        if any(word in haystack for word in blocked_words):
            continue
        if not any(word in haystack for word in priority_words):
            continue
        featured.append(document)
        if len(featured) >= limit:
            break
    return featured[:limit]


def get_document_or_404(doc_id: str) -> Dict:
    doc = get_documents_map().get(doc_id)
    if not doc:
        abort(404)
    return doc


def build_source_cards(results: List) -> List[Dict]:
    # Здесь из retrieval-результатов строятся карточки источников для выдачи.
    # На этом этапе намеренно скрываются технические поля, чтобы интерфейс
    # показывал только полезную пользователю информацию.
    documents = get_documents_map()
    cards: List[Dict] = []
    seen = set()

    for score, chunk in results:
        doc_id = chunk.get("doc_id", "").strip()
        if not doc_id or doc_id in seen:
            continue
        seen.add(doc_id)

        document = documents.get(doc_id, {})
        section = chunk.get("section_heading", "")
        section_label = _normalize_text(section).lstrip("#").strip()
        if not is_meaningful_section(section_label):
            section_label = ""

        cards.append(
            {
                "doc_id": doc_id,
                "title": document.get("title", chunk.get("title", "").strip()),
                "breadcrumbs": document.get("breadcrumbs", chunk.get("breadcrumbs", [])),
                "section": section_label,
                "excerpt": _build_source_excerpt(chunk.get("chunk_text", ""), section),
                "original_url": document.get("original_url", "").strip(),
                "download_name": document.get("download_name", f"{doc_id}.md"),
            }
        )

    return cards


def build_article_markdown(document: Dict) -> str:
    # Полный markdown статьи используется для скачивания и для внутренних задач.
    # Он собирается из чанков так, чтобы сохранить структуру исходного документа.
    lines: List[str] = [f"# {document['title']}"]
    if document.get("breadcrumbs"):
        lines.append("")
        lines.append("## Навигация")
        lines.append("")
        for crumb in document["breadcrumbs"]:
            lines.append(f"- {crumb}")

    current_section = None
    section_body = ""

    for chunk in document["chunks"]:
        section = _normalize_text(chunk.get("section_heading", ""))
        chunk_text = _strip_duplicate_heading(chunk.get("chunk_text", ""), section)

        if current_section is None:
            current_section = section
            section_body = chunk_text
            continue

        if section == current_section:
            section_body = _merge_with_overlap(section_body, chunk_text)
            continue

        if current_section:
            lines.extend(_render_section_block(current_section, section_body))
        current_section = section
        section_body = chunk_text

    if current_section:
        lines.extend(_render_section_block(current_section, section_body))

    return "\n".join(lines).strip() + "\n"


def build_article_body_markdown(document: Dict) -> str:
    # Для HTML-страницы статьи убираем дублирующий заголовок и блок навигации,
    # потому что эти данные уже показаны в пользовательской шапке страницы.
    markdown_text = build_article_markdown(document).strip()
    if not markdown_text:
        return ""

    title_line = f"# {document['title']}".strip()
    if markdown_text.startswith(title_line):
        markdown_text = markdown_text[len(title_line):].lstrip()

    navigation_heading = "## Навигация"
    if markdown_text.startswith(navigation_heading):
        lines = markdown_text.splitlines()
        next_heading_index = 0
        for index, line in enumerate(lines[1:], start=1):
            stripped = line.strip()
            if stripped.startswith("#") and stripped != navigation_heading:
                next_heading_index = index
                break

        if next_heading_index:
            markdown_text = "\n".join(lines[next_heading_index:]).lstrip()

    return markdown_text.strip()


def _render_section_block(section: str, text: str) -> List[str]:
    # Если секция не определена явно, подставляем нейтральный заголовок,
    # чтобы текст статьи не превращался в неструктурированный поток.
    block: List[str] = ["", section or "## Материал", ""]
    if text.strip():
        block.append(text.strip())
    return block


def normalized_markdown_path(document: Dict) -> Path:
    return NORMALIZED_DIR_DEFAULT / document.get("normalized_file", "")


def article_download_payload(document: Dict) -> bytes:
    # Приоритет отдается реальному markdown-файлу, если он существует на диске.
    # Если файла нет, пользователю все равно отдается собранная версия статьи.
    normalized_path = normalized_markdown_path(document)
    if normalized_path.exists():
        return normalized_path.read_bytes()
    return document["markdown_text"].encode("utf-8")


def build_content_disposition(download_name: str) -> str:
    # Заголовок формируется в двух вариантах: безопасный ASCII и UTF-8.
    # Это нужно, чтобы скачивание работало даже для имен файлов с кириллицей.
    filename = (download_name or "article.md").strip()
    if not filename.lower().endswith(".md"):
        filename = f"{filename}.md"

    ascii_name = unicodedata.normalize("NFKD", filename).encode("ascii", "ignore").decode("ascii")
    ascii_name = re.sub(r"[^A-Za-z0-9._-]+", "_", ascii_name).strip("._")
    if not ascii_name:
        ascii_name = "article.md"
    elif not ascii_name.lower().endswith(".md"):
        ascii_name = f"{ascii_name}.md"

    utf8_name = quote(filename, safe="")
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{utf8_name}"
