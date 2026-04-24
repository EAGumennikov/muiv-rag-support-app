#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт нормализации HTML-корпуса базы знаний в markdown-формат.

Он является самым ранним этапом подготовки корпуса для RAG: из исходных
HTML-страниц извлекаются заголовки, breadcrumbs, ссылки, автор, дата,
вложения и основной текст. Результатом становится набор markdown-документов
и индекс метаданных, которые затем используются при чанкинге и индексации.
"""

import os
import re
import csv
import html
import argparse
from html.parser import HTMLParser
from urllib.parse import unquote


INPUT_ROOT_DEFAULT = "/volume1/MUIV_Diplom/05_sources/02_unpacked/pubkb"
OUTPUT_MD_DIR_DEFAULT = "/volume1/MUIV_Diplom/05_sources/03_normalized/astra_linux_wiki/articles_md"
INDEX_CSV_DEFAULT = "/volume1/MUIV_Diplom/05_sources/04_prepared/source_index/astra_linux_wiki_source_index.csv"
LOG_CSV_DEFAULT = "/volume1/MUIV_Diplom/05_sources/04_prepared/logs/astra_linux_wiki_normalize_log.csv"

SKIP_DIRS = {"attachments", "images", "styles", "@eaDir"}
IMG_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg"}
NON_ATTACHMENT_EXTS = {".html", ".htm", ".css", ".js", ".map", ".json", ""}


def safe_text(value):
    # Базовая очистка текста нужна почти на всех этапах:
    # убираем лишние пробелы, HTML entities и пустые строки.
    if value is None:
        return ""
    value = html.unescape(value)
    value = value.replace("\r", "")
    value = re.sub(r"\s+\n", "\n", value)
    value = re.sub(r"[ \t]{2,}", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def strip_tags(raw):
    # Для извлечения "чистого" текста убираем не только теги,
    # но и содержимое script/style, которое не несет ценности для корпуса.
    raw = re.sub(r"<script\b.*?</script>", " ", raw, flags=re.I | re.S)
    raw = re.sub(r"<style\b.*?</style>", " ", raw, flags=re.I | re.S)
    raw = re.sub(r"<[^>]+>", " ", raw, flags=re.S)
    return safe_text(raw)


def read_file_with_fallback(path):
    # Корпус может содержать файлы в разных кодировках,
    # поэтому читаем их с несколькими вариантами fallback.
    encodings = ["utf-8", "utf-8-sig", "cp1251", "latin-1"]
    for enc in encodings:
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read(), enc
        except Exception:
            pass

    with open(path, "rb") as f:
        raw = f.read()
    return raw.decode("utf-8", errors="replace"), "utf-8-replace"


def sanitize_filename(text, max_len=90):
    # Имя markdown-файла должно быть безопасным для файловой системы,
    # но при этом оставаться узнаваемым для человека.
    text = safe_text(text)
    text = text.replace("/", "_").replace("\\", "_").replace(":", "_")
    text = text.replace("*", "_").replace("?", "_").replace('"', "_")
    text = text.replace("<", "_").replace(">", "_").replace("|", "_")
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"_+", "_", text)
    text = text.strip("._ ")
    if not text:
        text = "untitled"
    return text[:max_len]


def yaml_quote(value):
    value = "" if value is None else str(value)
    value = value.replace("\\", "\\\\").replace('"', '\\"')
    return f"\"{value}\""


def relpath_safe(path, start):
    try:
        return os.path.relpath(path, start)
    except Exception:
        return path


def resolve_local_ref(base_dir, ref, input_root):
    # Внутренние ссылки в HTML приводим к относительному виду,
    # чтобы потом можно было различать изображения, вложения и прочие ресурсы.
    if not ref:
        return ""

    ref = ref.strip()
    if ref.startswith(("http://", "https://", "mailto:", "javascript:", "#")):
        return ref

    ref = ref.split("#")[0].split("?")[0].strip()
    ref = unquote(ref)

    if not ref:
        return ""

    joined = os.path.normpath(os.path.join(base_dir, ref))
    if os.path.exists(joined):
        return relpath_safe(joined, input_root)

    return ref


def classify_ref(ref):
    # Классификация ссылок нужна для раздельного учета изображений и вложений
    # в итоговых метаданных документа.
    low = ref.lower()

    if low.startswith(("http://", "https://", "mailto:", "javascript:")):
        return "other"

    ext = os.path.splitext(low)[1]

    if "/images/" in low or low.startswith("images/") or ext in IMG_EXTS:
        return "image"

    if "/attachments/" in low or low.startswith("attachments/"):
        return "attachment"

    if ext not in NON_ATTACHMENT_EXTS:
        return "attachment"

    return "other"


def extract_title(raw_html):
    # Заголовок статьи сначала ищем в h1, а если его нет — в title.
    # Такой порядок ближе к фактическому пользовательскому представлению страницы.
    m = re.search(r"<h1\b[^>]*>(.*?)</h1>", raw_html, flags=re.I | re.S)
    if m:
        title = strip_tags(m.group(1))
        if title:
            return title

    m = re.search(r"<title\b[^>]*>(.*?)</title>", raw_html, flags=re.I | re.S)
    if m:
        title = strip_tags(m.group(1))
        if title:
            return title

    return ""


def extract_breadcrumbs(raw_html):
    # Хлебные крошки извлекаются из ссылок до первого h1 —
    # это помогает восстановить место статьи в иерархии базы знаний.
    h1_match = re.search(r"<h1\b[^>]*>", raw_html, flags=re.I | re.S)
    search_part = raw_html[:h1_match.start()] if h1_match else raw_html[:50000]

    links = re.findall(r"<a\b[^>]*>(.*?)</a>", search_part, flags=re.I | re.S)

    cleaned = []
    seen = set()

    for item in links:
        txt = strip_tags(item).strip()
        if not txt:
            continue
        if len(txt) > 120:
            continue
        if txt.lower() in {"начальная страница", "home"}:
            continue
        if txt not in seen:
            cleaned.append(txt)
            seen.add(txt)

    if len(cleaned) > 8:
        cleaned = cleaned[-8:]

    return cleaned


def extract_author_and_date(raw_html):
    # Автор и дата могут встречаться в разных текстовых шаблонах,
    # поэтому функция проверяет несколько типовых паттернов.
    page_text = strip_tags(raw_html[:50000])

    author = ""
    date = ""

    patterns = [
        r"Created by\s+(.+?)\s+on\s+(\d{2}\.\d{2}\.\d{2,4})",
        r"Создано\s+(.+?)\s+(\d{2}\.\d{2}\.\d{2,4})",
        r"Автор\s*[:\-]\s*(.+?)\s+(\d{2}\.\d{2}\.\d{2,4})",
    ]

    for p in patterns:
        m = re.search(p, page_text, flags=re.I)
        if m:
            author = safe_text(m.group(1))
            date = safe_text(m.group(2))
            break

    if not date:
        m = re.search(r"\b(\d{2}\.\d{2}\.\d{2,4})\b", page_text)
        if m:
            date = m.group(1)

    return author, date


def extract_original_url(raw_html):
    # canonical/og:url сохраняем отдельно, чтобы в веб-интерфейсе
    # можно было показать ссылку на исходную страницу.
    patterns = [
        r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\'](.*?)["\']',
        r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\'](.*?)["\']',
        r'<meta[^>]+name=["\']url["\'][^>]+content=["\'](.*?)["\']',
    ]
    for p in patterns:
        m = re.search(p, raw_html, flags=re.I | re.S)
        if m:
            return safe_text(m.group(1))
    return ""


def remove_simple_toc(markdown_body):
    # Некоторые статьи содержат короткое оглавление "Окружение / Вопрос / Ответ".
    # Его стараемся убрать, чтобы в markdown не было лишнего дубля структуры.
    lines = markdown_body.splitlines()
    cleaned_lines = []
    toc_buffer = []

    for line in lines:
        if re.match(r"^\s*-\s*(Окружение|Вопрос|Ответ)\s*$", line):
            toc_buffer.append(line)
            continue

        if toc_buffer and re.match(r"^\s*##\s+(Окружение|Вопрос|Ответ)\s*$", line):
            toc_buffer = []

        elif toc_buffer:
            cleaned_lines.extend(toc_buffer)
            toc_buffer = []

        cleaned_lines.append(line)

    if toc_buffer:
        cleaned_lines.extend(toc_buffer)

    return "\n".join(cleaned_lines).strip()


class MarkdownExtractor(HTMLParser):
    # HTMLParser используется как простой и управляемый способ
    # последовательно перевести HTML-структуру в markdown-текст.
    def __init__(self, input_root, current_dir):
        super().__init__(convert_charrefs=True)
        self.input_root = input_root
        self.current_dir = current_dir
        self.out = []
        self.ignore_depth = 0
        self.in_pre = False
        self.images = []
        self.attachments = []
        self._seen_images = set()
        self._seen_attachments = set()

    def append(self, text):
        if text:
            self.out.append(text)

    def newline(self, n=1):
        self.out.append("\n" * n)

    def handle_starttag(self, tag, attrs):
        # Здесь закладываются правила перевода HTML-тегов в markdown:
        # заголовки, абзацы, списки, ссылки, изображения и кодовые блоки.
        attrs = dict(attrs)

        if tag in {"script", "style", "noscript", "svg"}:
            self.ignore_depth += 1
            return

        if self.ignore_depth:
            return

        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            level = int(tag[1])
            self.newline(2)
            self.append("#" * level + " ")
            return

        if tag in {"p", "section", "article"}:
            self.newline(2)
            return

        if tag == "div":
            self.newline(1)
            return

        if tag == "br":
            self.newline(1)
            return

        if tag in {"ul", "ol"}:
            self.newline(1)
            return

        if tag == "li":
            self.newline(1)
            self.append("- ")
            return

        if tag == "pre":
            self.newline(2)
            self.append("```text\n")
            self.in_pre = True
            return

        if tag == "code" and not self.in_pre:
            self.append("`")
            return

        if tag == "table":
            self.newline(2)
            return

        if tag == "tr":
            self.newline(1)
            return

        if tag in {"td", "th"}:
            self.append(" | ")
            return

        if tag == "a":
            href = attrs.get("href", "").strip()
            resolved = resolve_local_ref(self.current_dir, href, self.input_root)
            kind = classify_ref(resolved)

            if kind == "image":
                if resolved and resolved not in self._seen_images:
                    self.images.append(resolved)
                    self._seen_images.add(resolved)

            elif kind == "attachment":
                if resolved and resolved not in self._seen_attachments:
                    self.attachments.append(resolved)
                    self._seen_attachments.add(resolved)
            return

        if tag == "img":
            src = attrs.get("src", "").strip()
            resolved = resolve_local_ref(self.current_dir, src, self.input_root)
            kind = classify_ref(resolved)

            if kind == "image":
                if resolved and resolved not in self._seen_images:
                    self.images.append(resolved)
                    self._seen_images.add(resolved)
            return

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg"}:
            if self.ignore_depth:
                self.ignore_depth -= 1
            return

        if self.ignore_depth:
            return

        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.newline(2)
            return

        if tag in {"p", "section", "article", "div"}:
            self.newline(1)
            return

        if tag == "pre":
            self.append("\n```")
            self.newline(2)
            self.in_pre = False
            return

        if tag == "code" and not self.in_pre:
            self.append("`")
            return

    def handle_data(self, data):
        if self.ignore_depth:
            return

        if not data:
            return

        if self.in_pre:
            self.append(data)
            return

        text = safe_text(data)
        if text:
            self.append(text + " ")

    def get_markdown(self):
        text = "".join(self.out)
        text = text.replace("\r", "")
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n[ \t]+", "\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" +([,.;:!?])", r"\1", text)
        return text.strip()


def build_front_matter(meta):
    lines = ["---"]

    simple_fields = [
        "doc_id",
        "title",
        "source_file",
        "source_encoding",
        "source_type",
        "original_url",
        "author",
        "date",
    ]

    for field in simple_fields:
        lines.append(f"{field}: {yaml_quote(meta.get(field, ''))}")

    for field in ["breadcrumbs", "images", "attachments"]:
        lines.append(f"{field}:")
        for item in meta.get(field, []):
            lines.append(f"  - {yaml_quote(item)}")

    lines.append("---")
    return "\n".join(lines)


def find_html_files(input_root):
    result = []
    for root, dirs, files in os.walk(input_root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if name.lower().endswith(".html"):
                result.append(os.path.join(root, name))
    result.sort()
    return result


def convert_one(path, input_root):
    raw_html, used_encoding = read_file_with_fallback(path)
    current_dir = os.path.dirname(path)
    source_rel = relpath_safe(path, input_root)

    title = extract_title(raw_html)
    breadcrumbs = extract_breadcrumbs(raw_html)
    author, date = extract_author_and_date(raw_html)
    original_url = extract_original_url(raw_html)

    first_h1 = re.search(r"<h1\b[^>]*>.*?</h1>", raw_html, flags=re.I | re.S)
    parse_html = raw_html[first_h1.end():] if first_h1 else raw_html

    parser = MarkdownExtractor(input_root=input_root, current_dir=current_dir)
    parser.feed(parse_html)
    markdown_body = parser.get_markdown()

    markdown_body = re.sub(
        r"^Created by .*? on \d{2}\.\d{2}\.\d{2,4}\s*$",
        "",
        markdown_body,
        flags=re.I | re.M
    )

    markdown_body = re.sub(
        r"^Создано .*?\d{2}\.\d{2}\.\d{2,4}\s*$",
        "",
        markdown_body,
        flags=re.I | re.M
    )

    markdown_body = re.sub(
        r"^Document generated by Confluence on .*?$",
        "",
        markdown_body,
        flags=re.I | re.M
    )

    markdown_body = re.sub(
        r"^Atlassian\s*$",
        "",
        markdown_body,
        flags=re.I | re.M
    )

    markdown_body = re.sub(r"\n{3,}", "\n\n", markdown_body).strip()
    markdown_body = remove_simple_toc(markdown_body)

    parser.images = [
        x for x in parser.images
        if "plugins/servlet/confluence/placeholder/unknown-macro" not in x.lower()
    ]

    if not title:
        title = os.path.splitext(os.path.basename(path))[0]

    if not markdown_body:
        raise ValueError("Не удалось извлечь текст статьи")

    doc_id = os.path.splitext(os.path.basename(path))[0]
    safe_title = sanitize_filename(title)
    output_name = f"{doc_id}__{safe_title}.md"

    meta = {
        "doc_id": doc_id,
        "title": title,
        "source_file": source_rel,
        "source_encoding": used_encoding,
        "source_type": "astra_kb_html",
        "original_url": original_url,
        "author": author,
        "date": date,
        "breadcrumbs": breadcrumbs,
        "images": parser.images,
        "attachments": parser.attachments,
    }

    front_matter = build_front_matter(meta)

    parts = [front_matter, "", f"# {title}", ""]

    if breadcrumbs:
        parts.append("## Раздел")
        parts.extend([f"- {x}" for x in breadcrumbs])
        parts.append("")

    parts.append(markdown_body)
    parts.append("")

    if parser.attachments:
        parts.append("## Связанные вложения")
        parts.extend([f"- `{x}`" for x in parser.attachments])
        parts.append("")

    if parser.images:
        parts.append("## Связанные изображения")
        parts.extend([f"- `{x}`" for x in parser.images])
        parts.append("")

    final_md = "\n".join(parts).strip() + "\n"

    return meta, output_name, final_md


def ensure_parent(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)


def main():
    parser = argparse.ArgumentParser(description="Нормализация HTML -> Markdown для базы знаний Astra Linux")
    parser.add_argument("--input-root", default=INPUT_ROOT_DEFAULT)
    parser.add_argument("--output-dir", default=OUTPUT_MD_DIR_DEFAULT)
    parser.add_argument("--index-csv", default=INDEX_CSV_DEFAULT)
    parser.add_argument("--log-csv", default=LOG_CSV_DEFAULT)
    parser.add_argument("--limit", type=int, default=0, help="Ограничить количество файлов для теста")
    parser.add_argument("--overwrite", action="store_true", help="Перезаписывать существующие md-файлы")
    args = parser.parse_args()

    input_root = os.path.abspath(args.input_root)
    output_dir = os.path.abspath(args.output_dir)
    index_csv = os.path.abspath(args.index_csv)
    log_csv = os.path.abspath(args.log_csv)

    os.makedirs(output_dir, exist_ok=True)
    ensure_parent(index_csv)
    ensure_parent(log_csv)

    html_files = find_html_files(input_root)

    if args.limit and args.limit > 0:
        html_files = html_files[:args.limit]

    total = len(html_files)
    print(f"Найдено HTML-файлов к обработке: {total}")

    with open(index_csv, "w", encoding="utf-8", newline="") as idx_f, \
         open(log_csv, "w", encoding="utf-8", newline="") as log_f:

        idx_writer = csv.writer(idx_f)
        log_writer = csv.writer(log_f)

        idx_writer.writerow([
            "doc_id",
            "title",
            "source_file",
            "normalized_file",
            "author",
            "date",
            "breadcrumbs",
            "images_count",
            "attachments_count",
            "original_url",
        ])

        log_writer.writerow([
            "source_file",
            "status",
            "message",
        ])

        ok_count = 0
        skip_count = 0
        err_count = 0

        for i, path in enumerate(html_files, start=1):
            source_rel = relpath_safe(path, input_root)
            try:
                meta, output_name, final_md = convert_one(path, input_root)
                output_path = os.path.join(output_dir, output_name)

                if os.path.exists(output_path) and not args.overwrite:
                    skip_count += 1
                    log_writer.writerow([source_rel, "skipped", "md уже существует"])
                else:
                    with open(output_path, "w", encoding="utf-8") as f:
                        f.write(final_md)
                    ok_count += 1
                    log_writer.writerow([source_rel, "ok", ""])

                idx_writer.writerow([
                    meta["doc_id"],
                    meta["title"],
                    meta["source_file"],
                    relpath_safe(output_path, output_dir),
                    meta["author"],
                    meta["date"],
                    " > ".join(meta["breadcrumbs"]),
                    len(meta["images"]),
                    len(meta["attachments"]),
                    meta["original_url"],
                ])

                if i % 100 == 0 or i == total:
                    print(f"[{i}/{total}] ok={ok_count} skipped={skip_count} errors={err_count}")

            except Exception as e:
                err_count += 1
                log_writer.writerow([source_rel, "error", str(e)])
                if i % 50 == 0 or i == total:
                    print(f"[{i}/{total}] ok={ok_count} skipped={skip_count} errors={err_count}")

    print("Готово.")
    print(f"Индекс: {index_csv}")
    print(f"Лог: {log_csv}")
    print(f"Markdown: {output_dir}")


if __name__ == "__main__":
    main()
