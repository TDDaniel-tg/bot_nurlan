FROM python:3.11

# Установка poppler-utils для pdf2image
RUN apt-get update && apt-get install -y poppler-utils

# Копируем файлы проекта
WORKDIR /app
COPY . .

# Установка зависимостей
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Запуск бота
CMD ["python", "bot.py"] 