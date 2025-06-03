FROM python:3.11

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    poppler-utils \
    libpoppler-dev \
    && rm -rf /var/lib/apt/lists/*

# Проверка установки poppler
RUN which pdftoppm && pdftoppm -v

# Копируем файлы проекта
WORKDIR /app
COPY . .

# Установка зависимостей Python
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Переменные окружения для pdf2image
ENV PDF2IMAGE_USE_POPPLER_PATH=/usr/bin

# Запуск бота
CMD ["python", "bot.py"] 