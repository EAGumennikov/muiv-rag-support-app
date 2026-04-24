from __future__ import annotations

"""
Сервис описания защищенных разделов приложения.

Здесь собраны структуры страниц личного кабинета, панели администратора
и рабочего контура редактора знаний. Такой подход позволяет держать тексты
и навигацию отдельно от Flask-маршрутов и не захламлять app.py.
"""

from typing import Dict, List


CABINET_PAGES: List[Dict] = [
    {
        "endpoint": "cabinet_home",
        "route": "/cabinet",
        "title": "Личный кабинет",
        "heading": "Рабочий кабинет пользователя",
        "summary": "Раздел объединяет персональные и рабочие страницы авторизованного пользователя.",
        "content": "Здесь собраны разделы, которые доступны после входа: профиль, история обращений к RAG-сервису и справочные материалы для работы с системой.",
    },
    {
        "endpoint": "cabinet_profile",
        "route": "/cabinet/profile",
        "title": "Профиль",
        "heading": "Профиль пользователя",
        "summary": "Страница показывает основные данные учетной записи и текущую роль в системе.",
        "content": "На следующем этапе здесь можно будет добавить редактирование профиля, смену пароля и персональные настройки.",
    },
    {
        "endpoint": "cabinet_history",
        "route": "/cabinet/history",
        "title": "История запросов",
        "heading": "История обращений к RAG-сервису",
        "summary": "Каркас раздела для просмотра последних запросов и метрик retrieval.",
        "content": "Пока раздел показывает последние запросы системы в демонстрационном режиме. На следующем этапе история будет привязана к конкретному пользователю.",
    },
    {
        "endpoint": "cabinet_saved_answers",
        "route": "/cabinet/saved-answers",
        "title": "Сохраненные ответы",
        "heading": "Последние ответы системы",
        "summary": "Каркас для просмотра ранее сформированных RAG-ответов.",
        "content": "Раздел подготавливает основу под будущие пользовательские подборки, сохраненные ответы и историю взаимодействия.",
    },
    {
        "endpoint": "cabinet_help",
        "route": "/cabinet/help",
        "title": "Помощь",
        "heading": "Справка по работе с кабинетом",
        "summary": "Краткие рекомендации по использованию рабочих функций и взаимодействию с системой.",
        "content": "В этом разделе собраны рекомендации по безопасной работе с системой, интерпретации RAG-ответов и обращению к администраторам или редакторам знаний.",
    },
]


ADMIN_PAGES: List[Dict] = [
    {
        "endpoint": "admin_home",
        "route": "/admin",
        "title": "Админ-панель",
        "heading": "Панель администратора",
        "summary": "Центральная страница административного контура с обзором основных сущностей системы.",
    },
    {
        "endpoint": "admin_users",
        "route": "/admin/users",
        "title": "Пользователи",
        "heading": "Учетные записи пользователей",
        "summary": "Список учетных записей и ролей, доступных в системе.",
    },
    {
        "endpoint": "admin_roles",
        "route": "/admin/roles",
        "title": "Роли",
        "heading": "Роли и разграничение доступа",
        "summary": "Справочник ролей и их текущее использование.",
    },
    {
        "endpoint": "admin_feedback",
        "route": "/admin/feedback",
        "title": "Обратная связь",
        "heading": "Сообщения обратной связи",
        "summary": "Список сообщений, отправленных через публичную форму.",
    },
    {
        "endpoint": "admin_content",
        "route": "/admin/content",
        "title": "Контент",
        "heading": "Состояние контентного слоя",
        "summary": "Краткий обзор статей, глоссария, onboarding-страниц и FAQ.",
    },
    {
        "endpoint": "admin_audit",
        "route": "/admin/audit",
        "title": "Аудит",
        "heading": "Журнал основных событий",
        "summary": "Демонстрационный журнал базовых действий, зафиксированных в приложении.",
    },
]


EDITOR_PAGES: List[Dict] = [
    {
        "endpoint": "editor_content",
        "route": "/editor/content",
        "title": "Контур редактора",
        "heading": "Рабочая зона редактора базы знаний",
        "summary": "Раздел доступен редактору знаний и администратору.",
        "content": "Здесь можно развивать функции подготовки, проверки и сопровождения контента базы знаний без доступа ко всему административному контуру.",
    }
]


def get_cabinet_pages() -> List[Dict]:
    return CABINET_PAGES


def get_admin_pages() -> List[Dict]:
    return ADMIN_PAGES


def get_editor_pages() -> List[Dict]:
    return EDITOR_PAGES


def get_page_by_endpoint(endpoint: str, pages: List[Dict]) -> Dict:
    return next(page for page in pages if page["endpoint"] == endpoint)
