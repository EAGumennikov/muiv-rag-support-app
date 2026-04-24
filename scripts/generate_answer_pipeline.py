#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from providers.yandex_llm import generate_answer

import os
import json
import argparse
from typing import List, Dict, Tuple

import numpy as np
import faiss
from sentence_transformers import SentenceTransformer


INDEX_PATH_DEFAULT = os.path.expanduser(
    "~/Projects/MUIV_Diplom_local/output/indexes/astra_linux_wiki_faiss.index"
)
CHUNK_MAP_PATH_DEFAULT = os.path.expanduser(
    "~/Projects/MUIV_Diplom_local/output/indexes/astra_linux_wiki_chunk_map.jsonl"
)
MODEL_NAME_DEFAULT = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
TOP_K_DEFAULT = 3
MAX_CONTEXT_CHARS_DEFAULT = 3500
MODE_DEFAULT = "prompt-only"


def load_chunk_map(path: str) -> List[Dict]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception as e:
                raise ValueError(f"Ошибка чтения chunk_map на строке {line_no}: {e}")
    return rows


def semantic_search(
    *,
    query: str,
    top_k: int,
    index_path: str,
    chunk_map_path: str,
    model_name: str,
) -> List[Tuple[float, Dict]]:
    chunks = load_chunk_map(chunk_map_path)
    index = faiss.read_index(index_path)
    model = SentenceTransformer(model_name)

    query_embedding = model.encode(
        [query],
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    query_embedding = np.asarray(query_embedding, dtype=np.float32)

    scores, indices = index.search(query_embedding, top_k)

    results: List[Tuple[float, Dict]] = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0 or idx >= len(chunks):
            continue
        results.append((float(score), chunks[idx]))
    return results


def human_section(section_heading: str) -> str:
    if not section_heading:
        return ""
    return section_heading.lstrip("#").strip()


def format_source_label(chunk: Dict) -> str:
    title = chunk.get("title", "").strip()
    breadcrumbs = " > ".join(chunk.get("breadcrumbs", []))
    section = human_section(chunk.get("section_heading", ""))

    parts = []
    if title:
        parts.append(title)
    if breadcrumbs:
        parts.append(f"Раздел: {breadcrumbs}")
    if section:
        parts.append(f"Секция: {section}")

    return " | ".join(parts)


def deduplicate_results(results: List[Tuple[float, Dict]]) -> List[Tuple[float, Dict]]:
    seen = set()
    unique = []

    for score, chunk in results:
        key = (
            chunk.get("title", ""),
            chunk.get("section_heading", ""),
            chunk.get("chunk_text", "")[:200],
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append((score, chunk))

    return unique

def filter_results_for_context(results: List[Tuple[float, Dict]]) -> List[Tuple[float, Dict]]:
    strong = []
    weak = []

    for score, chunk in results:
        section = human_section(chunk.get("section_heading", ""))
        text = chunk.get("chunk_text", "").strip()

        # Общие обзорные секции стараемся не тащить в prompt,
        # если уже есть более конкретные фрагменты.
        if section in {"Раздел", ""}:
            weak.append((score, chunk))
            continue

        # Совсем короткие и малоинформативные фрагменты тоже в конец.
        if len(text) < 120:
            weak.append((score, chunk))
            continue

        strong.append((score, chunk))

    return strong + weak

def build_context_blocks(
    results: List[Tuple[float, Dict]],
    max_context_chars: int,
) -> Tuple[str, List[str]]:
    blocks = []
    source_labels = []
    total_len = 0

    for idx, (score, chunk) in enumerate(results, start=1):
        title = chunk.get("title", "").strip()
        breadcrumbs = " > ".join(chunk.get("breadcrumbs", []))
        section = human_section(chunk.get("section_heading", ""))
        text = chunk.get("chunk_text", "").strip()

        block = (
            f"[Источник {idx}]\n"
            f"Статья: {title}\n"
            f"Раздел: {breadcrumbs}\n"
            f"Секция: {section}\n"
            f"Фрагмент:\n{text}"
        )

        projected = total_len + len(block) + 2
        if projected > max_context_chars and blocks:
            break

        blocks.append(block)
        total_len += len(block) + 2
        source_labels.append(format_source_label(chunk))

    return "\n\n".join(blocks), source_labels


def build_prompt(query: str, context_blocks: str) -> str:
    return f"""Ты - помощник базы знаний службы поддержки пользователей.

Ответь на вопрос только по переданным источникам.

Правила:
1. Не выдумывай ничего сверх контекста.
2. Если данных недостаточно, прямо скажи об этом.
3. Дай только полезный прикладной ответ.
4. Если есть несколько способов решения, кратко перечисли их.
5. Если есть шаги, оформи их списком.
6. Не пересказывай весь контекст.
7. Ответ должен быть компактным.
8. В конце выведи блок "Источники".

Вопрос:
{query}

Источники:
{context_blocks}
""".strip()


def call_llm(prompt: str) -> str:
    return generate_answer(prompt)


def print_retrieval_preview(results: List[Tuple[float, Dict]]) -> None:
    print("\nНайденные фрагменты\n")
    print("=" * 80)
    for rank, (score, chunk) in enumerate(results, start=1):
        print(f"[{rank}] score={score:.4f}")
        print(f"title: {chunk.get('title', '')}")
        print(f"section: {human_section(chunk.get('section_heading', ''))}")
        print(f"breadcrumbs: {' > '.join(chunk.get('breadcrumbs', []))}")
        print(f"chunk_id: {chunk.get('chunk_id', '')}")
        print(f"text: {chunk.get('chunk_text', '')[:500]}")
        print("-" * 80)


def main():
    parser = argparse.ArgumentParser(description="Generate answer pipeline over retrieval")
    parser.add_argument("--query", required=True, help="Вопрос пользователя")
    parser.add_argument("--top-k", type=int, default=TOP_K_DEFAULT)
    parser.add_argument("--index-path", default=INDEX_PATH_DEFAULT)
    parser.add_argument("--chunk-map-path", default=CHUNK_MAP_PATH_DEFAULT)
    parser.add_argument("--model-name", default=MODEL_NAME_DEFAULT)
    parser.add_argument("--max-context-chars", type=int, default=MAX_CONTEXT_CHARS_DEFAULT)
    parser.add_argument(
        "--mode",
        choices=["prompt-only", "real-answer"],
        default=MODE_DEFAULT,
        help="prompt-only - печать только готового prompt; real-answer - retrieval + реальный вызов LLM",
    )
    args = parser.parse_args()

    print("Поиск релевантных фрагментов...")
    results = semantic_search(
        query=args.query,
        top_k=args.top_k,
        index_path=args.index_path,
        chunk_map_path=args.chunk_map_path,
        model_name=args.model_name,
    )

    results = deduplicate_results(results)
    results = filter_results_for_context(results)

    if not results:
        print("Ничего не найдено.")
        return

    context_blocks, source_labels = build_context_blocks(
        results=results,
        max_context_chars=args.max_context_chars,
    )

    prompt = build_prompt(args.query, context_blocks)

    if args.mode == "prompt-only":
        print("\nГотовый prompt\n")
        print("=" * 80)
        print(prompt)
        print("\nИсточники, которые будут показаны пользователю:\n")
        for i, src in enumerate(source_labels, start=1):
            print(f"{i}. {src}")
        return

    if args.mode == "real-answer":
        print_retrieval_preview(results)
        print("\nСформированный ответ\n")
        print("=" * 80)
        try:
            answer = call_llm(prompt)
            print(answer)
        except Exception as e:
            print(f"Ошибка вызова LLM: {e}")
            print("\nПодсказка:")
            print("- проверь, что source .env.yc действительно выполнен")
            print("- проверь YC_API_KEY, YC_FOLDER_ID и YC_MODEL_URI")
            print("- если видишь 401 Unauthenticated / Unknown api key, ключ неверный, удален или создан не для того service account")
            return

        print("\nИсточники\n")
        for i, src in enumerate(source_labels, start=1):
            print(f"{i}. {src}")
        return


if __name__ == "__main__":
    main()
