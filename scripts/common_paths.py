#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Единая точка хранения путей к runtime-артефактам RAG-контура.

Модуль нужен для того, чтобы и CLI-скрипты, и веб-приложение ссылались
на одни и те же файлы индекса, chunk_map и эмбеддингов. Благодаря этому
кодовый репозиторий остается независимым от конкретного рабочего каталога.
"""

import os


def env_or_default(env_name: str, default: str) -> str:
    # Если путь задан через переменную окружения, используем его.
    # Иначе берем безопасное значение по умолчанию из внешнего workdir.
    value = os.environ.get(env_name, "").strip()
    if value:
        return os.path.expanduser(value)
    return os.path.expanduser(default)


WORKDIR_DEFAULT = "~/Projects/muiv-rag-support-workdir"

INPUT_CHUNKS_DEFAULT = env_or_default(
    "RAG_INPUT_CHUNKS",
    f"{WORKDIR_DEFAULT}/input/astra_linux_wiki_chunks.jsonl",
)

EMBEDDINGS_PATH_DEFAULT = env_or_default(
    "RAG_EMBEDDINGS_PATH",
    f"{WORKDIR_DEFAULT}/output/embeddings/astra_linux_wiki_embeddings.npy",
)

INDEX_PATH_DEFAULT = env_or_default(
    "RAG_INDEX_PATH",
    f"{WORKDIR_DEFAULT}/output/indexes/astra_linux_wiki_faiss.index",
)

CHUNK_MAP_PATH_DEFAULT = env_or_default(
    "RAG_CHUNK_MAP_PATH",
    f"{WORKDIR_DEFAULT}/output/indexes/astra_linux_wiki_chunk_map.jsonl",
)

RETRIEVAL_STATS_DEFAULT = env_or_default(
    "RAG_RETRIEVAL_STATS",
    f"{WORKDIR_DEFAULT}/output/retrieval_debug/astra_linux_wiki_index_stats.txt",
)
