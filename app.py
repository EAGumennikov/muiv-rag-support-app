from __future__ import annotations

import os

from flask import Flask, render_template


def create_app() -> Flask:
    app = Flask(__name__)

    @app.route("/")
    def index():
        demo_answer = (
            "Это демонстрационная заглушка веб-интерфейса. На следующем этапе "
            "здесь будет отображаться результат работы retrieval и генерации ответа."
        )
        demo_sources = [
            "Документ базы знаний: пример инструкции.md",
            "Фрагмент корпуса: описание типового обращения пользователя",
        ]
        return render_template(
            "index.html",
            page_title="Главная",
            answer_text=demo_answer,
            sources=demo_sources,
        )

    @app.route("/about")
    def about():
        return render_template("about.html", page_title="О системе")

    return app


app = create_app()


if __name__ == "__main__":
    host = os.getenv("FLASK_RUN_HOST", "127.0.0.1")
    port = int(os.getenv("FLASK_RUN_PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "").lower() in {"1", "true", "yes"}
    app.run(host=host, port=port, debug=debug)
