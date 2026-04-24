from __future__ import annotations

from markupsafe import Markup
import markdown


def render_markdown(text: str) -> Markup:
    html = markdown.markdown(
        text or "",
        extensions=[
            "extra",
            "fenced_code",
            "sane_lists",
            "nl2br",
            "tables",
        ],
        output_format="html5",
    )
    return Markup(html)
