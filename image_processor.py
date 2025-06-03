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
    # На сервере (Railway/Linux)
    USE_POPPLER_PATH = os.environ.get('PDF2IMAGE_USE_POPPLER_PATH', None)

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
            images = convert_from_path(pdf_path, first_page=1, last_page=1, dpi=150, poppler_path=POPPLER_PATH)
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
            
            # Запрос к Claude
            response = self.claude_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4000,
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
                                "text": """Извлеки весь текст из этого изображения. 
                                Сохрани структуру и форматирование. 
                                Если есть таблицы, представь их в структурированном виде.
                                Отвечай только извлеченным текстом без дополнительных комментариев."""
                            }
                        ]
                    }
                ],
                temperature=0
            )
            
            return response.content[0].text.strip()
            
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
            
            # Запрос к Claude для извлечения таблиц
            response = self.claude_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4000,
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
                                "text": """Найди и извлеки все таблицы из этого изображения.
                                Для каждой найденной записи в таблице верни JSON объект со следующими полями:
                                - fio: ФИО (если есть)
                                - birth_date: дата рождения (если есть)
                                - position: должность (если есть)
                                - harmful_factors: факторы вредности (если есть)
                                - other: любая другая важная информация
                                
                                Верни результат в формате JSON массива объектов.
                                Если таблиц нет, верни пустой массив []."""
                            }
                        ]
                    }
                ],
                temperature=0
            )
            
            import json
            try:
                # Пытаемся распарсить JSON ответ
                result = json.loads(response.content[0].text.strip())
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
                images = convert_from_path(pdf_path, poppler_path=USE_POPPLER_PATH)
            except Exception as e:
                logger.error(f"Ошибка конвертации PDF с poppler_path={USE_POPPLER_PATH}: {e}")
                # Пробуем без явного указания пути
                images = convert_from_path(pdf_path)
            
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