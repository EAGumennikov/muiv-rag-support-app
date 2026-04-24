from __future__ import annotations

from typing import Dict, List, Tuple

from scripts.common_paths import CHUNK_MAP_PATH_DEFAULT, INDEX_PATH_DEFAULT
from scripts.providers.yandex_llm import generate_answer

from services.retrieval_service import (
    MODEL_NAME_DEFAULT,
    TOP_K_DEFAULT,
    RetrievalResult,
    format_source_label,
    get_retrieval_results,
    human_section,
)

MAX_CONTEXT_CHARS_DEFAULT = 3500


def build_context_blocks(
    results: List[RetrievalResult],
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


def print_retrieval_preview(results: List[RetrievalResult]) -> None:
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


def generate_answer_from_query(
    *,
    query: str,
    top_k: int = TOP_K_DEFAULT,
    index_path: str = INDEX_PATH_DEFAULT,
    chunk_map_path: str = CHUNK_MAP_PATH_DEFAULT,
    model_name: str = MODEL_NAME_DEFAULT,
    max_context_chars: int = MAX_CONTEXT_CHARS_DEFAULT,
) -> Dict:
    query = query.strip()
    if not query:
        raise ValueError("Пустой запрос")

    results = get_retrieval_results(
        query=query,
        top_k=top_k,
        index_path=index_path,
        chunk_map_path=chunk_map_path,
        model_name=model_name,
    )
    if not results:
        return {
            "query": query,
            "answer": "По запросу не удалось найти релевантные фрагменты в индексированном корпусе.",
            "sources": [],
            "debug": {
                "retrieved_chunks": 0,
                "used_chunks": 0,
            },
            "prompt": "",
            "retrieval_results": [],
        }

    context_blocks, source_labels = build_context_blocks(
        results=results,
        max_context_chars=max_context_chars,
    )
    prompt = build_prompt(query, context_blocks)
    answer = generate_answer(prompt)

    return {
        "query": query,
        "answer": answer,
        "sources": source_labels,
        "debug": {
            "retrieved_chunks": len(results),
            "used_chunks": len(source_labels),
        },
        "prompt": prompt,
        "retrieval_results": results,
    }
