#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CLI-пайплайн полного RAG-сценария: retrieval -> prompt -> answer.

Скрипт полезен для пошаговой отладки без Flask: можно отдельно посмотреть
готовый prompt или получить реальный ответ модели. Это позволяет проверять
качество retrieval и prompt-инженерии параллельно с веб-контуром.
"""

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parent
# Импортируем сервисный слой из репозитория так же, как это делает Flask.
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

from services.answer_service import (
    MAX_CONTEXT_CHARS_DEFAULT,
    build_context_blocks,
    build_prompt,
    generate_answer_from_query,
    print_retrieval_preview,
)
from services.retrieval_service import (
    CHUNK_MAP_PATH_DEFAULT,
    INDEX_PATH_DEFAULT,
    MODEL_NAME_DEFAULT,
    TOP_K_DEFAULT,
    get_retrieval_results,
)

MODE_DEFAULT = "prompt-only"


def main():
    # Через режимы можно по-разному использовать один и тот же пайплайн:
    # либо вывести только prompt, либо выполнить полный вызов внешней LLM.
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
    results = get_retrieval_results(
        query=args.query,
        top_k=args.top_k,
        index_path=args.index_path,
        chunk_map_path=args.chunk_map_path,
        model_name=args.model_name,
    )

    if not results:
        print("Ничего не найдено.")
        return

    context_blocks, source_labels = build_context_blocks(
        results=results,
        max_context_chars=args.max_context_chars,
    )

    prompt = build_prompt(args.query, context_blocks)

    if args.mode == "prompt-only":
        # Этот режим особенно полезен при учебной отладке:
        # можно анализировать prompt без затрат на вызов модели.
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
            # Веб-приложение и CLI используют одну и ту же функцию генерации,
            # чтобы поведение пайплайна не расходилось между контурами.
            payload = generate_answer_from_query(
                query=args.query,
                top_k=args.top_k,
                index_path=args.index_path,
                chunk_map_path=args.chunk_map_path,
                model_name=args.model_name,
                max_context_chars=args.max_context_chars,
            )
            print(payload["answer"])
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
