import os
import base64
import logging
import io
from typing import List, Dict, Optional
import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
from pdf2image import convert_from_path
import anthropic
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Путь к локальному poppler
POPPLER_PATH = os.path.join(os.path.dirname(__file__), "poppler", "poppler-24.08.0", "Library", "bin")

# Проверяем, где мы запущены - локально или на сервере
if os.path.exists(POPPLER_PATH):
    # Локальная разработка на Windows
    USE_POPPLER_PATH = POPPLER_PATH
else:
    # На сервере (Railway/Linux) - используем системный poppler
    USE_POPPLER_PATH = None  # None означает использовать системный путь

class ImageProcessor:
    def __init__(self):
        self.claude_client = None
        self.tesseract_available = False
        self.setup_claude()
        self.setup_tesseract()
    
    def setup_claude(self):
        """Настройка Claude API"""
        claude_api_key = os.getenv('CLAUDE_API_KEY')
        if claude_api_key and claude_api_key != 'your_claude_api_key_here':
            try:
                self.claude_client = anthropic.Anthropic(api_key=claude_api_key)
                logger.info("Claude API настроен успешно")
            except Exception as e:
                logger.warning(f"Ошибка настройки Claude API: {e}")
        else:
            logger.warning("CLAUDE_API_KEY не найден в .env или не настроен")
    
    def setup_tesseract(self):
        """Настройка Tesseract OCR"""
        try:
            # Попытка импортировать pytesseract
            import pytesseract
            
            # Проверка работы Tesseract
            pytesseract.get_tesseract_version()
            self.tesseract_available = True
            logger.info("Tesseract OCR настроен успешно")
        except Exception as e:
            self.tesseract_available = False
            logger.warning(f"Tesseract недоступен: {e}")
    
    def is_scanned_pdf(self, pdf_path: str) -> bool:
        """
        Определяет, является ли PDF сканированным документом
        """
        try:
            # Конвертируем первую страницу в изображение
            if USE_POPPLER_PATH:
                images = convert_from_path(pdf_path, first_page=1, last_page=1, dpi=150, poppler_path=USE_POPPLER_PATH)
            else:
                images = convert_from_path(pdf_path, first_page=1, last_page=1, dpi=150)
            
            if not images:
                return False
            
            # Анализируем изображение
            img_array = np.array(images[0])
            
            # Проверяем разнообразие цветов (сканы обычно имеют много градаций)
            unique_colors = len(np.unique(img_array.reshape(-1, img_array.shape[-1]), axis=0))
            
            # Если много уникальных цветов, вероятно это скан
            return unique_colors > 1000
            
        except Exception as e:
            logger.error(f"Ошибка определения типа PDF: {e}")
            return False
    
    def enhance_image(self, image: Image.Image) -> Image.Image:
        """
        Улучшает качество изображения для лучшего OCR
        """
        try:
            # Конвертируем в RGB если нужно
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Увеличиваем контрастность
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(1.5)
            
            # Увеличиваем резкость
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(2.0)
            
            # Применяем фильтр для удаления шума
            image = image.filter(ImageFilter.MedianFilter())
            
            return image
            
        except Exception as e:
            logger.error(f"Ошибка улучшения изображения: {e}")
            return image
    
    def extract_text_with_tesseract(self, image: Image.Image) -> str:
        """
        Извлекает текст из изображения с помощью Tesseract OCR
        """
        if not self.tesseract_available:
            return ""
            
        try:
            import pytesseract
            
            # Улучшаем изображение
            enhanced_image = self.enhance_image(image)
            
            # Настройки Tesseract для лучшего распознавания русского текста
            custom_config = r'--oem 3 --psm 6 -l rus+eng'
            
            # Извлекаем текст
            text = pytesseract.image_to_string(enhanced_image, config=custom_config)
            
            return text.strip()
            
        except Exception as e:
            logger.error(f"Ошибка Tesseract OCR: {e}")
            return ""
    
    def extract_text_with_claude(self, image: Image.Image) -> str:
        """
        Извлекает текст из изображения с помощью Claude API
        """
        if not self.claude_client:
            return ""
        
        try:
            # Конвертируем изображение в base64
            buffer = io.BytesIO()
            # Конвертируем в RGB если нужно
            if image.mode not in ['RGB', 'RGBA']:
                image = image.convert('RGB')
            image.save(buffer, format='PNG')
            image_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            # Запрос к Claude 4 Sonnet со streaming
            with self.claude_client.messages.stream(
                model="claude-sonnet-4-20250514",
                max_tokens=64000,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": image_data
                                }
                            },
                            {
                                "type": "text",
                                "text": """Ты - эксперт по извлечению данных из PDF документов. Проанализируй это изображение страницы PDF и извлеки ВЕСЬ текст с максимальной точностью.

КРИТИЧЕСКИЕ ТРЕБОВАНИЯ:
🔒 ИМЕНА И ПЕРСОНАЛЬНЫЕ ДАННЫЕ:
- Сохраняй все имена, фамилии, отчества ТОЧНО как написано
- НЕ исправляй орфографию в именах
- НЕ переводи имена на другие языки
- Сохраняй все символы, пробелы, дефисы, точки в именах

📋 ПОЛНОТА ИЗВЛЕЧЕНИЯ:
- Извлекай АБСОЛЮТНО ВСЕ текстовые данные с изображения
- Включай заголовки, подзаголовки, номера, коды
- Не пропускай мелкий текст, сноски, примечания
- Извлекай все числа, даты, адреса полностью

📊 СТРУКТУРА:
- Сохраняй исходное форматирование и структуру
- Если есть таблицы - передавай их точно построчно
- Сохраняй последовательность элементов на странице
- Обозначай разделы и границы данных

🎯 КАЧЕСТВО:
- Если символ неразборчив - используй наиболее вероятный
- При сомнениях в написании - выбирай вариант ближе к оригиналу
- Не добавляй пояснения или комментарии
- Отвечай только чистым извлеченным текстом

Извлеки ВЕСЬ текст с изображения:"""
                            }
                        ]
                    }
                ],
                temperature=0
            ) as stream:
                text_result = ""
                for text in stream.text_stream:
                    text_result += text
                
                return text_result.strip()
            
        except Exception as e:
            logger.error(f"Ошибка Claude API: {e}")
            return ""
    
    def extract_tables_with_claude(self, image: Image.Image) -> List[Dict]:
        """
        Извлекает таблицы из изображения с помощью Claude API
        """
        if not self.claude_client:
            return []
        
        try:
            # Конвертируем изображение в base64
            buffer = io.BytesIO()
            if image.mode not in ['RGB', 'RGBA']:
                image = image.convert('RGB')
            image.save(buffer, format='PNG')
            image_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            # Запрос к Claude 4 Sonnet для извлечения таблиц со streaming
            with self.claude_client.messages.stream(
                model="claude-sonnet-4-20250514",
                max_tokens=64000,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png", 
                                    "data": image_data
                                }
                            },
                            {
                                "type": "text",
                                "text": """Ты - профессиональный аналитик данных, специализирующийся на извлечении информации из PDF документов. Проанализируй это изображение и извлеки ВСЮ структурированную информацию с максимальной полнотой.

🔍 АНАЛИЗ ДОКУМЕНТА:
Определи тип документа и извлеки АБСОЛЮТНО ВСЕ структурированные данные, не пропуская ни одной записи.

📋 ДЛЯ ДОКУМЕНТОВ ОРГАНИЗАЦИЙ (карты партнеров, справки, реквизиты):
Для КАЖДОЙ организации/учреждения создай отдельный объект:
- organization_name: полное название (со всеми сокращениями и символами)
- inn: ИНН (все цифры точно)
- kpp: КПП (все цифры точно)
- ogrn: ОГРН (если есть)
- okpo: ОКПО (если есть)
- oktmo: ОКТМО (если есть)
- okato: ОКАТО (если есть)
- okfs: ОКФС (если есть)
- address: полный адрес (включая индекс, все улицы, дома)
- director: ФИО руководителя (точно как написано)
- phone: все телефоны (с кодами и форматированием)
- email: все email адреса
- bank_name: название банка
- bank_account: расчетный счет
- korr_account: корреспондентский счет
- bik: БИК банка
- license: все лицензии и сертификаты
- registration_date: даты регистрации
- other: ВСЯ остальная информация

👥 ДЛЯ СПИСКОВ ЛЮДЕЙ (медосмотры, сотрудники, пациенты):
Для КАЖДОГО человека создай отдельный объект:
- fio: полное ФИО (точно как написано с пробелами)
- birth_date: дата рождения (в исходном формате)
- age: возраст (если указан)
- position: должность/профессия
- department: отдел/подразделение
- workplace: место работы
- address: адрес проживания
- phone: телефон
- passport: паспортные данные
- snils: СНИЛС
- medical_book: номер медкнижки
- harmful_factors: вредные факторы
- diagnosis: диагнозы (если есть)
- recommendations: рекомендации
- exam_date: дата осмотра
- next_exam: дата следующего осмотра
- other: ВСЯ дополнительная информация

🔒 КРИТИЧЕСКИЕ ПРАВИЛА:
1. ИЗВЛЕКАЙ КАЖДУЮ ЗАПИСЬ - не пропускай ни одной строки с данными
2. ТОЧНОСТЬ ИМЕН - сохраняй все символы, регистр, пробелы в именах
3. ПОЛНЫЕ ЧИСЛА - все коды, номера, даты целиком
4. НЕ ИСПРАВЛЯЙ орфографию в именах и названиях
5. НЕ ПЕРЕВОДИ на другие языки
6. СОХРАНЯЙ исходный формат дат и номеров

Верни результат в виде JSON массива объектов. Если на изображении 10 записей - должно быть 10 объектов. Если структурированных данных нет, верни []."""
                            }
                        ]
                    }
                ],
                temperature=0
            ) as stream:
                json_result = ""
                for text in stream.text_stream:
                    json_result += text
            
            import json
            try:
                # Пытаемся распарсить JSON ответ
                result = json.loads(json_result.strip())
                if isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                logger.warning("Claude вернул не JSON формат для таблиц")
            
            return []
            
        except Exception as e:
            logger.error(f"Ошибка извлечения таблиц Claude API: {e}")
            return []
    
    def process_pdf_images(self, pdf_path: str) -> Dict:
        """
        Обрабатывает PDF файл как изображения (для сканированных документов)
        """
        try:
            # Конвертируем PDF в изображения
            try:
                # Пробуем с настроенным путем
                if USE_POPPLER_PATH:
                    images = convert_from_path(pdf_path, poppler_path=USE_POPPLER_PATH)
                else:
                    # Используем системный poppler
                    images = convert_from_path(pdf_path)
            except Exception as e:
                logger.error(f"Ошибка конвертации PDF с poppler_path={USE_POPPLER_PATH}: {e}")
                # Пробуем разные варианты
                try:
                    # Без указания пути
                    images = convert_from_path(pdf_path)
                except Exception as e2:
                    logger.error(f"Ошибка конвертации PDF без пути: {e2}")
                    # Пробуем с явным путем к системному poppler
                    try:
                        images = convert_from_path(pdf_path, poppler_path="/usr/bin")
                    except Exception as e3:
                        logger.error(f"Ошибка конвертации PDF с /usr/bin: {e3}")
                        return {
                            'success': False,
                            'text': '',
                            'pages': 0,
                            'tables': [],
                            'method': 'None',
                            'error': f'Не удалось конвертировать PDF в изображения: {e3}'
                        }
            
            all_text = ""
            all_tables = []
            method_used = "None"
            
            for i, image in enumerate(images):
                logger.info(f"Обрабатываю страницу {i+1}/{len(images)}")
                
                # Пробуем Claude API сначала (если доступен)
                if self.claude_client:
                    claude_text = self.extract_text_with_claude(image)
                    if claude_text:
                        all_text += f"\n\n--- Страница {i+1} ---\n{claude_text}"
                        method_used = "Claude API"
                        
                        # Извлекаем таблицы
                        tables = self.extract_tables_with_claude(image)
                        all_tables.extend(tables)
                        continue
                
                # Fallback на Tesseract OCR (если доступен)
                if self.tesseract_available:
                    tesseract_text = self.extract_text_with_tesseract(image)
                    if tesseract_text:
                        all_text += f"\n\n--- Страница {i+1} ---\n{tesseract_text}"
                        method_used = "Tesseract OCR"
                else:
                    # Если нет ни Claude, ни Tesseract
                    if not self.claude_client:
                        return {
                            'success': False,
                            'text': '',
                            'pages': len(images),
                            'tables': [],
                            'method': 'None',
                            'error': 'Нет доступных методов распознавания. Настройте Claude API или установите Tesseract.'
                        }
            
            return {
                'success': True,
                'text': all_text.strip(),
                'pages': len(images),
                'tables': all_tables,
                'method': method_used,
                'error': None
            }
            
        except Exception as e:
            logger.error(f"Ошибка обработки PDF изображений: {e}")
            return {
                'success': False,
                'text': '',
                'pages': 0,
                'tables': [],
                'method': 'None',
                'error': str(e)
            }
    
    def process_pdf_direct_claude(self, pdf_path: str) -> Dict:
        """
        Обрабатывает PDF файл напрямую через Claude API (без конвертации в изображения)
        Это более эффективный и точный метод обработки PDF
        """
        if not self.claude_client:
            return {
                'success': False,
                'text': '',
                'pages': 0,
                'tables': [],
                'method': 'None',
                'error': 'Claude API не настроен'
            }
        
        try:
            logger.info(f"Обрабатываю PDF напрямую через Claude API: {pdf_path}")
            
            # Читаем PDF файл в base64
            with open(pdf_path, 'rb') as pdf_file:
                pdf_data = base64.b64encode(pdf_file.read()).decode('utf-8')
            
            # Первый этап: извлечение всех данных из PDF
            logger.info("Этап 1: Извлечение данных из PDF")
            with self.claude_client.messages.stream(
                model="claude-sonnet-4-20250514",
                max_tokens=64000,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "document",
                                "source": {
                                    "type": "base64",
                                    "media_type": "application/pdf",
                                    "data": pdf_data
                                }
                            },
                            {
                                "type": "text",
                                "text": """Ты - эксперт-аналитик по извлечению данных из PDF документов. Проанализируй этот PDF файл и извлеки АБСОЛЮТНО ВСЕ данные с максимальной точностью.

🎯 ЗАДАЧА: Полный анализ и извлечение данных

📋 ПЕРВИЧНОЕ ИЗВЛЕЧЕНИЕ:
- Извлеки КАЖДОЕ слово, цифру, дату из документа
- Сохраняй ТОЧНУЮ структуру и форматирование
- Включай заголовки, подзаголовки, таблицы, списки
- НЕ пропускай мелкий текст, сноски, примечания
- Извлекай печати, подписи, штампы (если есть текст)

🔒 КРИТИЧЕСКИ ВАЖНО - ИМЕНА И ДАННЫЕ:
- Все имена, фамилии, отчества ТОЧНО как написано
- НЕ исправляй орфографию в персональных данных
- НЕ переводи имена на другие языки
- Сохраняй ВСЕ символы, пробелы, дефисы в именах
- Сохраняй точные написания организаций и должностей

📊 СТРУКТУРИРОВАННЫЕ ДАННЫЕ:
Если видишь таблицы или списки данных - извлекай каждую строку отдельно:
- ФИО сотрудников/пациентов
- Даты рождения, возраст
- Должности, отделы, места работы
- Медицинские данные, диагнозы
- Организационные данные (ИНН, КПП, адреса)
- Банковские реквизиты, телефоны, email
- Номера документов, лицензий, сертификатов

🎯 ФОРМАТ ОТВЕТА:
Верни ВЕСЬ извлеченный текст в исходном порядке и структуре.
НЕ добавляй комментарии или пояснения.
Только чистые данные из PDF."""
                            }
                        ]
                    }
                ],
                temperature=0
            ) as stream:
                extracted_text = ""
                for text in stream.text_stream:
                    extracted_text += text
            
            if not extracted_text.strip():
                return {
                    'success': False,
                    'text': '',
                    'pages': 1,
                    'tables': [],
                    'method': 'Claude Direct PDF',
                    'error': 'Не удалось извлечь текст из PDF'
                }
            
            # Второй этап: проверка и уточнение имен и критических данных
            logger.info("Этап 2: Проверка и уточнение имен и данных")
            with self.claude_client.messages.stream(
                model="claude-sonnet-4-20250514",
                max_tokens=64000,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "document",
                                "source": {
                                    "type": "base64",
                                    "media_type": "application/pdf",
                                    "data": pdf_data
                                }
                            },
                            {
                                "type": "text",
                                "text": f"""Ты - контролер качества данных. Перед тобой извлеченный из PDF текст. Твоя задача - ПРОВЕРИТЬ и ИСПРАВИТЬ только явные ошибки распознавания, сохранив все оригинальные написания имен.

ИЗВЛЕЧЕННЫЙ ТЕКСТ:
{extracted_text}

🔍 ЗАДАЧА ПРОВЕРКИ:
1. Проверь по исходному PDF все имена, фамилии, отчества
2. Убедись что НИ ОДНО имя не потеряно или искажено
3. Исправь только ОЧЕВИДНЫЕ ошибки OCR (неправильные символы)
4. НЕ исправляй орфографию - только технические ошибки распознавания

⚠️ КРИТИЧЕСКИЕ ПРАВИЛА:
- ЗАПРЕЩЕНО менять написание имен (даже если кажется неправильным)
- ЗАПРЕЩЕНО переводить имена на другие языки
- ЗАПРЕЩЕНО "исправлять" региональные или необычные имена
- Исправляй только символы распознавания: 0→О, 1→I, и т.д.

🎯 ВЕРНИ:
Исправленный текст с сохранением ВСЕХ оригинальных имен и данных.
Только технические исправления символов распознавания."""
                            }
                        ]
                    }
                ],
                temperature=0
            ) as stream:
                verified_text = ""
                for text in stream.text_stream:
                    verified_text += text
            
            # Третий этап: извлечение структурированных данных для Excel
            logger.info("Этап 3: Извлечение структурированных данных")
            with self.claude_client.messages.stream(
                model="claude-sonnet-4-20250514",
                max_tokens=64000,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"""Из этого проверенного текста извлеки структурированные данные в JSON формате:

ТЕКСТ ДОКУМЕНТА:
{verified_text}

🔍 АНАЛИЗ И СТРУКТУРИЗАЦИЯ:
Определи тип документа и извлеки ВСЕ структурированные данные.

📋 ДЛЯ ОРГАНИЗАЦИЙ (карты, справки, реквизиты):
Для КАЖДОЙ организации создай объект:
{{
    "organization_name": "полное название",
    "inn": "ИНН", "kpp": "КПП", "ogrn": "ОГРН",
    "address": "полный адрес", "director": "ФИО руководителя",
    "phone": "телефон", "email": "email", "bank_name": "банк",
    "bank_account": "р/с", "korr_account": "к/с", "bik": "БИК"
}}

👥 ДЛЯ СПИСКОВ ЛЮДЕЙ (медосмотры, сотрудники):
Для КАЖДОГО человека создай объект:
{{
    "fio": "полное ФИО", "birth_date": "дата рождения", "age": "возраст",
    "position": "должность", "department": "отдел", "workplace": "место работы",
    "address": "адрес", "phone": "телефон", "medical_book": "мед.книжка",
    "harmful_factors": "вредные факторы", "exam_date": "дата осмотра"
}}

🔒 ТРЕБОВАНИЯ:
- КАЖДУЮ запись из документа - отдельный объект
- Имена ТОЧНО как в тексте - без изменений
- Если поле пустое - оставь пустую строку ""
- Верни JSON массив объектов []

ВАЖНО: Если видишь 10 человек в списке - должно быть 10 объектов!"""
                            }
                        ]
                    }
                ],
                temperature=0
            ) as stream:
                json_data = ""
                for text in stream.text_stream:
                    json_data += text
            
            # Парсим JSON данные
            structured_data = []
            try:
                import json
                structured_data = json.loads(json_data.strip())
                if not isinstance(structured_data, list):
                    structured_data = []
            except json.JSONDecodeError as e:
                logger.warning(f"Не удалось распарсить JSON данные: {e}")
                structured_data = []
            
            logger.info(f"PDF обработан напрямую через Claude: текст={len(verified_text)} символов, записей={len(structured_data)}")
            
            return {
                'success': True,
                'text': verified_text.strip(),
                'pages': 1,  # Claude обрабатывает весь PDF как единое целое
                'tables': structured_data,
                'method': 'Claude Direct PDF (3-stage)',
                'error': None
            }
            
        except Exception as e:
            logger.error(f"Ошибка прямой обработки PDF через Claude: {e}")
            return {
                'success': False,
                'text': '',
                'pages': 0,
                'tables': [],
                'method': 'Claude Direct PDF',
                'error': str(e)
            } 