from __future__ import annotations

"""
Справочник отраслевых и ИТ-сокращений для публичного глоссария.

На этапе 23 данные хранятся в сервисном слое: текущая SQL-модель GlossaryTerm
не содержит категории, расшифровки и примера использования. Структура записей
сделана близкой к будущему SQL-представлению, где уникальность лучше задавать
по связке term + category.
"""

from typing import Any


INDUSTRY_CATEGORY = "Отраслевой контекст"
IT_SECURITY_CATEGORY = "ИТ / ИБ-контур"


GLOSSARY_TERMS: list[dict[str, str]] = [
    {"term": "ГК «Росатом»", "expansion": "Государственная корпорация по атомной энергии «Росатом»", "category": INDUSTRY_CATEGORY, "comment": "Официальные документы, письма, регламенты.", "example": "Встречается при описании отраслевых процессов и организационного контекста."},
    {"term": "АЭС", "expansion": "атомная электрическая станция", "category": INDUSTRY_CATEGORY, "comment": "Энергетика, эксплуатация, отчетность.", "example": "Используется в материалах по эксплуатации энергоблоков."},
    {"term": "АС", "expansion": "атомная станция", "category": INDUSTRY_CATEGORY, "comment": "Эксплуатационная и проектная документация.", "example": "Важно не смешивать с ИТ-сокращением АСУ ТП."},
    {"term": "ОИАЭ", "expansion": "объект использования атомной энергии", "category": INDUSTRY_CATEGORY, "comment": "Безопасность, лицензирование, надзор.", "example": "Может встречаться в нормативных и контрольных материалах."},
    {"term": "ЯРБ", "expansion": "ядерная и радиационная безопасность", "category": INDUSTRY_CATEGORY, "comment": "Производственные и регуляторные документы.", "example": "Используется при описании требований безопасности."},
    {"term": "ЯТЦ", "expansion": "ядерный топливный цикл", "category": INDUSTRY_CATEGORY, "comment": "Топливный дивизион, стратегия, производство.", "example": "Термин связан с этапами обращения с ядерным топливом."},
    {"term": "ЗЯТЦ", "expansion": "замкнутый ядерный топливный цикл", "category": INDUSTRY_CATEGORY, "comment": "Проекты развития атомной энергетики.", "example": "Используется в материалах о перспективных технологических направлениях."},
    {"term": "ОЯТ", "expansion": "отработавшее ядерное топливо", "category": INDUSTRY_CATEGORY, "comment": "Обращение с топливом, хранение, переработка.", "example": "Встречается в темах хранения и переработки топлива."},
    {"term": "РАО", "expansion": "радиоактивные отходы", "category": INDUSTRY_CATEGORY, "comment": "Экология, безопасность, вывод из эксплуатации.", "example": "Используется в материалах об обращении с отходами."},
    {"term": "ЯМ", "expansion": "ядерные материалы", "category": INDUSTRY_CATEGORY, "comment": "Учет, контроль, безопасность.", "example": "Относится к контролю и безопасному обращению с материалами."},
    {"term": "РВ", "expansion": "радиоактивные вещества", "category": INDUSTRY_CATEGORY, "comment": "Учет, контроль, обращение с материалами.", "example": "Термин встречается в документах по безопасности и учету."},
    {"term": "ЯРОО", "expansion": "ядерно и радиационно опасные объекты", "category": INDUSTRY_CATEGORY, "comment": "Безопасность, вывод из эксплуатации.", "example": "Используется при классификации объектов и рисков."},
    {"term": "ТВЭЛ", "expansion": "тепловыделяющий элемент", "category": INDUSTRY_CATEGORY, "comment": "Топливо, производство, эксплуатация реакторов.", "example": "Базовый термин реакторного топлива."},
    {"term": "ТВС", "expansion": "тепловыделяющая сборка", "category": INDUSTRY_CATEGORY, "comment": "Реакторное топливо.", "example": "Используется при описании состава активной зоны реактора."},
    {"term": "ОТВС", "expansion": "отработавшая тепловыделяющая сборка", "category": INDUSTRY_CATEGORY, "comment": "Обращение с ОЯТ.", "example": "Встречается в контексте отработавшего топлива."},
    {"term": "ВВЭР", "expansion": "водо-водяной энергетический реактор", "category": INDUSTRY_CATEGORY, "comment": "Тип реактора.", "example": "Используется в материалах о типах энергоблоков."},
    {"term": "РБМК", "expansion": "реактор большой мощности канальный", "category": INDUSTRY_CATEGORY, "comment": "Тип реактора.", "example": "Относится к классификации реакторных установок."},
    {"term": "БН", "expansion": "реактор на быстрых нейтронах", "category": INDUSTRY_CATEGORY, "comment": "Быстрые реакторы, двухкомпонентная энергетика.", "example": "Встречается в материалах о перспективной энергетике."},
    {"term": "КИУМ", "expansion": "коэффициент использования установленной мощности", "category": INDUSTRY_CATEGORY, "comment": "Эффективность эксплуатации энергоблоков.", "example": "Показатель может использоваться в отчетности."},
    {"term": "ПСР", "expansion": "Производственная система «Росатома»", "category": INDUSTRY_CATEGORY, "comment": "Бережливое производство, улучшение процессов.", "example": "Связано с оптимизацией рабочих процессов."},
    {"term": "НИОКР", "expansion": "научно-исследовательские и опытно-конструкторские работы", "category": INDUSTRY_CATEGORY, "comment": "Наука, инновации, разработки.", "example": "Используется в проектной и научной деятельности."},
    {"term": "ФНП", "expansion": "федеральные нормы и правила", "category": INDUSTRY_CATEGORY, "comment": "Регулирование, безопасность.", "example": "Встречается в нормативном контексте."},
    {"term": "НП", "expansion": "нормы и правила", "category": INDUSTRY_CATEGORY, "comment": "Нормативная документация.", "example": "Общее обозначение нормативных документов."},
    {"term": "ЕОСДО", "expansion": "Единая отраслевая система электронного документооборота", "category": INDUSTRY_CATEGORY, "comment": "Документы, согласования, поручения.", "example": "Может упоминаться в обращениях о согласовании документов."},
    {"term": "ЕОСЗ", "expansion": "Единая отраслевая система закупок / ЕОС Закупки", "category": INDUSTRY_CATEGORY, "comment": "Закупочная деятельность.", "example": "Относится к закупочным процессам."},
    {"term": "ЕОС НСИ", "expansion": "Единая отраслевая система нормативно-справочной информации", "category": INDUSTRY_CATEGORY, "comment": "Справочники, контрагенты, оргструктура.", "example": "Связана со справочными данными."},
    {"term": "ЕОС-Качество", "expansion": "Единая отраслевая система управления качеством", "category": INDUSTRY_CATEGORY, "comment": "Качество, проверки, процессы.", "example": "Используется в контуре качества."},
    {"term": "ЕОМУ", "expansion": "Единые отраслевые методические указания", "category": INDUSTRY_CATEGORY, "comment": "Методология, регламенты, требования.", "example": "Встречается в методических материалах."},
    {"term": "ИАСУП", "expansion": "Информационная автоматизированная система управления персоналом", "category": INDUSTRY_CATEGORY, "comment": "Кадровые процессы, данные сотрудников.", "example": "Связана с кадровыми и учетными процессами."},
    {"term": "КУЦ", "expansion": "Корпоративный удостоверяющий центр Госкорпорации «Росатом»", "category": INDUSTRY_CATEGORY, "comment": "Сертификаты электронной подписи.", "example": "Может встречаться в вопросах сертификатов и подписи."},
    {"term": "ИТ", "expansion": "информационные технологии", "category": IT_SECURITY_CATEGORY, "comment": "Общий ИТ-контекст.", "example": "Используется как широкое обозначение ИТ-направления."},
    {"term": "ИС", "expansion": "информационная система", "category": IT_SECURITY_CATEGORY, "comment": "Реестры систем, доступы, сопровождение.", "example": "Часто встречается в заявках на доступ."},
    {"term": "АСУ ТП", "expansion": "автоматизированная система управления технологическим процессом", "category": IT_SECURITY_CATEGORY, "comment": "Промышленная автоматизация, производственные и технологические процессы.", "example": "Относится к промышленному ИТ-контексту."},
    {"term": "КИС", "expansion": "корпоративная информационная система", "category": IT_SECURITY_CATEGORY, "comment": "Корпоративные и отраслевые системы.", "example": "Используется в описании корпоративных сервисов."},
    {"term": "ЛИС", "expansion": "локальная информационная система", "category": IT_SECURITY_CATEGORY, "comment": "Системы уровня организации или площадки.", "example": "Может отличаться от корпоративной системы по масштабу."},
    {"term": "ПО", "expansion": "программное обеспечение", "category": IT_SECURITY_CATEGORY, "comment": "Установка, сопровождение, лицензии.", "example": "Базовый термин для заявок по программам."},
    {"term": "СПО", "expansion": "системное программное обеспечение", "category": IT_SECURITY_CATEGORY, "comment": "ОС, драйверы, базовое ПО.", "example": "Встречается при обслуживании рабочих мест."},
    {"term": "ОС", "expansion": "операционная система", "category": IT_SECURITY_CATEGORY, "comment": "Astra Linux, Windows, импортозамещение.", "example": "Используется при описании среды пользователя."},
    {"term": "АРМ", "expansion": "автоматизированное рабочее место", "category": IT_SECURITY_CATEGORY, "comment": "Рабочие места пользователей.", "example": "Часто встречается в заявках на настройку рабочего места."},
    {"term": "РМ", "expansion": "рабочее место", "category": IT_SECURITY_CATEGORY, "comment": "Поддержка, инвентаризация, бронирование.", "example": "Общее обозначение рабочего места пользователя."},
    {"term": "СУ ИТ", "expansion": "система управления ИТ-услугами", "category": IT_SECURITY_CATEGORY, "comment": "Заявки, инциденты, обращения пользователей.", "example": "Связана с обработкой обращений службы поддержки."},
    {"term": "СУЗ", "expansion": "система управления знаниями", "category": IT_SECURITY_CATEGORY, "comment": "База знаний, инструкции, поиск решений.", "example": "Класс систем, к которому относится текущий web-сервис."},
    {"term": "БЗ", "expansion": "база знаний", "category": IT_SECURITY_CATEGORY, "comment": "Поддержка пользователей, инструкции, типовые решения.", "example": "Источник решений для первой линии поддержки."},
    {"term": "SLA", "expansion": "Service Level Agreement - соглашение об уровне сервиса", "category": IT_SECURITY_CATEGORY, "comment": "Сроки реакции и решения.", "example": "Используется для контроля качества ИТ-услуг."},
    {"term": "OLA", "expansion": "Operational Level Agreement - внутреннее соглашение об уровне сервиса", "category": IT_SECURITY_CATEGORY, "comment": "Взаимодействие между ИТ-подразделениями.", "example": "Помогает разграничить внутренние сроки исполнения."},
    {"term": "ВКС", "expansion": "видеоконференцсвязь", "category": IT_SECURITY_CATEGORY, "comment": "Переговорные, совещания, оборудование.", "example": "Часто встречается в заявках по совещаниям."},
    {"term": "СКС", "expansion": "структурированная кабельная система", "category": IT_SECURITY_CATEGORY, "comment": "Сеть, порты, коммутация.", "example": "Используется при диагностике сетевых подключений."},
    {"term": "ЛВС", "expansion": "локальная вычислительная сеть", "category": IT_SECURITY_CATEGORY, "comment": "Сеть на площадке или в офисе.", "example": "Базовый термин сетевой инфраструктуры."},
    {"term": "КСПД", "expansion": "корпоративная сеть передачи данных", "category": IT_SECURITY_CATEGORY, "comment": "Межплощадочная сеть, корпоративный контур.", "example": "Встречается в сетевом и корпоративном контексте."},
    {"term": "ЦОД", "expansion": "центр обработки данных", "category": IT_SECURITY_CATEGORY, "comment": "Серверная инфраструктура.", "example": "Связан с размещением серверов и сервисов."},
    {"term": "ВМ", "expansion": "виртуальная машина", "category": IT_SECURITY_CATEGORY, "comment": "Серверы, тестовые среды, VDI.", "example": "Используется в инфраструктурных заявках."},
    {"term": "VDI", "expansion": "Virtual Desktop Infrastructure - инфраструктура виртуальных рабочих столов", "category": IT_SECURITY_CATEGORY, "comment": "Удаленные рабочие места, виртуальные АРМ.", "example": "Связано с виртуальными рабочими местами."},
    {"term": "AD", "expansion": "Active Directory", "category": IT_SECURITY_CATEGORY, "comment": "Учетные записи, группы, политики.", "example": "Часто встречается при заявках на доступы."},
    {"term": "УЗ", "expansion": "учетная запись", "category": IT_SECURITY_CATEGORY, "comment": "Доступы, блокировки, права.", "example": "Базовый объект поддержки пользователей."},
    {"term": "VPN", "expansion": "Virtual Private Network - защищенное сетевое подключение", "category": IT_SECURITY_CATEGORY, "comment": "Удаленный доступ.", "example": "Используется при удаленной работе."},
    {"term": "RDP", "expansion": "Remote Desktop Protocol - протокол удаленного рабочего стола", "category": IT_SECURITY_CATEGORY, "comment": "Подключение к удаленным рабочим столам.", "example": "Встречается в заявках по удаленному подключению."},
    {"term": "ИБ", "expansion": "информационная безопасность", "category": IT_SECURITY_CATEGORY, "comment": "Требования, согласования, ограничения.", "example": "Связано с политиками защиты информации."},
    {"term": "СЗИ", "expansion": "средство защиты информации", "category": IT_SECURITY_CATEGORY, "comment": "Защита информации, сертификация, контроль.", "example": "Используется в ИБ-контуре."},
    {"term": "СКЗИ", "expansion": "средство криптографической защиты информации", "category": IT_SECURITY_CATEGORY, "comment": "Подпись, шифрование, защищенные каналы.", "example": "Встречается в темах электронной подписи и защиты каналов."},
    {"term": "ПДн", "expansion": "персональные данные", "category": IT_SECURITY_CATEGORY, "comment": "Обработка и защита данных.", "example": "Требует аккуратного обращения и соблюдения правил защиты."},
    {"term": "СЗПДн", "expansion": "система защиты персональных данных", "category": IT_SECURITY_CATEGORY, "comment": "Защита ИС с персональными данными.", "example": "Используется в ИБ-документации."},
    {"term": "КИИ", "expansion": "критическая информационная инфраструктура", "category": IT_SECURITY_CATEGORY, "comment": "Категорирование и защита объектов.", "example": "Термин относится к отдельному регуляторному контуру."},
    {"term": "ЗОКИИ", "expansion": "значимый объект критической информационной инфраструктуры", "category": IT_SECURITY_CATEGORY, "comment": "ИБ, категорирование, аудит.", "example": "Используется в материалах по КИИ."},
    {"term": "КЭП", "expansion": "квалифицированная электронная подпись", "category": IT_SECURITY_CATEGORY, "comment": "Подписание документов.", "example": "Встречается в задачах электронного документооборота."},
    {"term": "УКЭП", "expansion": "усиленная квалифицированная электронная подпись", "category": IT_SECURITY_CATEGORY, "comment": "Юридически значимый электронный документооборот.", "example": "Используется при подписании документов."},
    {"term": "МЧД", "expansion": "машиночитаемая доверенность", "category": IT_SECURITY_CATEGORY, "comment": "Подписание от имени организации.", "example": "Связана с полномочиями подписанта."},
    {"term": "ПДС", "expansion": "платформа доверенных сервисов", "category": IT_SECURITY_CATEGORY, "comment": "Электронная подпись, МЧД, доверенные сервисы.", "example": "Может встречаться в задачах доверенного документооборота."},
    {"term": "ЭДО", "expansion": "электронный документооборот", "category": IT_SECURITY_CATEGORY, "comment": "Договоры, письма, согласования.", "example": "Общий контур работы с электронными документами."},
    {"term": "ЭП", "expansion": "электронная подпись", "category": IT_SECURITY_CATEGORY, "comment": "Подписание документов.", "example": "Базовый термин для сертификатов и подписания."},
    {"term": "УЦ", "expansion": "удостоверяющий центр", "category": IT_SECURITY_CATEGORY, "comment": "Выпуск и сопровождение сертификатов.", "example": "Используется в задачах электронной подписи."},
    {"term": "СЭД", "expansion": "система электронного документооборота", "category": IT_SECURITY_CATEGORY, "comment": "Документооборот, согласование документов.", "example": "Встречается в заявках по работе с документами."},
    {"term": "МФУ", "expansion": "многофункциональное устройство", "category": IT_SECURITY_CATEGORY, "comment": "Печать, сканирование, копирование.", "example": "Типовая зона поддержки первой линии."},
    {"term": "СУБД", "expansion": "система управления базами данных", "category": IT_SECURITY_CATEGORY, "comment": "Хранение и обработка данных.", "example": "Используется при описании серверных приложений."},
    {"term": "API", "expansion": "Application Programming Interface - программный интерфейс приложения", "category": IT_SECURITY_CATEGORY, "comment": "Интеграции между системами.", "example": "Встречается при обмене данными между сервисами."},
    {"term": "LDAP", "expansion": "Lightweight Directory Access Protocol - протокол доступа к каталогам", "category": IT_SECURITY_CATEGORY, "comment": "Каталоги пользователей, авторизация.", "example": "Может использоваться в задачах аутентификации."},
    {"term": "DNS", "expansion": "Domain Name System - система доменных имен", "category": IT_SECURITY_CATEGORY, "comment": "Сетевые имена, доступность ресурсов.", "example": "Проверяется командами nslookup или dig."},
    {"term": "DHCP", "expansion": "Dynamic Host Configuration Protocol - протокол автоматической настройки сети", "category": IT_SECURITY_CATEGORY, "comment": "Выдача IP-адресов.", "example": "Полезно при диагностике сетевых параметров."},
    {"term": "NTP", "expansion": "Network Time Protocol - протокол синхронизации времени", "category": IT_SECURITY_CATEGORY, "comment": "Синхронизация времени в инфраструктуре.", "example": "Важен для корректной работы доменных и защищенных сервисов."},
    {"term": "MFA", "expansion": "Multi-Factor Authentication - многофакторная аутентификация", "category": IT_SECURITY_CATEGORY, "comment": "Защита учетных записей.", "example": "Используется для повышения безопасности входа."},
    {"term": "SSO", "expansion": "Single Sign-On - единый вход", "category": IT_SECURITY_CATEGORY, "comment": "Сквозная авторизация в системах.", "example": "Позволяет пользователю входить в несколько систем через единый механизм."},
]


def get_glossary_terms() -> list[dict[str, str]]:
    # Порядок сохраняет смешанную демонстрационную витрину, а не сухую
    # алфавитную выдачу: сначала отраслевой контекст, затем ИТ / ИБ.
    return list(GLOSSARY_TERMS)


def get_glossary_terms_by_category() -> list[dict[str, Any]]:
    # Для главного вида глоссария термины группируются в две колонки,
    # чтобы отраслевые и ИТ-сокращения читались параллельно.
    groups = []
    for category in (INDUSTRY_CATEGORY, IT_SECURITY_CATEGORY):
        groups.append(
            {
                "category": category,
                "items": [item for item in GLOSSARY_TERMS if item["category"] == category],
            }
        )
    return groups


def get_glossary_categories() -> list[str]:
    return sorted({item["category"] for item in GLOSSARY_TERMS})


def get_glossary_statistics() -> list[dict[str, Any]]:
    return [
        {"label": "Термины глоссария", "value": len(GLOSSARY_TERMS), "note": "Демонстрационное наполнение"},
        {"label": "Категории", "value": len(get_glossary_categories()), "note": "Отраслевой и ИТ / ИБ-контур"},
    ]
