from __future__ import annotations

import os

from flask import Flask, jsonify, render_template, request

from services.answer_service import generate_answer_from_query


def render_index_page(
    *,
    question: str = "",
    answer_text: str = "",
    sources: list[str] | None = None,
    debug: dict | None = None,
    error_message: str = "",
):
    return render_template(
        "index.html",
        page_title="Главная",
        question=question,
        answer_text=answer_text,
        sources=sources or [],
        debug=debug or {},
        error_message=error_message,
    )


def create_app() -> Flask:
    app = Flask(__name__)

    @app.route("/")
    def index():
        return render_index_page()

    @app.route("/ask", methods=["POST"])
    def ask():
        is_json_request = request.is_json
        payload = request.get_json(silent=True) if is_json_request else None
        question = ""
        if payload:
            question = str(payload.get("question", "")).strip()
        else:
            question = request.form.get("question", "").strip()

        if not question:
            error_message = "Введите вопрос, чтобы выполнить поиск по базе знаний."
            if is_json_request:
                return jsonify({"error": error_message}), 400
            return render_index_page(question=question, error_message=error_message), 400

        try:
            result = generate_answer_from_query(query=question)
        except Exception as exc:
            error_message = f"Не удалось обработать запрос: {exc}"
            if is_json_request:
                return jsonify({"error": error_message}), 500
            return render_index_page(question=question, error_message=error_message), 500

        if is_json_request:
            return jsonify(
                {
                    "question": result["query"],
                    "answer": result["answer"],
                    "sources": result["sources"],
                    "debug": result["debug"],
                }
            )

        return render_index_page(
            question=result["query"],
            answer_text=result["answer"],
            sources=result["sources"],
            debug=result["debug"],
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
