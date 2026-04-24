#!/bin/bash
set -euo pipefail

REPO_DIR="$HOME/Projects/muiv-rag-support-app"
WORKDIR="$HOME/Projects/muiv-rag-support-workdir"

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
source .venv/bin/activate
source "$WORKDIR/.env.yc"
source "$WORKDIR/.env.local"

python scripts/generate_answer_pipeline.py "$@"
