#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Адаптер вызова Yandex AI Studio через OpenAI-совместимый API.

Проект использует единый интерфейс OpenAI-клиента, но фактически отправляет
запросы в Yandex AI Studio. Это позволяет сохранить привычную структуру вызова
LLM и при этом работать с выбранным внешним провайдером.
"""

import os
from openai import OpenAI


def get_yandex_client() -> OpenAI:
    # Создаем клиента только после проверки ключа, чтобы ошибка настройки
    # была понятной и возникала до отправки первого запроса.
    api_key = os.environ.get("YC_API_KEY", "").strip()
    if not api_key:
        raise ValueError("Не задана переменная окружения YC_API_KEY")

    return OpenAI(
        api_key=api_key,
        base_url="https://llm.api.cloud.yandex.net/v1",
    )


def get_model_uri() -> str:
    # Модель можно задать полностью через YC_MODEL_URI.
    # Если URI не указан, он собирается из folder_id по принятому шаблону.
    model_uri = os.environ.get("YC_MODEL_URI", "").strip()
    if model_uri:
        return model_uri

    folder_id = os.environ.get("YC_FOLDER_ID", "").strip()
    if not folder_id:
        raise ValueError("Не задана YC_MODEL_URI и не задана YC_FOLDER_ID")

    return f"gpt://{folder_id}/deepseek-v32/latest"


def generate_answer(prompt: str, temperature: float = 0.2, max_tokens: int = 1200) -> str:
    # Ответ формируется в chat.completions-формате, чтобы логика вызова
    # была совместима с OpenAI-подобным интерфейсом и легко читалась в проекте.
    client = get_yandex_client()
    model_uri = get_model_uri()

    response = client.chat.completions.create(
        model=model_uri,
        messages=[
            {
                "role": "system",
                # Системное сообщение дополнительно удерживает модель
                # в рамках роли помощника базы знаний.
                "content": "Ты помощник базы знаний службы поддержки. Отвечай только по переданному контексту."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )

    return response.choices[0].message.content.strip()
