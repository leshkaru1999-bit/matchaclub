FROM cr.yandex/mirror/library/python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код в контейнер
COPY . .

# Создаем директорию для базы данных, если ее нет
RUN mkdir -p /app/data

# Экспонируем порт для FastAPI
EXPOSE 8000

# Запускаем сразу и FastAPI сервер, и Telegram бота
# Для этого мы используем скрипт, который запускает bot.py
CMD ["python", "bot.py"]
