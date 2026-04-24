from __future__ import annotations

"""
Главный Flask-модуль учебного веб-приложения.

Здесь собирается публичный контур сайта: маршруты страниц, маршрут /ask,
обработка формы обратной связи и выдача пользовательских страниц статей.
Модуль не содержит тяжелой бизнес-логики RAG сам по себе, а связывает
HTML-шаблоны с сервисным слоем, чтобы архитектура оставалась понятной:
веб-уровень отвечает за маршрутизацию и отображение, а сервисы — за данные.
"""

import os

from flask import Flask, Response, g, jsonify, redirect, render_template, request, session, url_for

from services.answer_service import generate_answer_from_query
from services.article_service import (
    article_download_payload,
    build_content_disposition,
    get_document_or_404,
    get_documents_list,
)
from services.access_content_service import (
    get_admin_pages,
    get_cabinet_pages,
    get_editor_pages,
    get_page_by_endpoint as get_secure_page_by_endpoint,
)
from services.auth_service import (
    ROLE_ADMIN,
    ROLE_KNOWLEDGE_EDITOR,
    SESSION_USER_ID_KEY,
    authenticate_user,
    current_user_from_context,
    get_current_user,
    login_required,
    login_user,
    logout_user,
    roles_required,
    user_primary_role_label,
)
from services.db_service import (
    get_admin_dashboard_stats,
    get_content_statistics,
    initialize_database,
    list_feedback_messages,
    list_recent_audit_logs,
    list_recent_rag_answers,
    list_recent_search_queries,
    list_roles_summary,
    list_users_with_roles,
    save_search_interaction,
)
from services.feedback_service import save_feedback
from services.markdown_service import render_markdown
from services.site_content_service import get_page_by_endpoint, get_public_navigation


def build_breadcrumbs(*items: tuple[str, str | None]):
    # Хлебные крошки собираются централизованно, чтобы все страницы сайта
    # выглядели единообразно и не дублировали одну и ту же логику в шаблонах.
    crumbs = [{"label": "Главная", "url": url_for("index")}]
    for label, url in items:
        crumbs.append({"label": label, "url": url})
    return crumbs


def render_content_page(endpoint: str):
    # Для статичных пользовательских разделов используем единый шаблон.
    # Это упрощает поддержку сайта: тексты лежат в сервисе контента,
    # а сами маршруты остаются короткими и наглядными.
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
    # Экран поиска рендерится отдельной функцией, потому что один и тот же
    # шаблон используется и при первом открытии страницы, и после отправки
    # вопроса, и в случае ошибки обработки запроса.
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


def render_secure_section(
    *,
    page: dict,
    section_label: str,
    navigation_title: str,
    section_navigation: list[dict],
    info_cards: list[dict] | None = None,
    records: list[dict] | None = None,
    records_title: str = "",
    empty_message: str = "",
):
    # Общий шаблон нужен, чтобы кабинет, редакторский контур и админ-панель
    # выглядели согласованно, но не дублировали одинаковую верстку в app.py.
    return render_template(
        "secure_page.html",
        page_title=page["title"],
        page=page,
        section_label=section_label,
        navigation_title=navigation_title,
        section_navigation=section_navigation,
        info_cards=info_cards or [],
        records=records or [],
        records_title=records_title,
        empty_message=empty_message,
        breadcrumbs=build_breadcrumbs((section_label, section_navigation[0]["route"]), (page["title"], None)),
    )


def create_app() -> Flask:
    # Создание приложения вынесено в фабрику, чтобы модуль было удобно
    # импортировать как из локального запуска, так и из тестов.
    app = Flask(__name__)
    # Для учебного локального запуска допускается значение по умолчанию,
    # но в реальной среде секретный ключ лучше задавать через окружение.
    app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "muiv-rag-support-dev-secret")
    app.jinja_env.filters["markdown_to_html"] = render_markdown
    initialize_database()

    @app.before_request
    def load_current_user():
        # Текущий пользователь восстанавливается из Flask-сессии до обработки
        # маршрута, чтобы дальнейшая логика могла опираться на единый g.current_user.
        g.current_user = get_current_user(session.get(SESSION_USER_ID_KEY))

    @app.context_processor
    def inject_site_navigation():
        current_user = current_user_from_context()
        return {
            "public_navigation": get_public_navigation(),
            "current_user": current_user,
            "current_user_role_label": user_primary_role_label(current_user),
        }

    @app.route("/")
    def index():
        # Главная страница показывает краткое описание проекта и несколько
        # примеров статей, чтобы пользователь сразу видел предметную область.
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
        # Отдельная страница поиска нужна, чтобы маршрут /ask отвечал только
        # за обработку вопроса, а не за рендер стартового состояния интерфейса.
        return render_search_page()

    @app.route("/login", methods=["GET", "POST"])
    def login_page():
        # В проекте нет открытой регистрации, поэтому вход строится
        # вокруг заранее подготовленных или вручную созданных учетных записей.
        error_message = ""
        next_url = request.args.get("next", "").strip() or request.form.get("next", "").strip()

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            user = authenticate_user(username=username, password=password)
            if user is None:
                error_message = "Не удалось выполнить вход. Проверьте логин, пароль и активность учетной записи."
            else:
                login_user(user)
                return redirect(next_url or url_for("index"))

        return render_template(
            "login.html",
            page_title="Вход",
            breadcrumbs=build_breadcrumbs(("Вход", None)),
            error_message=error_message,
            next_url=next_url,
        )

    @app.route("/logout")
    def logout_page():
        logout_user()
        return redirect(url_for("index"))

    @app.route("/cabinet")
    @login_required
    def cabinet_home():
        user = current_user_from_context()
        page = get_secure_page_by_endpoint("cabinet_home", get_cabinet_pages())
        return render_secure_section(
            page=page,
            section_label="Личный кабинет",
            navigation_title="Разделы кабинета",
            section_navigation=get_cabinet_pages(),
            info_cards=[
                {"label": "Пользователь", "value": user.display_name, "note": user.username},
                {"label": "Роль", "value": user_primary_role_label(user), "note": ", ".join(user.roles)},
                {"label": "Статус", "value": "Активен" if user.is_active else "Неактивен", "note": user.email},
            ],
        )

    @app.route("/cabinet/profile")
    @login_required
    def cabinet_profile():
        user = current_user_from_context()
        page = get_secure_page_by_endpoint("cabinet_profile", get_cabinet_pages())
        return render_secure_section(
            page=page,
            section_label="Личный кабинет",
            navigation_title="Разделы кабинета",
            section_navigation=get_cabinet_pages(),
            info_cards=[
                {"label": "Полное имя", "value": user.display_name, "note": ""},
                {"label": "Логин", "value": user.username, "note": ""},
                {"label": "Электронная почта", "value": user.email or "Не указана", "note": ""},
            ],
        )

    @app.route("/cabinet/history")
    @login_required
    def cabinet_history():
        page = get_secure_page_by_endpoint("cabinet_history", get_cabinet_pages())
        records = [
            {
                "Вопрос": row["question_text"],
                "Найдено фрагментов": row["retrieved_chunks_count"],
                "Использовано": row["used_chunks_count"],
                "Время": row["created_at"],
            }
            for row in list_recent_search_queries(limit=10)
        ]
        return render_secure_section(
            page=page,
            section_label="Личный кабинет",
            navigation_title="Разделы кабинета",
            section_navigation=get_cabinet_pages(),
            records=records,
            records_title="Последние запросы",
            empty_message="История запросов пока не накоплена.",
        )

    @app.route("/cabinet/saved-answers")
    @login_required
    def cabinet_saved_answers():
        page = get_secure_page_by_endpoint("cabinet_saved_answers", get_cabinet_pages())
        records = [
            {
                "Ответ": row["answer_text"],
                "Создан": row["created_at"],
            }
            for row in list_recent_rag_answers(limit=10)
        ]
        return render_secure_section(
            page=page,
            section_label="Личный кабинет",
            navigation_title="Разделы кабинета",
            section_navigation=get_cabinet_pages(),
            records=records,
            records_title="Последние ответы системы",
            empty_message="Сохраненные ответы пока отсутствуют.",
        )

    @app.route("/cabinet/help")
    @login_required
    def cabinet_help():
        page = get_secure_page_by_endpoint("cabinet_help", get_cabinet_pages())
        return render_secure_section(
            page=page,
            section_label="Личный кабинет",
            navigation_title="Разделы кабинета",
            section_navigation=get_cabinet_pages(),
        )

    @app.route("/editor/content")
    @roles_required(ROLE_KNOWLEDGE_EDITOR, ROLE_ADMIN)
    def editor_content():
        page = get_secure_page_by_endpoint("editor_content", get_editor_pages())
        return render_secure_section(
            page=page,
            section_label="Контур редактора",
            navigation_title="Рабочие разделы редактора",
            section_navigation=get_editor_pages(),
            info_cards=get_content_statistics(),
        )

    @app.route("/admin")
    @roles_required(ROLE_ADMIN)
    def admin_home():
        page = get_secure_page_by_endpoint("admin_home", get_admin_pages())
        return render_secure_section(
            page=page,
            section_label="Панель администратора",
            navigation_title="Разделы админ-панели",
            section_navigation=get_admin_pages(),
            info_cards=get_admin_dashboard_stats(),
        )

    @app.route("/admin/users")
    @roles_required(ROLE_ADMIN)
    def admin_users():
        page = get_secure_page_by_endpoint("admin_users", get_admin_pages())
        records = [
            {
                "Логин": row["username"],
                "ФИО": row["full_name"] or "Не указано",
                "Email": row["email"] or "Не указан",
                "Роли": row["roles"],
                "Активность": "Да" if row["is_active"] else "Нет",
            }
            for row in list_users_with_roles()
        ]
        return render_secure_section(
            page=page,
            section_label="Панель администратора",
            navigation_title="Разделы админ-панели",
            section_navigation=get_admin_pages(),
            records=records,
            records_title="Пользователи системы",
            empty_message="Пользователи пока не созданы.",
        )

    @app.route("/admin/roles")
    @roles_required(ROLE_ADMIN)
    def admin_roles():
        page = get_secure_page_by_endpoint("admin_roles", get_admin_pages())
        records = [
            {
                "Код": row["code"],
                "Название": row["name"],
                "Описание": row["description"],
                "Пользователей": row["users_count"],
            }
            for row in list_roles_summary()
        ]
        return render_secure_section(
            page=page,
            section_label="Панель администратора",
            navigation_title="Разделы админ-панели",
            section_navigation=get_admin_pages(),
            records=records,
            records_title="Роли доступа",
            empty_message="Роли пока не инициализированы.",
        )

    @app.route("/admin/feedback")
    @roles_required(ROLE_ADMIN)
    def admin_feedback():
        page = get_secure_page_by_endpoint("admin_feedback", get_admin_pages())
        records = [
            {
                "Имя": row["name"],
                "Email": row["email"],
                "Тема": row["topic"],
                "Статус": row["status"],
                "Время": row["created_at"],
            }
            for row in list_feedback_messages(limit=20)
        ]
        return render_secure_section(
            page=page,
            section_label="Панель администратора",
            navigation_title="Разделы админ-панели",
            section_navigation=get_admin_pages(),
            records=records,
            records_title="Сообщения обратной связи",
            empty_message="Сообщения обратной связи пока отсутствуют.",
        )

    @app.route("/admin/content")
    @roles_required(ROLE_ADMIN)
    def admin_content():
        page = get_secure_page_by_endpoint("admin_content", get_admin_pages())
        return render_secure_section(
            page=page,
            section_label="Панель администратора",
            navigation_title="Разделы админ-панели",
            section_navigation=get_admin_pages(),
            info_cards=get_content_statistics(),
        )

    @app.route("/admin/audit")
    @roles_required(ROLE_ADMIN)
    def admin_audit():
        page = get_secure_page_by_endpoint("admin_audit", get_admin_pages())
        records = [
            {
                "Событие": row["event_type"],
                "Сущность": row["entity_type"] or "—",
                "ID": row["entity_id"] or "—",
                "Время": row["created_at"],
            }
            for row in list_recent_audit_logs(limit=20)
        ]
        return render_secure_section(
            page=page,
            section_label="Панель администратора",
            navigation_title="Разделы админ-панели",
            section_navigation=get_admin_pages(),
            records=records,
            records_title="Журнал событий",
            empty_message="События аудита пока отсутствуют.",
        )

    @app.route("/ask", methods=["POST"])
    def ask():
        # Один и тот же маршрут поддерживает и обычную HTML-форму, и JSON-запросы.
        # Это позволяет использовать его и в веб-интерфейсе, и в будущем — в AJAX.
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
            # Для программного клиента возвращаем уже готовые данные ответа
            # и HTML-представление markdown, чтобы фронтенд мог выбрать формат.
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
        # Каталог статей — отдельная пользовательская точка входа в корпус знаний.
        # Здесь можно просматривать материалы независимо от сценария /ask.
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
        # Форма обратной связи оставлена максимально простой, но уже пишет
        # данные в SQL-слой, чтобы проект был готов к следующему этапу.
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
        # Пользовательская страница статьи строится поверх уже подготовленных
        # метаданных корпуса и не показывает внутренние служебные поля.
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
        # Скачать markdown можно как исходный нормализованный файл,
        # а если его нет на диске — как реконструированный текст статьи.
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
    # В локальном учебном сценарии приложение запускается встроенным сервером Flask.
    # Настройки хоста и порта можно переопределить через переменные окружения.
    host = os.getenv("FLASK_RUN_HOST", "127.0.0.1")
    port = int(os.getenv("FLASK_RUN_PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "").lower() in {"1", "true", "yes"}
    app.run(host=host, port=port, debug=debug)
