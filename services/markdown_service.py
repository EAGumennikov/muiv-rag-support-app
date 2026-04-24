from __future__ import annotations

import re

from markupsafe import Markup
import markdown


def normalize_markdown(text: str) -> str:
    value = (text or "").replace("\r\n", "\n").strip()
    if not value:
        return ""

    # Нормализуем часто встречающиеся маркеры списков из LLM-ответов.
    value = re.sub(r"(?m)^[ \t]*[•●▪◦]\s+", "- ", value)

    # Убираем лишнюю обертку ```markdown ... ```, если модель вернула весь ответ в одном fenced block.
    fenced_match = re.fullmatch(r"```(?:markdown|md)?\n(?P<body>.*)\n```", value, flags=re.DOTALL)
    if fenced_match:
        value = fenced_match.group("body").strip()

    # Если модель открыла fenced block и забыла закрыть, закрываем его для корректного HTML-рендера.
    if value.count("```") % 2 == 1:
        value = f"{value}\n```"

    return value


def render_markdown(text: str) -> Markup:
    normalized_text = normalize_markdown(text)
    html = markdown.markdown(
        normalized_text,
        extensions=[
            "extra",
            "fenced_code",
            "md_in_html",
            "sane_lists",
            "nl2br",
            "tables",
        ],
        output_format="html5",
    )
    return Markup(html)
