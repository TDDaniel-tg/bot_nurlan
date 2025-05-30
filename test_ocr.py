#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Тестовый скрипт для проверки OCR функциональности
"""

import os
import logging
from image_processor import ImageProcessor
from pdf_processor import PDFProcessor
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_image_processor():
    """Тестирование ImageProcessor"""
    print("🧪 Тестирование ImageProcessor...")
    
    processor = ImageProcessor()
    
    print(f"Claude API доступен: {'✅' if processor.claude_client else '❌'}")
    print(f"Tesseract доступен: {'✅' if processor.tesseract_available else '❌'}")
    
    if not processor.claude_client and not processor.tesseract_available:
        print("❌ Ни один метод OCR не доступен!")
        print("📝 Рекомендации:")
        print("   • Настройте Claude API в .env файле")
        print("   • Или установите Tesseract OCR")
        return False
    
    return True

def test_pdf_processor():
    """Тестирование PDFProcessor"""
    print("\n🧪 Тестирование PDFProcessor...")
    
    processor = PDFProcessor()
    
    # Проверяем что ImageProcessor инициализирован
    if hasattr(processor, 'image_processor'):
        print("✅ ImageProcessor успешно интегрирован")
        return True
    else:
        print("❌ ImageProcessor не интегрирован")
        return False

def show_env_status():
    """Показывает статус переменных окружения"""
    print("\n🔧 Статус переменных окружения:")
    
    bot_token = os.getenv('BOT_TOKEN')
    claude_key = os.getenv('CLAUDE_API_KEY')
    
    print(f"BOT_TOKEN: {'✅ Настроен' if bot_token and bot_token != 'your_bot_token_here' else '❌ Не настроен'}")
    print(f"CLAUDE_API_KEY: {'✅ Настроен' if claude_key and claude_key != 'your_claude_api_key_here' else '❌ Не настроен'}")
    
    if not claude_key or claude_key == 'your_claude_api_key_here':
        print("\n💡 Для настройки Claude API:")
        print("   1. Получите ключ на console.anthropic.com")
        print("   2. Добавьте в .env файл: CLAUDE_API_KEY=ваш_ключ")
        print("   3. Или см. НАСТРОЙКА_CLAUDE_API.md")

def check_dependencies():
    """Проверяет наличие всех зависимостей"""
    print("\n📦 Проверка зависимостей:")
    
    dependencies = [
        'PIL', 'cv2', 'numpy', 'pdf2image', 'anthropic'
    ]
    
    for dep in dependencies:
        try:
            __import__(dep)
            print(f"✅ {dep}")
        except ImportError:
            print(f"❌ {dep} - не установлен")
    
    # Проверка pytesseract отдельно
    try:
        import pytesseract
        try:
            pytesseract.get_tesseract_version()
            print("✅ pytesseract + Tesseract")
        except:
            print("⚠️ pytesseract установлен, но Tesseract не найден")
    except ImportError:
        print("❌ pytesseract - не установлен")

def show_usage_guide():
    """Показывает руководство по использованию"""
    print("\n📚 Руководство по использованию:")
    print("""
🚀 Для запуска бота:
   python bot.py

📄 Поддерживаемые файлы:
   • Текстовые PDF - извлечение текста
   • Сканированные PDF - OCR распознавание
   • Размер до 20 МБ

🧠 Методы распознавания:
   • Claude AI - высокая точность (платный)
   • Tesseract - базовая точность (бесплатный)

📊 Экспорт данных:
   • Текст - полное содержимое
   • Excel - структурированные таблицы

🔧 Настройка:
   • См. ИНСТРУКЦИЯ_ЗАПУСКА.md
   • См. НАСТРОЙКА_CLAUDE_API.md
""")

def main():
    """Основная функция тестирования"""
    print("🤖 PDF Bot - Тест OCR Функциональности")
    print("=" * 50)
    
    # Загружаем переменные окружения
    load_dotenv()
    
    # Проверяем зависимости
    check_dependencies()
    
    # Показываем статус окружения
    show_env_status()
    
    # Тестируем компоненты
    image_ok = test_image_processor()
    pdf_ok = test_pdf_processor()
    
    print("\n📊 Результаты тестирования:")
    print(f"ImageProcessor: {'✅' if image_ok else '❌'}")
    print(f"PDFProcessor: {'✅' if pdf_ok else '❌'}")
    
    if image_ok and pdf_ok:
        print("\n🎉 Все компоненты готовы к работе!")
        print("📄 Бот готов обрабатывать PDF документы")
    else:
        print("\n⚠️ Обнаружены проблемы с настройкой")
        print("📝 Проверьте инструкции выше")
    
    # Показываем руководство
    show_usage_guide()

if __name__ == "__main__":
    main() 