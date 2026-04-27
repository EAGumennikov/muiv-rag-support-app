# Роли и разграничение доступа

В приложении реализована базовая ролевая модель с тремя ролями:

- `support_user`;
- `knowledge_editor`;
- `admin`.

## Пользовательская роль `support_user`

Роль предназначена для сотрудника поддержки. Пользователь получает доступ к личному кабинету и видит только собственные данные.

Доступные разделы:

- `/cabinet`;
- `/cabinet/profile`;
- `/cabinet/history`;
- `/cabinet/saved-answers`;
- `/cabinet/feedback`;
- `/cabinet/help`;
- `/cabinet/history/export.xlsx`;
- свои RAG-ответы по `/export/rag-answer/<rag_answer_id>.docx`.

Пользователь не получает доступ к чужим ответам и административным выгрузкам.

## Роль `knowledge_editor`

Роль предназначена для анализа качества базы знаний и источников.

Доступные разделы:

- `/editor`;
- `/editor/content`;
- `/editor/sources`;
- `/editor/feedback`;
- `/editor/links`;
- экспорт RAG-ответов для анализа источников.

Редактор не получает административные `.xlsx`-выгрузки.

## Роль `admin`

Администратор получает доступ к общесистемным данным и административным страницам:

- `/admin`;
- `/admin/users`;
- `/admin/roles`;
- `/admin/feedback`;
- `/admin/feedback/<id>`;
- `/admin/history`;
- `/admin/content`;
- `/admin/audit`;
- `/admin/export/feedback.xlsx`;
- `/admin/export/history.xlsx`;
- `/admin/export/statistics.xlsx`.

## Сессионная аутентификация

Текущий пользователь хранится в Flask-сессии. Перед обработкой запроса приложение восстанавливает пользователя в `g.current_user`.

Для защиты маршрутов используются:

- `login_required` - проверяет факт входа;
- `roles_required` - проверяет наличие нужной роли.

## Персонализация данных

История запросов и feedback имеют nullable-поле `user_id`. Если пользователь вошел в систему, запись связывается с его учетной записью. Если сценарий выполнен публично, `user_id` остается пустым.

RAG-ответ связан с пользователем через `SearchQuery`, поэтому дополнительное поле `user_id` в `RagAnswer` не дублируется.
