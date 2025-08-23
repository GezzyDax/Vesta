FROM python:3.11-slim

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Копирование и установка Python зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование приложения
COPY . .

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