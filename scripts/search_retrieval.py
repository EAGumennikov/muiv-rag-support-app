#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import argparse

import numpy as np
import faiss
from sentence_transformers import SentenceTransformer


from common_paths import INDEX_PATH_DEFAULT, CHUNK_MAP_PATH_DEFAULT

MODEL_NAME_DEFAULT = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
TOP_K_DEFAULT = 5


def load_chunk_map(path):
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


def format_result(rank, score, chunk):
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
    parser = argparse.ArgumentParser(description="Semantic search over Astra Linux chunk index")
    parser.add_argument("--query", required=True, help="Вопрос пользователя")
    parser.add_argument("--top-k", type=int, default=TOP_K_DEFAULT)
    parser.add_argument("--index-path", default=INDEX_PATH_DEFAULT)
    parser.add_argument("--chunk-map-path", default=CHUNK_MAP_PATH_DEFAULT)
    parser.add_argument("--model-name", default=MODEL_NAME_DEFAULT)
    args = parser.parse_args()

    print("Загрузка chunk_map...")
    chunks = load_chunk_map(args.chunk_map_path)
    print(f"Загружено чанков: {len(chunks)}")

    print("Загрузка FAISS-индекса...")
    index = faiss.read_index(args.index_path)
    print(f"Векторов в индексе: {index.ntotal}")

    print(f"Загрузка модели эмбеддингов: {args.model_name}")
    model = SentenceTransformer(args.model_name)

    query_text = args.query.strip()
    if not query_text:
        raise ValueError("Пустой запрос")

    query_embedding = model.encode(
        [query_text],
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    query_embedding = np.asarray(query_embedding, dtype=np.float32)

    scores, indices = index.search(query_embedding, args.top_k)

    print("\nРезультаты поиска\n")
    print(f"query: {query_text}")
    print("=" * 80)

    for rank, (score, idx) in enumerate(zip(scores[0], indices[0]), start=1):
        if idx < 0 or idx >= len(chunks):
            continue
        chunk = chunks[idx]
        print(format_result(rank, float(score), chunk))


if __name__ == "__main__":
    main()
