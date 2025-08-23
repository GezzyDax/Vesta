FROM python:3.11-slim

WORKDIR /app

# Build arguments for git info
ARG GIT_COMMIT=unknown
ARG GIT_BRANCH=unknown
ARG BUILD_DATE=unknown

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Копирование и установка Python зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование приложения
COPY . .

# Create build info file with git information
RUN echo "{ \
    \"git_commit\": \"$GIT_COMMIT\", \
    \"git_branch\": \"$GIT_BRANCH\", \
    \"build_date\": \"$BUILD_DATE\" \
}" > /app/build_info.json

# Создание пользователя и настройка прав
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/instance && \
    chown -R appuser:appuser /app && \
    chmod 755 /app/instance

USER appuser

# Переменные окружения
ENV FLASK_APP=run.py
ENV FLASK_ENV=production

# Открытие порта
EXPOSE 5000

# Команда запуска
CMD ["python", "run.py"]