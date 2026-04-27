document.addEventListener("DOMContentLoaded", () => {
    const form = document.querySelector("#rag-search-form");
    if (!form || !window.fetch) {
        return;
    }

    const questionField = form.querySelector("#question");
    const submitButton = form.querySelector("#rag-submit-button");
    const errorBlock = document.querySelector("#rag-error");
    const loadingBlock = document.querySelector("#rag-loading");
    const answerBlock = document.querySelector("#rag-answer");
    const sourcesBlock = document.querySelector("#rag-sources");
    const exportBlock = document.querySelector("#rag-export");

    // AJAX-обработка дополняет обычную HTML-форму: при отключенном JavaScript
    // браузер продолжит отправлять POST на /ask стандартным способом.
    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const question = questionField.value.trim();

        clearError();
        if (!question) {
            showError("Введите вопрос, чтобы выполнить поиск по базе знаний.");
            return;
        }

        setLoading(true);
        try {
            const response = await fetch(form.action, {
                method: "POST",
                headers: {
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                credentials: "same-origin",
                body: JSON.stringify({ question }),
            });
            const data = await response.json().catch(() => ({}));

            if (!response.ok || data.ok === false) {
                showError(data.message || "Не удалось сформировать ответ. Повторите попытку позже.");
                return;
            }

            renderAnswer(data);
        } catch (error) {
            showError("Не удалось связаться с сервером. Проверьте подключение и повторите запрос.");
        } finally {
            setLoading(false);
        }
    });

    function setLoading(isLoading) {
        // Кнопка блокируется на время запроса, чтобы пользователь случайно
        // не запустил несколько обращений к защищенному контуру подряд.
        if (submitButton) {
            submitButton.disabled = isLoading;
        }
        if (loadingBlock) {
            loadingBlock.classList.toggle("is-hidden", !isLoading);
        }
    }

    function clearError() {
        if (!errorBlock) {
            return;
        }
        errorBlock.textContent = "";
        errorBlock.classList.add("is-hidden");
    }

    function showError(message) {
        if (!errorBlock) {
            return;
        }
        errorBlock.textContent = message;
        errorBlock.classList.remove("is-hidden");
    }

    function renderAnswer(data) {
        if (answerBlock) {
            answerBlock.innerHTML = data.answer_html || `<p>${escapeHtml(data.answer || "")}</p>`;
        }
        renderExportLink(data.export_url);
        renderSources(data.sources || []);
    }

    function renderExportLink(exportUrl) {
        if (!exportBlock) {
            return;
        }
        exportBlock.innerHTML = "";
        exportBlock.classList.toggle("is-hidden", !exportUrl);
        if (!exportUrl) {
            return;
        }

        const link = document.createElement("a");
        link.className = "button-secondary";
        link.href = exportUrl;
        link.textContent = "Скачать ответ DOCX";
        exportBlock.appendChild(link);
    }

    function renderSources(sources) {
        if (!sourcesBlock) {
            return;
        }
        sourcesBlock.innerHTML = "";
        sourcesBlock.classList.toggle("is-empty", sources.length === 0);

        if (sources.length === 0) {
            const placeholder = document.createElement("p");
            placeholder.className = "placeholder-text";
            placeholder.textContent = "Источники для ответа не найдены.";
            sourcesBlock.appendChild(placeholder);
            return;
        }

        sources.forEach((source) => {
            sourcesBlock.appendChild(buildSourceCard(source));
        });
    }

    function buildSourceCard(source) {
        // Карточки источников собираются из пользовательских полей JSON.
        // Внутренние пути, source_file и debug-данные сюда не передаются.
        const card = document.createElement("article");
        card.className = "source-card";

        const label = document.createElement("p");
        label.className = "source-label";
        label.textContent = "Источник из базы знаний";
        card.appendChild(label);

        const head = document.createElement("div");
        head.className = "source-card-head";
        const title = document.createElement("h3");
        title.textContent = source.title || "Источник базы знаний";
        head.appendChild(title);
        if (source.section) {
            const badge = document.createElement("span");
            badge.className = "source-badge";
            badge.textContent = source.section;
            head.appendChild(badge);
        }
        card.appendChild(head);

        if (Array.isArray(source.breadcrumbs) && source.breadcrumbs.length > 0) {
            const breadcrumbs = document.createElement("p");
            breadcrumbs.className = "source-breadcrumbs";
            breadcrumbs.textContent = source.breadcrumbs.join(" > ");
            card.appendChild(breadcrumbs);
        }

        if (source.excerpt) {
            const excerpt = document.createElement("p");
            excerpt.className = "source-excerpt";
            excerpt.textContent = source.excerpt;
            card.appendChild(excerpt);
        }

        const actions = document.createElement("div");
        actions.className = "source-actions";
        appendAction(actions, source.article_url, "Открыть статью");
        appendAction(actions, source.download_url, "Скачать markdown");
        appendAction(actions, source.article_docx_url, "Скачать docx");
        appendAction(actions, source.original_url, "Открыть оригинал", true);
        card.appendChild(actions);

        return card;
    }

    function appendAction(container, href, label, external = false) {
        if (!href) {
            return;
        }
        const link = document.createElement("a");
        link.className = "button-secondary";
        link.href = href;
        link.textContent = label;
        if (external) {
            link.target = "_blank";
            link.rel = "noopener noreferrer";
        }
        container.appendChild(link);
    }

    function escapeHtml(value) {
        const element = document.createElement("div");
        element.textContent = value;
        return element.innerHTML;
    }
});
