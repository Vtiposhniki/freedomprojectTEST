# Используем официальный легковесный образ Python
FROM python:3.11-slim

# Устанавливаем системные зависимости, необходимые для psycopg2 и сборки пакетов
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Задаем рабочую директорию в контейнере
WORKDIR /app

# Копируем зависимости и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь исходный код проекта
COPY . .

# Открываем порт для FastAPI
EXPOSE 8000

# По умолчанию запускаем API-сервер
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]