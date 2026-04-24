#!/bin/bash
set -euo pipefail

# Этот скрипт сохраняет старый CLI-сценарий работы с RAG-пайплайном.
# Он нужен отдельно от веб-приложения, чтобы учебный проект можно было
# запускать и проверять как через Flask, так и через командную строку.

REPO_DIR="$HOME/Projects/muiv-rag-support-app"
WORKDIR="$HOME/Projects/muiv-rag-support-workdir"

# Проверки ниже помогают явно показать, что runtime и секреты хранятся
# не в репозитории, а во внешнем рабочем каталоге.
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
# Сценарий запуска совпадает с веб-скриптом по окружению, но вместо Flask
# вызывается CLI-пайплайн генерации ответа.
source .venv/bin/activate
source "$WORKDIR/.env.yc"
source "$WORKDIR/.env.local"

python scripts/generate_answer_pipeline.py "$@"
