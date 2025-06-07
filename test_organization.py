#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Тест обработки документов организаций
"""

from pdf_processor import PDFProcessor
import json

# Тестовые данные организации (как если бы Claude их извлек)
test_organization_data = [
    {
        'organization_name': 'Муниципальное казенное общеобразовательное учреждение Бобровская-2 средняя школа',
        'inn': '3427010884',
        'kpp': '342701001',
        'address': '403448, Бобровский 2-й, Серафимовический район, Волгоградская область',
        'director': 'Фирсов Александр Васильевич',
        'phone': '8(84464)1924',
        'email': 'Serafimbobr2@mail.ru',
        'license': 'регистрационный № 662 от 28 октября 2016 г.',
        'other': 'МКОУ Бобровская-2 СШ'
    }
]

# Тестовые данные людей
test_people_data = [
    {
        'fio': 'Иванов Иван Иванович',
        'birth_date': '15.03.1985',
        'position': 'Инженер',
        'department': 'Техническая служба',
        'other': 'Дополнительная информация'
    },
    {
        'fio': 'Петрова Анна Сергеевна',
        'birth_date': '22.07.1990',
        'position': 'Бухгалтер',
        'department': 'Финансовый отдел',
        'other': ''
    }
]

def test_excel_creation():
    """Тестирует создание Excel файлов для разных типов данных"""
    
    processor = PDFProcessor()
    
    print("🧪 Тестирование создания Excel файлов...")
    
    # Тест 1: Документ организации
    print("\n1️⃣ Тест: Документ организации")
    try:
        org_file = "test_organization.xlsx"
        processor.create_excel_from_data(test_organization_data, org_file)
        print(f"✅ Excel файл организации создан: {org_file}")
        
        # Выводим данные
        print("📊 Данные организации:")
        for key, value in test_organization_data[0].items():
            print(f"   • {key}: {value}")
            
    except Exception as e:
        print(f"❌ Ошибка создания файла организации: {e}")
    
    # Тест 2: Данные людей
    print("\n2️⃣ Тест: Данные людей")
    try:
        people_file = "test_people.xlsx"
        processor.create_excel_from_data(test_people_data, people_file)
        print(f"✅ Excel файл людей создан: {people_file}")
        
        # Выводим данные
        print("📊 Данные людей:")
        for i, person in enumerate(test_people_data, 1):
            print(f"   Человек {i}:")
            for key, value in person.items():
                if value:
                    print(f"     • {key}: {value}")
                    
    except Exception as e:
        print(f"❌ Ошибка создания файла людей: {e}")

if __name__ == "__main__":
    test_excel_creation() 