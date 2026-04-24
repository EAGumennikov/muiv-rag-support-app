from __future__ import annotations

import json
from typing import Dict, List, Tuple

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from scripts.common_paths import CHUNK_MAP_PATH_DEFAULT, INDEX_PATH_DEFAULT

MODEL_NAME_DEFAULT = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
TOP_K_DEFAULT = 5


Chunk = Dict
RetrievalResult = Tuple[float, Chunk]


def load_chunk_map(path: str) -> List[Chunk]:
    rows: List[Chunk] = []
    with open(path, "r", encoding="utf-8") as file:
        for line_no, line in enumerate(file, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception as exc:
                raise ValueError(f"Ошибка чтения chunk_map на строке {line_no}: {exc}") from exc
    return rows


def semantic_search(
    *,
    query: str,
    top_k: int = TOP_K_DEFAULT,
    index_path: str = INDEX_PATH_DEFAULT,
    chunk_map_path: str = CHUNK_MAP_PATH_DEFAULT,
    model_name: str = MODEL_NAME_DEFAULT,
) -> List[RetrievalResult]:
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

    results: List[RetrievalResult] = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0 or idx >= len(chunks):
            continue
        results.append((float(score), chunks[idx]))
    return results


def human_section(section_heading: str) -> str:
    if not section_heading:
        return ""
    return section_heading.lstrip("#").strip()


def format_source_label(chunk: Chunk) -> str:
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


def deduplicate_results(results: List[RetrievalResult]) -> List[RetrievalResult]:
    seen = set()
    unique: List[RetrievalResult] = []

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


def filter_results_for_context(results: List[RetrievalResult]) -> List[RetrievalResult]:
    strong: List[RetrievalResult] = []
    weak: List[RetrievalResult] = []

    for score, chunk in results:
        section = human_section(chunk.get("section_heading", ""))
        text = chunk.get("chunk_text", "").strip()

        if section in {"Раздел", ""}:
            weak.append((score, chunk))
            continue

        if len(text) < 120:
            weak.append((score, chunk))
            continue

        strong.append((score, chunk))

    return strong + weak


def get_retrieval_results(
    *,
    query: str,
    top_k: int = TOP_K_DEFAULT,
    index_path: str = INDEX_PATH_DEFAULT,
    chunk_map_path: str = CHUNK_MAP_PATH_DEFAULT,
    model_name: str = MODEL_NAME_DEFAULT,
) -> List[RetrievalResult]:
    results = semantic_search(
        query=query,
        top_k=top_k,
        index_path=index_path,
        chunk_map_path=chunk_map_path,
        model_name=model_name,
    )
    results = deduplicate_results(results)
    return filter_results_for_context(results)
