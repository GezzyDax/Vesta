#!/usr/bin/env python3
"""
Тестирование парсера Alpha Bank
"""

import os
import sys
import pandas as pd
from app import create_app
from app.bank_import import AlphaBankParser

def test_alpha_bank_parser():
    """Тестировать парсер Alpha Bank"""
    file_path = 'test_file.xlsx'
    
    if not os.path.exists(file_path):
        print("❌ Файл test_file.xlsx не найден")
        return
    
    print(f"📁 Анализируем файл: {file_path}")
    
    try:
        # Сначала посмотрим на структуру файла
        print("\n🔍 Анализ структуры файла...")
        
        # Читаем первые несколько листов
        xl_file = pd.ExcelFile(file_path)
        print(f"Листы в файле: {xl_file.sheet_names}")
        
        # Читаем первый лист
        df = pd.read_excel(file_path, sheet_name=0, header=None)
        print(f"Размер данных: {df.shape[0]} строк, {df.shape[1]} столбцов")
        
        # Показываем первые 25 строк для анализа
        print("\n📋 Первые 25 строк файла:")
        for i in range(min(25, len(df))):
            row_data = []
            for j in range(min(15, len(df.columns))):  # Первые 15 столбцов
                cell_value = df.iloc[i, j]
                if pd.isna(cell_value):
                    row_data.append("NULL")
                else:
                    row_data.append(str(cell_value)[:50])  # Ограничиваем длину
            print(f"Строка {i}: {' | '.join(row_data)}")
        
        # Теперь тестируем парсер
        print("\n🤖 Тестируем парсер Alpha Bank...")
        parser = AlphaBankParser()
        
        transactions = parser.parse_file(file_path)
        
        print(f"\n✅ Парсер нашёл {len(transactions)} транзакций")
        
        if transactions:
            print("\n📋 Примеры найденных транзакций:")
            for i, trans in enumerate(transactions[:5]):  # Первые 5
                print(f"Транзакция {i+1}:")
                print(f"  Дата: {trans['date']}")
                print(f"  Сумма: {trans['amount']}")
                print(f"  Описание: {trans['description'][:100]}...")
                print(f"  Тип: {trans['transaction_type']}")
                print(f"  Категория: {trans['category']}")
                if trans.get('subcategory'):
                    print(f"  Подкатегория: {trans['subcategory']}")
                if trans.get('contact_phone'):
                    print(f"  Телефон: {trans['contact_phone']}")
                print()
        
    except Exception as e:
        print(f"❌ Ошибка при анализе файла: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Основная функция"""
    app = create_app()
    
    with app.app_context():
        test_alpha_bank_parser()

if __name__ == '__main__':
    main()