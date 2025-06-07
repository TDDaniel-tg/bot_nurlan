#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path
import hashlib
from flask import Flask
import threading

# Импорты Telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# Импорт PDF обработчика
from pdf_processor import PDFProcessor

# Загрузка переменных окружения
load_dotenv()

# Получение токенов
BOT_TOKEN = os.getenv('BOT_TOKEN')
CLAUDE_API_KEY = os.getenv('CLAUDE_API_KEY')

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы
ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))

# Проверка конфигурации
if not BOT_TOKEN:
    logger.error("BOT_TOKEN не найден в переменных окружения!")
    exit(1)

if not CLAUDE_API_KEY:
    logger.warning("CLAUDE_API_KEY не найден. OCR через Claude API будет недоступен.")

logger.info("Бот запускается...")

class DocumentBot:
    def __init__(self):
        self.pdf_processor = PDFProcessor()

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.effective_user
        welcome_text = f"""
👋 Привет, {user.first_name}!

🤖 Я бот для работы с PDF документами.

📋 **Мои возможности:**
• 📄 Извлечение текста из PDF
• 🔢 Подсчет страниц
• 📊 Экспорт таблиц в Excel
• 💾 Сохранение результатов

📝 **Как пользоваться:**
1. Отправьте мне PDF файл
2. Выберите нужную операцию
3. Получите результат

🆘 Команды:
/help - помощь
/status - статус бота
        """
        
        keyboard = [
            [InlineKeyboardButton("📖 Инструкция", callback_data="help")],
            [InlineKeyboardButton("📊 Статистика", callback_data="stats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = """🤖 **PDF Обработчик Бот - Помощь**

**Возможности бота:**
📄 Извлечение текста из PDF документов
📊 Распознавание и экспорт таблиц в Excel
📸 Обработка сканированных документов (OCR)
🔄 Поддержка различных форматов PDF

**Поддерживаемые типы PDF:**
• **Текстовые PDF** - документы с выделяемым текстом
• **Сканированные PDF** - отсканированные изображения документов
• **Смешанные PDF** - содержащие и текст, и изображения

**Как использовать:**
1. Отправьте PDF файл боту
2. Дождитесь обработки
3. Получите извлеченный текст
4. При наличии таблиц - экспортируйте в Excel

**Функции распознавания:**
• **Claude AI** - высокоточное распознавание текста и таблиц
• **Tesseract OCR** - базовое распознавание (резервный метод)

**Поддерживаемые языки:**
• Русский
• Английский
• Смешанные тексты

**Форматы экспорта:**
📊 Excel (.xlsx) - для табличных данных
📄 Текст - полное содержимое документа

**Ограничения:**
• Максимальный размер файла: 20 МБ
• Время обработки: до 5 минут
• Защищенные паролем PDF не поддерживаются

**Команды:**
/start - Запуск бота
/help - Эта справка

**Техническая поддержка:**
При возникновении проблем отправьте описание ошибки администратору."""

        keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="start")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(help_text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(help_text, reply_markup=reply_markup)

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /status"""
        status_text = f"""
📊 **Статус бота**

✅ Бот работает нормально
🕐 Время: {datetime.now().strftime('%H:%M:%S')}
📅 Дата: {datetime.now().strftime('%d.%m.%Y')}

🔧 **Технические характеристики:**
• Python версия: 3.13
• Telegram Bot API: {context.bot.api_version if hasattr(context.bot, 'api_version') else 'N/A'}
• PDF обработчик: активен

👥 **Пользователи:**
• Активных сессий: {len(context.user_data) // 2}
        """
        await update.message.reply_text(status_text)

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик для полученных документов"""
        try:
            # Получаем информацию о файле
            document = update.message.document
            
            if not document.file_name.lower().endswith('.pdf'):
                await update.message.reply_text("❌ Пожалуйста, отправьте PDF файл.")
                return
            
            # Отправляем сообщение о начале обработки
            processing_message = await update.message.reply_text("📄 Получен PDF файл. Начинаю обработку...")
            
            # Скачиваем файл
            file = await context.bot.get_file(document.file_id)
            file_path = f"downloads/{document.file_name}"
            
            # Создаем папку downloads если она не существует
            os.makedirs("downloads", exist_ok=True)
            
            await file.download_to_drive(file_path)
            
            # Обновляем сообщение
            await processing_message.edit_text("🔍 Анализирую содержимое PDF...")
            
            # Обрабатываем PDF
            pdf_processor = PDFProcessor()
            result = pdf_processor.process_pdf(file_path)
            
            if result['success']:
                # Определяем метод обработки для пользователя
                method_info = ""
                if "OCR" in result.get('method', ''):
                    if "Claude API" in result.get('method', ''):
                        method_info = "📸 Обнаружен сканированный документ. Использовано распознавание Claude AI."
                    else:
                        method_info = "📸 Обнаружен сканированный документ. Использовано OCR распознавание."
                else:
                    method_info = "📝 Обработан текстовый PDF документ."
                
                # Формируем ответ
                response_text = f"""✅ PDF обработан успешно!

{method_info}

📊 **Статистика:**
• Страниц: {result['pages']}
• Символов текста: {len(result['text']) if result['text'] else 0}
• Найдено записей в таблицах: {len(result.get('tables', []))}

📄 **Извлеченный текст:**
{result['text'][:2000]}{'...' if len(result['text']) > 2000 else ''}"""
                
                # Создаем короткий идентификатор для callback
                short_id = hashlib.md5(document.file_id.encode()).hexdigest()[:8]
                
                # Создаем клавиатуру с кнопками
                keyboard = []
                
                # Показываем количество найденных таблиц для диагностики
                tables_count = len(result.get('tables', []))
                logger.info(f"Найдено таблиц: {tables_count}")
                
                # Кнопка для экспорта в Excel (показываем всегда для возможности извлечения таблиц)
                keyboard.append([InlineKeyboardButton("📊 Экспорт в Excel", callback_data=f"excel_{short_id}")])
                
                # Кнопка для получения полного текста
                if len(result['text']) > 2000:
                    keyboard.append([InlineKeyboardButton("📄 Получить полный текст", callback_data=f"text_{short_id}")])
                
                # Кнопка помощи
                keyboard.append([InlineKeyboardButton("ℹ️ Помощь", callback_data="help")])
                
                reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
                
                # Обновляем сообщение с результатом
                await processing_message.edit_text(response_text, reply_markup=reply_markup)
                
                # Сохраняем результат для дальнейшего использования с коротким ID
                context.user_data[f'pdf_result_{short_id}'] = result
                context.user_data[f'pdf_path_{short_id}'] = file_path
                context.user_data[f'pdf_filename_{short_id}'] = document.file_name or f"document_{short_id}.pdf"
                
            else:
                error_msg = f"""❌ Ошибка при обработке PDF

**Детали ошибки:** {result.get('error', 'Неизвестная ошибка')}

**Возможные причины:**
• PDF файл поврежден или защищен паролем
• Файл содержит только изображения (требуется настройка OCR)
• Проблемы с доступом к файлу

**Рекомендации:**
• Убедитесь, что PDF не защищен паролем
• Попробуйте другой PDF файл
• Обратитесь к администратору если проблема повторяется"""
                
                keyboard = [[InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await processing_message.edit_text(error_msg, reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Ошибка обработки документа: {e}")
            await update.message.reply_text(f"❌ Произошла ошибка при обработке файла: {str(e)}")
        
        finally:
            # Очищаем файл через некоторое время (но не сразу, так как он может понадобиться для экспорта)
            if 'file_path' in locals():
                # Планируем удаление файла через 30 минут
                context.job_queue.run_once(
                    lambda context: self.cleanup_file(file_path),
                    30 * 60,  # 30 минут
                    name=f"cleanup_{document.file_id}"
                )

    def cleanup_file(self, file_path: str):
        """Удаляет временный файл"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Удален временный файл: {file_path}")
        except Exception as e:
            logger.error(f"Ошибка удаления файла {file_path}: {e}")

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик callback кнопок"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = update.effective_user.id
        
        if data == "help":
            await self.help_command(update, context)
            
        elif data == "stats":
            await self.status_command(update, context)
            
        elif data.startswith("text_"):
            # Получение полного текста
            short_id = data.replace("text_", "")
            
            # Проверяем есть ли данные
            result_key = f'pdf_result_{short_id}'
            if result_key not in context.user_data:
                await query.edit_message_text("❌ Данные не найдены или устарели.")
                return
                
            result = context.user_data[result_key]
            text = result['text']
            filename = context.user_data.get(f'pdf_filename_{short_id}', 'document.pdf')
            
            if len(text) > 4000:
                # Отправка длинного текста файлом
                await query.edit_message_text("📄 Текст слишком длинный, отправляю файлом...")
                
                txt_file = f"text_{user_id}_{short_id}.txt"
                with open(txt_file, 'w', encoding='utf-8') as f:
                    f.write(text)
                
                with open(txt_file, 'rb') as f:
                    await context.bot.send_document(
                        chat_id=query.message.chat_id,
                        document=f,
                        filename=f"{filename}_extracted.txt",
                        caption="💾 Полный извлеченный текст из PDF"
                    )
                
                os.remove(txt_file)
                await query.edit_message_text("✅ Файл с полным текстом отправлен!")
            else:
                await query.edit_message_text(f"📄 **Полный извлеченный текст:**\n\n{text}")
                
        elif data.startswith("excel_"):
            # Экспорт в Excel
            short_id = data.replace("excel_", "")
            
            # Проверяем есть ли данные
            result_key = f'pdf_result_{short_id}'
            path_key = f'pdf_path_{short_id}'
            if result_key not in context.user_data or path_key not in context.user_data:
                await query.edit_message_text("❌ Данные не найдены или устарели.")
                return
                
            await query.edit_message_text("🔄 Создаю Excel файл...")
            
            try:
                result = context.user_data[result_key]
                file_path = context.user_data[path_key]
                filename = context.user_data.get(f'pdf_filename_{short_id}', 'document.pdf')
                
                # Используем таблицы из результата OCR если есть
                table_data = result.get('tables', [])
                ocr_tables_count = len(table_data)
                logger.info(f"Таблиц из OCR: {ocr_tables_count}")
                
                # Если таблиц нет в результате OCR, пробуем извлечь стандартным методом
                if not table_data:
                    logger.info("Пробую извлечь таблицы стандартным методом...")
                    table_data = await asyncio.to_thread(
                        self.pdf_processor.extract_table_from_pdf, 
                        file_path
                    )
                    standard_tables_count = len(table_data) if table_data else 0
                    logger.info(f"Таблиц стандартным методом: {standard_tables_count}")
                
                if not table_data:
                    # Также пробуем извлечь данные из текста
                    logger.info("Пробую извлечь структурированные данные из текста...")
                    text_data = await asyncio.to_thread(
                        self.pdf_processor._extract_from_text,
                        result.get('text', '')
                    )
                    if text_data:
                        table_data = text_data
                        logger.info(f"Данных из текста: {len(table_data)}")
                
                if not table_data:
                    await query.edit_message_text(
                        "❌ Структурированные данные не найдены в PDF.\n\n"
                        "Возможные причины:\n"
                        "• PDF содержит только обычный текст без таблиц\n" 
                        "• Таблицы в сложном формате\n"
                        "• Неструктурированные данные\n\n"
                        f"📊 Попытки извлечения:\n"
                        f"• OCR таблицы: {ocr_tables_count}\n"
                        f"• Стандартные таблицы: {len(table_data) if 'standard_tables_count' in locals() else 0}\n"
                        f"• Данные из текста: проверено"
                    )
                    return
                
                # Создаем Excel файл
                excel_filename = f"excel_{user_id}_{short_id}.xlsx"
                await asyncio.to_thread(
                    self.pdf_processor.create_excel_from_data,
                    table_data,
                    excel_filename
                )
                
                # Отправляем Excel файл
                with open(excel_filename, 'rb') as f:
                    await context.bot.send_document(
                        chat_id=query.message.chat_id,
                        document=f,
                        filename=f"{filename.replace('.pdf', '')}_extracted.xlsx",
                        caption=f"📊 Excel файл готов!\n\n"
                               f"📝 Найдено записей: {len(table_data)}\n"
                               f"📄 Исходный файл: {filename}"
                    )
                
                # Удаляем временные файлы
                os.remove(excel_filename)
                
                await query.edit_message_text("✅ Excel файл отправлен!")
                
            except Exception as e:
                logger.error(f"Ошибка создания Excel: {e}")
                await query.edit_message_text(
                    f"❌ Ошибка при создании Excel:\n{str(e)}\n\n"
                    "Попробуйте отправить файл повторно."
                )

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик ошибок"""
        error_message = str(context.error)
        
        # Обрабатываем конфликт экземпляров
        if "Conflict: terminated by other getUpdates request" in error_message:
            logger.warning("Обнаружен конфликт экземпляров бота - игнорируем")
            return
        
        # Обрабатываем другие ошибки
        logger.error(f"Ошибка: {context.error}")
        
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Произошла внутренняя ошибка. Попробуйте позже."
            )

def main():
    """Основная функция запуска бота"""
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN не найден в .env файле")
        return
    
    print("🚀 Запуск бота...")
    
    # Создание экземпляра бота
    bot = DocumentBot()
    
    # Создание приложения с обработкой конфликтов
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрация обработчиков
    app.add_handler(CommandHandler("start", bot.start))
    app.add_handler(CommandHandler("help", bot.help_command))
    app.add_handler(CommandHandler("status", bot.status_command))
    app.add_handler(MessageHandler(filters.Document.PDF, bot.handle_document))
    app.add_handler(CallbackQueryHandler(bot.handle_callback))
    
    # Обработчик ошибок
    app.add_error_handler(bot.error_handler)
    
    print("✅ Бот запущен и готов к работе!")
    
    # Запуск бота с обработкой конфликтов
    try:
        app.run_polling(
            drop_pending_updates=True,  # Игнорируем старые обновления
            close_loop=False
        )
    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}")
        print(f"❌ Ошибка запуска: {e}")
        print("🔄 Попробуйте перезапустить бота через несколько секунд")

app = Flask(__name__)

@app.route("/")
def healthcheck():
    return "OK", 200

def run_flask():
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

if __name__ == '__main__':
    # Запуск Flask healthcheck в отдельном потоке
    threading.Thread(target=run_flask, daemon=True).start()
    main() 