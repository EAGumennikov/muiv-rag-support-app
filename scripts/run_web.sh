#!/bin/bash
set -euo pipefail

# Скрипт запускает веб-контур проекта в локальной учебной конфигурации.
# Здесь намеренно используется разделение repo + workdir: код живет в репозитории,
# а секреты и runtime-настройки подтягиваются из внешнего рабочего каталога.

REPO_DIR="$HOME/Projects/muiv-rag-support-app"
WORKDIR="$HOME/Projects/muiv-rag-support-workdir"

# До запуска проверяем базовые зависимости среды, чтобы пользователь получил
# понятную ошибку сразу, а не уже внутри Flask-приложения.
if [ ! -d "$REPO_DIR/.venv" ]; then
  echo "Ошибка: не найдено виртуальное окружение $REPO_DIR/.venv"
  exit 1
fi

if [ ! -f "$WORKDIR/.env.yc" ]; then
  echo "Ошибка: не найден файл $WORKDIR/.env.yc"
  exit 1
fi

if [ ! -f "$WORKDIR/.env.local" ]; then
  echo "Ошибка: не найден файл $WORKDIR/.env.local"
  exit 1
fi

cd "$REPO_DIR"
# Активируем окружение и подгружаем переменные, которые нужны и для SQL-слоя,
# и для вызова внешней LLM через Yandex AI Studio.
source .venv/bin/activate
source "$WORKDIR/.env.yc"
source "$WORKDIR/.env.local"

python3 app.py
