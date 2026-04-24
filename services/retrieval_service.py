from __future__ import annotations

"""
Сервис retrieval для поиска релевантных фрагментов по корпусу знаний.

Модуль инкапсулирует загрузку chunk_map, обращение к FAISS-индексу и
постобработку найденных фрагментов. Именно отсюда начинается связка
"вопрос пользователя -> релевантные чанки", которая затем передается
в генерацию итогового ответа через внешнюю LLM.
"""

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
    # chunk_map хранит метаданные каждого фрагмента корпуса.
    # При поиске он нужен для обратного перехода от индекса FAISS
    # к человекочитаемому содержимому и источнику.
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
    # Функция выполняет "чистый" семантический поиск:
    # 1. загружает индекс и карту чанков;
    # 2. строит embedding для вопроса;
    # 3. получает top-k наиболее близких фрагментов.
    chunks = load_chunk_map(chunk_map_path)
    index = faiss.read_index(index_path)
    model = SentenceTransformer(model_name)

    # Нормализация эмбеддингов нужна, потому что индекс строится
    # на косинусной близости через скалярное произведение.
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
    # В корпусе заголовки секций часто приходят в markdown-виде.
    # Для пользовательского интерфейса и prompt удобнее хранить их
    # уже без символов # и лишних пробелов.
    if not section_heading:
        return ""
    return section_heading.lstrip("#").strip()


def format_source_label(chunk: Chunk) -> str:
    # Компактная подпись источника используется и в CLI, и в SQL-слое.
    # Она помогает быстро понять, какая статья и какой раздел попали в ответ.
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
    # После поиска в индекс могут попасть почти одинаковые куски одного документа.
    # Здесь отбрасываем дубли, чтобы не перегружать prompt и пользовательскую выдачу.
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
    # Не все найденные фрагменты одинаково полезны для LLM.
    # Более содержательные куски ставим вперед, а слишком общие или короткие
    # уводим в конец списка, чтобы они реже попадали в ограниченный контекст.
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
    # Публичная функция retrieval-слоя. Она скрывает внутренние шаги:
    # поиск, дедупликацию и упорядочивание результатов по полезности.
    results = semantic_search(
        query=query,
        top_k=top_k,
        index_path=index_path,
        chunk_map_path=chunk_map_path,
        model_name=model_name,
    )
    results = deduplicate_results(results)
    return filter_results_for_context(results)
