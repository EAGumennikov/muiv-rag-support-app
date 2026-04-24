#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import argparse
from typing import List, Dict

import numpy as np

try:
    import faiss
    FAISS_AVAILABLE = True
except Exception:
    FAISS_AVAILABLE = False

from sentence_transformers import SentenceTransformer


INPUT_JSONL_DEFAULT = os.path.expanduser(
    "~/Projects/MUIV_Diplom_local/input/astra_linux_wiki_chunks.jsonl"
)
OUTPUT_EMBEDDINGS_DEFAULT = os.path.expanduser(
    "~/Projects/MUIV_Diplom_local/output/embeddings/astra_linux_wiki_embeddings.npy"
)
OUTPUT_INDEX_DEFAULT = os.path.expanduser(
    "~/Projects/MUIV_Diplom_local/output/indexes/astra_linux_wiki_faiss.index"
)
OUTPUT_CHUNK_MAP_DEFAULT = os.path.expanduser(
    "~/Projects/MUIV_Diplom_local/output/indexes/astra_linux_wiki_chunk_map.jsonl"
)
OUTPUT_STATS_DEFAULT = os.path.expanduser(
    "~/Projects/MUIV_Diplom_local/output/retrieval_debug/astra_linux_wiki_index_stats.txt"
)

MODEL_NAME_DEFAULT = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
BATCH_SIZE_DEFAULT = 64


def ensure_parent(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)


def load_chunks(jsonl_path: str) -> List[Dict]:
    chunks = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                chunks.append(obj)
            except Exception as e:
                raise ValueError(f"Ошибка чтения JSONL на строке {line_no}: {e}")
    return chunks


def build_text_for_embedding(chunk: Dict) -> str:
    title = chunk.get("title", "")
    section_heading = chunk.get("section_heading", "")
    chunk_text = chunk.get("chunk_text", "")

    parts = []
    if title:
        parts.append(f"Заголовок статьи: {title}")
    if section_heading:
        parts.append(f"Раздел: {section_heading}")
    if chunk_text:
        parts.append(chunk_text)

    return "\n\n".join(parts).strip()


def save_chunk_map(chunks: List[Dict], path: str) -> None:
    ensure_parent(path)
    with open(path, "w", encoding="utf-8") as f:
        for ch in chunks:
            f.write(json.dumps(ch, ensure_ascii=False) + "\n")


def write_stats(path: str, *, model_name: str, chunk_count: int, dim: int, faiss_used: bool) -> None:
    ensure_parent(path)
    with open(path, "w", encoding="utf-8") as f:
        f.write("Статистика индексирования\n")
        f.write(f"Модель эмбеддингов: {model_name}\n")
        f.write(f"Количество чанков: {chunk_count}\n")
        f.write(f"Размерность вектора: {dim}\n")
        f.write(f"FAISS: {'yes' if faiss_used else 'no'}\n")


def main():
    parser = argparse.ArgumentParser(description="Build embeddings and vector index for RAG")
    parser.add_argument("--input-jsonl", default=INPUT_JSONL_DEFAULT)
    parser.add_argument("--output-embeddings", default=OUTPUT_EMBEDDINGS_DEFAULT)
    parser.add_argument("--output-index", default=OUTPUT_INDEX_DEFAULT)
    parser.add_argument("--output-chunk-map", default=OUTPUT_CHUNK_MAP_DEFAULT)
    parser.add_argument("--output-stats", default=OUTPUT_STATS_DEFAULT)
    parser.add_argument("--model-name", default=MODEL_NAME_DEFAULT)
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE_DEFAULT)
    args = parser.parse_args()

    print("Загрузка чанков...")
    chunks = load_chunks(args.input_jsonl)
    if not chunks:
        raise ValueError("Файл chunks.jsonl пуст")

    print(f"Чанков загружено: {len(chunks)}")

    texts = [build_text_for_embedding(ch) for ch in chunks]

    print(f"Загрузка модели эмбеддингов: {args.model_name}")
    model = SentenceTransformer(args.model_name)

    print("Вычисление эмбеддингов...")
    embeddings = model.encode(
        texts,
        batch_size=args.batch_size,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    embeddings = np.asarray(embeddings, dtype=np.float32)

    if embeddings.ndim != 2:
        raise ValueError(f"Неожиданная форма embeddings: {embeddings.shape}")

    dim = embeddings.shape[1]
    print(f"Готово. shape={embeddings.shape}")

    ensure_parent(args.output_embeddings)
    np.save(args.output_embeddings, embeddings)
    print(f"Embeddings saved: {args.output_embeddings}")

    ensure_parent(args.output_chunk_map)
    save_chunk_map(chunks, args.output_chunk_map)
    print(f"Chunk map saved: {args.output_chunk_map}")

    if FAISS_AVAILABLE:
        print("Построение FAISS IndexFlatIP...")
        index = faiss.IndexFlatIP(dim)
        index.add(embeddings)
        ensure_parent(args.output_index)
        faiss.write_index(index, args.output_index)
        print(f"FAISS index saved: {args.output_index}")
    else:
        print("FAISS недоступен, этап построения индекса пропущен.")
        args.output_index = ""

    write_stats(
        args.output_stats,
        model_name=args.model_name,
        chunk_count=len(chunks),
        dim=dim,
        faiss_used=FAISS_AVAILABLE,
    )
    print(f"Stats saved: {args.output_stats}")
    print("Индексирование завершено.")


if __name__ == "__main__":
    main()
