#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CLI-скрипт для ручной проверки retrieval-слоя.

Он позволяет без веб-приложения посмотреть, какие фрагменты корпуса находит
семантический поиск по вопросу пользователя. Скрипт удобен для отладки индекса
и для демонстрации работы retrieval как отдельного шага RAG-контура.
"""

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parent
# Добавляем корень проекта в sys.path, чтобы CLI-скрипт напрямую использовал
# тот же сервисный слой, что и веб-приложение.
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

from services.retrieval_service import (
    CHUNK_MAP_PATH_DEFAULT,
    INDEX_PATH_DEFAULT,
    MODEL_NAME_DEFAULT,
    TOP_K_DEFAULT,
    semantic_search,
)


def format_result(rank, score, chunk):
    # Форматированный вывод помогает увидеть не только текст,
    # но и техническую структуру найденного фрагмента.
    title = chunk.get("title", "")
    section = chunk.get("section_heading", "")
    breadcrumbs = " > ".join(chunk.get("breadcrumbs", []))
    source_file = chunk.get("source_file", "")
    chunk_id = chunk.get("chunk_id", "")
    text = chunk.get("chunk_text", "").strip()

    block = []
    block.append(f"[{rank}] score={score:.4f}")
    block.append(f"chunk_id: {chunk_id}")
    block.append(f"title: {title}")
    block.append(f"section: {section}")
    block.append(f"breadcrumbs: {breadcrumbs}")
    block.append(f"source_file: {source_file}")
    block.append("text:")
    block.append(text)
    block.append("-" * 80)
    return "\n".join(block)


def main():
    # Скрипт принимает минимальный набор параметров поиска и печатает
    # top-k результатов в текстовом виде для ручного анализа.
    parser = argparse.ArgumentParser(description="Semantic search over Astra Linux chunk index")
    parser.add_argument("--query", required=True, help="Вопрос пользователя")
    parser.add_argument("--top-k", type=int, default=TOP_K_DEFAULT)
    parser.add_argument("--index-path", default=INDEX_PATH_DEFAULT)
    parser.add_argument("--chunk-map-path", default=CHUNK_MAP_PATH_DEFAULT)
    parser.add_argument("--model-name", default=MODEL_NAME_DEFAULT)
    args = parser.parse_args()

    query_text = args.query.strip()
    if not query_text:
        raise ValueError("Пустой запрос")

    print("Поиск релевантных фрагментов...")
    results = semantic_search(
        query=query_text,
        top_k=args.top_k,
        index_path=args.index_path,
        chunk_map_path=args.chunk_map_path,
        model_name=args.model_name,
    )

    print("\nРезультаты поиска\n")
    print(f"query: {query_text}")
    print("=" * 80)

    for rank, (score, chunk) in enumerate(results, start=1):
        print(format_result(rank, float(score), chunk))


if __name__ == "__main__":
    main()
