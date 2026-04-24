#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт разбиения markdown-корпуса на чанки для retrieval и индексации.

После нормализации HTML-документов проект получает длинные markdown-статьи.
Этот скрипт превращает их в фрагменты подходящего размера, сохраняя связь
с doc_id, breadcrumbs и секциями. Именно эти чанки затем индексируются
и используются как контекст для генерации ответа.
"""

import os
import re
import csv
import json
import argparse


INPUT_MD_DIR_DEFAULT = "/volume1/MUIV_Diplom/05_sources/03_normalized/astra_linux_wiki/articles_md"
OUTPUT_JSONL_DEFAULT = "/volume1/MUIV_Diplom/05_sources/04_prepared/chunks/astra_linux_wiki_chunks.jsonl"
OUTPUT_CSV_DEFAULT = "/volume1/MUIV_Diplom/05_sources/04_prepared/chunks/astra_linux_wiki_chunks.csv"
OUTPUT_STATS_DEFAULT = "/volume1/MUIV_Diplom/05_sources/04_prepared/chunks/astra_linux_wiki_chunks_stats.txt"

TARGET_CHARS_DEFAULT = 1800
OVERLAP_CHARS_DEFAULT = 250
MIN_CHARS_DEFAULT = 350
MERGE_SMALLER_THAN_DEFAULT = 900


def safe_text(value):
    # Единая очистка текста нужна, чтобы все дальнейшие операции
    # работали уже с нормализованным markdown без лишнего "шума".
    if value is None:
        return ""
    value = value.replace("\r", "")
    value = re.sub(r"[ \t]+\n", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def strip_yaml_quotes(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        value = value[1:-1]
    value = value.replace('\\"', '"').replace("\\\\", "\\")
    return value


def parse_front_matter(md_text):
    # Из markdown-документа отделяем front matter и тело статьи.
    # Метаданные понадобятся для связи чанка с исходным документом.
    md_text = md_text.replace("\r", "")
    if not md_text.startswith("---\n"):
        return {}, md_text

    end_idx = md_text.find("\n---\n", 4)
    if end_idx == -1:
        return {}, md_text

    fm_text = md_text[4:end_idx]
    body = md_text[end_idx + 5:]

    meta = {}
    lines = fm_text.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue

        if re.match(r"^[A-Za-z0-9_]+:\s*$", line):
            key = line.split(":", 1)[0].strip()
            items = []
            i += 1
            while i < len(lines):
                item_line = lines[i]
                if re.match(r"^\s+-\s+", item_line):
                    value = re.sub(r"^\s+-\s+", "", item_line).strip()
                    value = strip_yaml_quotes(value)
                    items.append(value)
                    i += 1
                else:
                    break
            meta[key] = items
            continue

        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = strip_yaml_quotes(value.strip())

        i += 1

    return meta, body


def normalize_compare_text(text):
    # Нормализованное сравнение помогает безопасно сопоставлять
    # breadcrumb-строки и повторяющийся текст независимо от форматирования.
    text = safe_text(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def remove_leading_breadcrumb_lines(lines, breadcrumbs):
    # В некоторых документах breadcrumbs дублируются в начале раздела списком.
    # Для чанка это бесполезный шум, поэтому стараемся его убрать.
    normalized_breadcrumbs = {normalize_compare_text(x) for x in breadcrumbs if safe_text(x)}
    out = list(lines)

    while out:
        line = out[0].strip()
        m = re.match(r"^-\s+(.*)$", line)
        if not m:
            break
        candidate = normalize_compare_text(m.group(1))
        if candidate in normalized_breadcrumbs:
            out.pop(0)
        else:
            break

    return out


def split_into_sections(md_body):
    # Сначала разбиваем документ на смысловые секции по markdown-заголовкам.
    # Это помогает позже не резать текст полностью "вслепую".
    md_body = safe_text(md_body)
    lines = md_body.splitlines()

    sections = []
    current_heading = ""
    current_lines = []

    for line in lines:
        if re.match(r"^#{1,6}\s+", line):
            if current_lines:
                section_text = safe_text("\n".join(current_lines))
                if section_text:
                    sections.append({
                        "heading": current_heading,
                        "text": section_text
                    })
            current_heading = line.strip()
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        section_text = safe_text("\n".join(current_lines))
        if section_text:
            sections.append({
                "heading": current_heading,
                "text": section_text
            })

    return sections


def clean_section_text(heading, text, title, breadcrumbs):
    # На этом этапе удаляем заведомо бесполезные или дублирующиеся части:
    # служебные списки, повтор заголовка статьи и повтор breadcrumbs.
    text = safe_text(text)
    if not text:
        return ""

    lines = text.splitlines()
    heading_line = lines[0].strip() if lines else ""
    body_lines = lines[1:] if lines and heading_line == heading else lines

    if heading in {"## Связанные вложения", "## Связанные изображения"}:
        return ""

    if heading == f"# {safe_text(title)}":
        # Не выбрасываем всю секцию целиком.
        # Убираем только строку заголовка и оставляем тело статьи.
        cleaned = safe_text("\n".join(body_lines))
        return cleaned

    if heading == "## Раздел":
        # Убираем heading и повторяющиеся breadcrumb-строки,
        # но оставляем возможный полезный текст внутри секции.
        body_lines = remove_leading_breadcrumb_lines(body_lines, breadcrumbs)
        cleaned = safe_text("\n".join(body_lines))
        return cleaned

    return text

def hard_split(text, target_chars, overlap_chars):
    # Жесткое разбиение используется как запасной вариант,
    # когда текст слишком длинный и его нельзя аккуратно поделить по абзацам.
    text = safe_text(text)
    if len(text) <= target_chars:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = min(len(text), start + target_chars)

        if end < len(text):
            boundary = text.rfind(" ", start, end)
            if boundary > start + int(target_chars * 0.6):
                end = boundary

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        start = max(0, end - overlap_chars)

    return chunks


def split_long_text(text, target_chars, overlap_chars):
    # Основное разбиение старается учитывать абзацы и сохранять overlap,
    # чтобы retrieval не терял связность соседних фрагментов.
    text = safe_text(text)
    if not text:
        return []

    if len(text) <= target_chars:
        return [text]

    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]

    # Если документ фактически состоит из одного большого абзаца,
    # режем его сразу hard_split, иначе он останется одним огромным чанком.
    if len(paragraphs) <= 1:
        return [safe_text(x) for x in hard_split(text, target_chars, overlap_chars) if safe_text(x)]

    chunks = []
    current = ""

    for p in paragraphs:
        if not current:
            current = p
            continue

        candidate = current + "\n\n" + p
        if len(candidate) <= target_chars:
            current = candidate
        else:
            # Перед сохранением проверяем, не слишком ли большой current
            if len(current) > target_chars:
                chunks.extend(hard_split(current, target_chars, overlap_chars))
            else:
                chunks.append(current)

            overlap = current[-overlap_chars:] if overlap_chars > 0 else ""
            current = safe_text(overlap + "\n\n" + p)

            if len(current) > target_chars * 1.2:
                hard_parts = hard_split(current, target_chars, overlap_chars)
                chunks.extend(hard_parts[:-1])
                current = hard_parts[-1]

    if current:
        if len(current) > target_chars:
            chunks.extend(hard_split(current, target_chars, overlap_chars))
        else:
            chunks.append(current)

    return [safe_text(x) for x in chunks if safe_text(x)]


def merge_small_chunks(chunks, merge_smaller_than):
    # Слишком маленькие чанки обычно малоинформативны для retrieval,
    # поэтому их объединяем с соседними фрагментами.
    if not chunks:
        return []

    merged = []
    carry_prefix = None

    for chunk in chunks:
        current_text = chunk["chunk_text"]

        if carry_prefix:
            current_text = safe_text(carry_prefix + "\n\n" + current_text)
            chunk["chunk_text"] = current_text
            chunk["char_count"] = len(current_text)
            chunk["word_count"] = len(current_text.split())
            carry_prefix = None

        if chunk["char_count"] < merge_smaller_than:
            if merged:
                merged[-1]["chunk_text"] = safe_text(merged[-1]["chunk_text"] + "\n\n" + chunk["chunk_text"])
                merged[-1]["char_count"] = len(merged[-1]["chunk_text"])
                merged[-1]["word_count"] = len(merged[-1]["chunk_text"].split())
            else:
                carry_prefix = chunk["chunk_text"]
        else:
            merged.append(chunk)

    if carry_prefix:
        if merged:
            merged[-1]["chunk_text"] = safe_text(merged[-1]["chunk_text"] + "\n\n" + carry_prefix)
            merged[-1]["char_count"] = len(merged[-1]["chunk_text"])
            merged[-1]["word_count"] = len(merged[-1]["chunk_text"].split())
        else:
            only_chunk = {
                "chunk_id": "",
                "doc_id": chunks[0]["doc_id"],
                "title": chunks[0]["title"],
                "breadcrumbs": chunks[0]["breadcrumbs"],
                "section_heading": chunks[0]["section_heading"],
                "source_file": chunks[0]["source_file"],
                "normalized_file": chunks[0]["normalized_file"],
                "chunk_index": 1,
                "chunk_part_in_section": 1,
                "chunk_text": carry_prefix,
                "char_count": len(carry_prefix),
                "word_count": len(carry_prefix.split()),
            }
            merged.append(only_chunk)

    for idx, chunk in enumerate(merged, start=1):
        chunk["chunk_index"] = idx
        chunk["chunk_id"] = f'{chunk["doc_id"]}__chunk_{idx:04d}'

    return merged


def build_chunks_for_doc(doc_meta, md_body, target_chars, overlap_chars, min_chars, merge_smaller_than):
    # Функция собирает весь набор чанков для одного документа,
    # сохраняя метаданные статьи в каждом фрагменте.
    title = doc_meta.get("title", "")
    breadcrumbs = doc_meta.get("breadcrumbs", [])
    if not isinstance(breadcrumbs, list):
        breadcrumbs = [breadcrumbs] if breadcrumbs else []

    doc_id = doc_meta.get("doc_id", "")
    source_file = doc_meta.get("source_file", "")
    normalized_file = doc_meta.get("normalized_file", "")

    sections = split_into_sections(md_body)

    all_chunks = []
    chunk_no = 1

    for sec in sections:
        sec_heading = sec["heading"]
        sec_text = clean_section_text(sec_heading, sec["text"], title, breadcrumbs)

        if not sec_text:
            continue

        parts = split_long_text(sec_text, target_chars, overlap_chars)

        for part_idx, part in enumerate(parts, start=1):
            clean_part = safe_text(part)
            if not clean_part:
                continue

            if len(clean_part) < min_chars and all_chunks:
                all_chunks[-1]["chunk_text"] = safe_text(all_chunks[-1]["chunk_text"] + "\n\n" + clean_part)
                all_chunks[-1]["char_count"] = len(all_chunks[-1]["chunk_text"])
                all_chunks[-1]["word_count"] = len(all_chunks[-1]["chunk_text"].split())
                continue

            chunk = {
                "chunk_id": f"{doc_id}__chunk_{chunk_no:04d}",
                "doc_id": doc_id,
                "title": title,
                "breadcrumbs": breadcrumbs,
                "section_heading": sec_heading,
                "source_file": source_file,
                "normalized_file": normalized_file,
                "chunk_index": chunk_no,
                "chunk_part_in_section": part_idx,
                "chunk_text": clean_part,
                "char_count": len(clean_part),
                "word_count": len(clean_part.split()),
            }
            all_chunks.append(chunk)
            chunk_no += 1

    all_chunks = merge_small_chunks(all_chunks, merge_smaller_than)
    return all_chunks


def find_md_files(input_dir):
    result = []
    for root, _, files in os.walk(input_dir):
        for name in files:
            if name.lower().endswith(".md"):
                result.append(os.path.join(root, name))
    result.sort()
    return result


def ensure_parent(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)


def main():
    parser = argparse.ArgumentParser(description="Chunking markdown corpus for RAG")
    parser.add_argument("--input-dir", default=INPUT_MD_DIR_DEFAULT)
    parser.add_argument("--output-jsonl", default=OUTPUT_JSONL_DEFAULT)
    parser.add_argument("--output-csv", default=OUTPUT_CSV_DEFAULT)
    parser.add_argument("--output-stats", default=OUTPUT_STATS_DEFAULT)
    parser.add_argument("--target-chars", type=int, default=TARGET_CHARS_DEFAULT)
    parser.add_argument("--overlap-chars", type=int, default=OVERLAP_CHARS_DEFAULT)
    parser.add_argument("--min-chars", type=int, default=MIN_CHARS_DEFAULT)
    parser.add_argument("--merge-smaller-than", type=int, default=MERGE_SMALLER_THAN_DEFAULT)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    input_dir = os.path.abspath(args.input_dir)
    output_jsonl = os.path.abspath(args.output_jsonl)
    output_csv = os.path.abspath(args.output_csv)
    output_stats = os.path.abspath(args.output_stats)

    ensure_parent(output_jsonl)
    ensure_parent(output_csv)
    ensure_parent(output_stats)

    md_files = find_md_files(input_dir)
    if args.limit and args.limit > 0:
        md_files = md_files[:args.limit]

    total_docs = len(md_files)
    total_chunks = 0
    total_errors = 0
    total_chars = 0

    print(f"Найдено markdown-документов: {total_docs}")

    with open(output_jsonl, "w", encoding="utf-8") as jsonl_f, \
         open(output_csv, "w", encoding="utf-8", newline="") as csv_f:

        csv_writer = csv.writer(csv_f)
        csv_writer.writerow([
            "chunk_id",
            "doc_id",
            "title",
            "breadcrumbs",
            "section_heading",
            "source_file",
            "normalized_file",
            "chunk_index",
            "chunk_part_in_section",
            "char_count",
            "word_count",
            "chunk_text",
        ])

        for i, md_path in enumerate(md_files, start=1):
            try:
                with open(md_path, "r", encoding="utf-8") as f:
                    md_text = f.read()

                meta, body = parse_front_matter(md_text)
                meta["normalized_file"] = os.path.relpath(md_path, input_dir)

                chunks = build_chunks_for_doc(
                    doc_meta=meta,
                    md_body=body,
                    target_chars=args.target_chars,
                    overlap_chars=args.overlap_chars,
                    min_chars=args.min_chars,
                    merge_smaller_than=args.merge_smaller_than,
                )

                for chunk in chunks:
                    jsonl_f.write(json.dumps(chunk, ensure_ascii=False) + "\n")
                    csv_writer.writerow([
                        chunk["chunk_id"],
                        chunk["doc_id"],
                        chunk["title"],
                        " > ".join(chunk["breadcrumbs"]),
                        chunk["section_heading"],
                        chunk["source_file"],
                        chunk["normalized_file"],
                        chunk["chunk_index"],
                        chunk["chunk_part_in_section"],
                        chunk["char_count"],
                        chunk["word_count"],
                        chunk["chunk_text"],
                    ])
                    total_chunks += 1
                    total_chars += chunk["char_count"]

                if i % 500 == 0 or i == total_docs:
                    print(f"[{i}/{total_docs}] chunks={total_chunks} errors={total_errors}")

            except Exception as e:
                total_errors += 1
                print(f"[ERROR] {md_path}: {e}")

    avg_chars = round(total_chars / total_chunks, 2) if total_chunks else 0

    with open(output_stats, "w", encoding="utf-8") as f:
        f.write("Статистика чанкинга\n")
        f.write(f"Документов: {total_docs}\n")
        f.write(f"Чанков: {total_chunks}\n")
        f.write(f"Ошибок: {total_errors}\n")
        f.write(f"Средний размер чанка, символов: {avg_chars}\n")
        f.write(f"Target chars: {args.target_chars}\n")
        f.write(f"Overlap chars: {args.overlap_chars}\n")
        f.write(f"Min chars: {args.min_chars}\n")
        f.write(f"Merge smaller than: {args.merge_smaller_than}\n")

    print("Готово.")
    print(f"JSONL: {output_jsonl}")
    print(f"CSV: {output_csv}")
    print(f"Stats: {output_stats}")


if __name__ == "__main__":
    main()
