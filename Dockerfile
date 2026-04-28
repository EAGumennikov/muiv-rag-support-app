# Контейнер web-сервиса собирается только из исходного кода репозитория.
# Runtime-данные RAG-контура, база SQLite и секреты подключаются отдельно
# через внешний workdir, чтобы не попадать в Docker-образ и git.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Сначала устанавливаем зависимости, чтобы Docker мог переиспользовать слой
# при изменении шаблонов, статики или документации.
COPY requirements.txt ./
RUN python -m pip install --upgrade pip && \
    python -m pip install --index-url https://download.pytorch.org/whl/cpu torch==2.4.1+cpu && \
    python -m pip install -r requirements.txt

COPY . .

EXPOSE 5002

# Команда запуска задается в compose.yaml: там подгружаются секреты из workdir
# и явно указываются пути к индексам, БД и файлам корпуса внутри контейнера.
CMD ["gunicorn", "--bind", "0.0.0.0:5002", "--workers", "2", "--threads", "4", "--timeout", "180", "app:app"]
