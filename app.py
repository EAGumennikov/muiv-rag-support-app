from __future__ import annotations

import os

from flask import Flask, Response, jsonify, redirect, render_template, request, url_for

from services.answer_service import generate_answer_from_query
from services.article_service import (
    article_download_payload,
    build_content_disposition,
    get_document_or_404,
    get_documents_list,
)
from services.db_service import initialize_database, save_search_interaction
from services.feedback_service import save_feedback
from services.markdown_service import render_markdown
from services.site_content_service import get_page_by_endpoint, get_public_navigation


def build_breadcrumbs(*items: tuple[str, str | None]):
    crumbs = [{"label": "Главная", "url": url_for("index")}]
    for label, url in items:
        crumbs.append({"label": label, "url": url})
    return crumbs


def render_content_page(endpoint: str):
    page = get_page_by_endpoint(endpoint)
    return render_template(
        "content_page.html",
        page_title=page["title"],
        page=page,
        breadcrumbs=build_breadcrumbs((page["title"], None)) if endpoint != "index" else build_breadcrumbs(),
    )


def render_search_page(
    *,
    question: str = "",
    answer_text: str = "",
    sources: list[dict] | None = None,
    debug: dict | None = None,
    error_message: str = "",
):
    page = get_page_by_endpoint("search_page")
    return render_template(
        "search.html",
        page_title=page["title"],
        page=page,
        breadcrumbs=build_breadcrumbs((page["title"], None)),
        question=question,
        answer_html=render_markdown(answer_text) if answer_text else "",
        sources=sources or [],
        debug=debug or {},
        error_message=error_message,
    )


def create_app() -> Flask:
    app = Flask(__name__)
    app.jinja_env.filters["markdown_to_html"] = render_markdown
    initialize_database()

    @app.context_processor
    def inject_site_navigation():
        return {"public_navigation": get_public_navigation()}

    @app.route("/")
    def index():
        page = get_page_by_endpoint("index")
        highlighted_docs = get_documents_list(limit=6)
        return render_template(
            "home.html",
            page_title=page["title"],
            page=page,
            breadcrumbs=build_breadcrumbs(),
            featured_articles=highlighted_docs,
        )

    @app.route("/search")
    def search_page():
        return render_search_page()

    @app.route("/ask", methods=["POST"])
    def ask():
        is_json_request = request.is_json
        payload = request.get_json(silent=True) if is_json_request else None
        question = str((payload or {}).get("question", "")).strip() if payload else request.form.get("question", "").strip()

        if not question:
            error_message = "Введите вопрос, чтобы выполнить поиск по базе знаний."
            if is_json_request:
                return jsonify({"error": error_message}), 400
            return render_search_page(question=question, error_message=error_message), 400

        try:
            result = generate_answer_from_query(query=question)
        except Exception as exc:
            error_message = f"Не удалось обработать запрос: {exc}"
            if is_json_request:
                return jsonify({"error": error_message}), 500
            return render_search_page(question=question, error_message=error_message), 500

        try:
            save_search_interaction(question=question, result=result, channel="web")
        except Exception:
            # Ошибки сохранения истории не должны ломать основной пользовательский сценарий.
            pass

        if is_json_request:
            return jsonify(
                {
                    "question": result["query"],
                    "answer": result["answer"],
                    "answer_html": str(render_markdown(result["answer"])),
                    "sources": result["sources"],
                    "source_labels": result.get("source_labels", []),
                    "debug": result["debug"],
                }
            )

        return render_search_page(
            question=result["query"],
            answer_text=result["answer"],
            sources=result["sources"],
            debug=result["debug"],
        )

    @app.route("/articles")
    def articles_page():
        page = get_page_by_endpoint("articles_page")
        documents = get_documents_list(limit=60)
        return render_template(
            "articles.html",
            page_title=page["title"],
            page=page,
            breadcrumbs=build_breadcrumbs((page["title"], None)),
            documents=documents,
            documents_count=len(get_documents_list()),
        )

    @app.route("/glossary")
    def glossary_page():
        return render_content_page("glossary_page")

    @app.route("/onboarding")
    def onboarding_page():
        return render_content_page("onboarding_page")

    @app.route("/faq")
    def faq_page():
        return render_content_page("faq_page")

    @app.route("/about-system")
    def about_system_page():
        return render_content_page("about_system_page")

    @app.route("/about-kb")
    def about_kb_page():
        return render_content_page("about_kb_page")

    @app.route("/testing")
    def testing_page():
        return render_content_page("testing_page")

    @app.route("/feedback", methods=["GET", "POST"])
    def feedback_page():
        page = get_page_by_endpoint("feedback_page")
        success_message = ""
        error_message = ""
        form_data = {"name": "", "email": "", "topic": "", "message": ""}

        if request.method == "POST":
            form_data = {
                "name": request.form.get("name", "").strip(),
                "email": request.form.get("email", "").strip(),
                "topic": request.form.get("topic", "").strip(),
                "message": request.form.get("message", "").strip(),
            }
            if not all(form_data.values()):
                error_message = "Заполните все поля формы обратной связи."
            else:
                save_feedback(**form_data)
                success_message = "Сообщение успешно отправлено. Спасибо за обратную связь."
                form_data = {"name": "", "email": "", "topic": "", "message": ""}

        return render_template(
            "feedback.html",
            page_title=page["title"],
            page=page,
            breadcrumbs=build_breadcrumbs((page["title"], None)),
            success_message=success_message,
            error_message=error_message,
            form_data=form_data,
        )

    @app.route("/article/<doc_id>")
    def article_detail(doc_id: str):
        document = get_document_or_404(doc_id)
        return render_template(
            "article_detail.html",
            page_title=document["title"],
            article=document,
            article_html=render_markdown(document["body_markdown_text"]),
            breadcrumbs=build_breadcrumbs(
                ("Статьи", url_for("articles_page")),
                (document["title"], None),
            ),
        )

    @app.route("/download/<doc_id>")
    def download_article(doc_id: str):
        document = get_document_or_404(doc_id)
        payload = article_download_payload(document)
        return Response(
            payload,
            mimetype="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": build_content_disposition(document["download_name"]),
            },
        )

    @app.route("/about")
    def about():
        return redirect(url_for("about_system_page"))

    return app


app = create_app()


if __name__ == "__main__":
    host = os.getenv("FLASK_RUN_HOST", "127.0.0.1")
    port = int(os.getenv("FLASK_RUN_PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "").lower() in {"1", "true", "yes"}
    app.run(host=host, port=port, debug=debug)
