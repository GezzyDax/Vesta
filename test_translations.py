#!/usr/bin/env python3
"""
Тест для проверки работы переводов в приложении Vesta
"""
import requests
import sys
import re

def test_translations():
    """Тестируем работу переводов на различных страницах"""
    base_url = "http://localhost:5000"
    
    # Тестовые фразы, которые должны переводиться
    test_phrases = {
        # Русские фразы -> Английские фразы
        "Все типы": "All Types",
        "Доходы": "Income", 
        "Расходы": "Expenses",
        "Переводы": "Transfers",
        "Пользователь": "User",
        "Все": "All",
        "Категория": "Category",
        "Дата с": "Date From",
        "Дата по": "Date To",
        "Дата": "Date",
        "Тип": "Type",
        "Счета": "Accounts",
        "Сумма": "Amount",
        "Описание": "Description",
        "Контакт": "Contact"
    }
    
    pages_to_test = [
        "/transactions",
        "/accounts", 
        "/profile"
    ]
    
    print("🔍 Тестирование переводов...")
    
    for page in pages_to_test:
        print(f"\n📄 Тестирование страницы: {page}")
        
        # Тест русского языка
        print("  🇷🇺 Проверяем русский язык...")
        try:
            response = requests.get(f"{base_url}{page}?lang=ru", timeout=10)
            if response.status_code == 200:
                content = response.text
                found_phrases = []
                missing_phrases = []
                
                for ru_phrase, en_phrase in test_phrases.items():
                    if ru_phrase in content:
                        found_phrases.append(ru_phrase)
                    else:
                        missing_phrases.append(ru_phrase)
                
                print(f"    ✅ Найдено русских фраз: {len(found_phrases)}")
                if found_phrases:
                    print(f"    📝 Найденные: {', '.join(found_phrases[:5])}{'...' if len(found_phrases) > 5 else ''}")
                
                if missing_phrases:
                    print(f"    ❌ Отсутствуют: {len(missing_phrases)} фраз")
                    print(f"    📝 Отсутствующие: {', '.join(missing_phrases[:5])}{'...' if len(missing_phrases) > 5 else ''}")
            else:
                print(f"    ❌ Страница недоступна (HTTP {response.status_code})")
        except Exception as e:
            print(f"    ❌ Ошибка при тестировании русского: {e}")
            
        # Тест английского языка
        print("  🇬🇧 Проверяем английский язык...")
        try:
            response = requests.get(f"{base_url}{page}?lang=en", timeout=10)
            if response.status_code == 200:
                content = response.text
                found_phrases = []
                missing_phrases = []
                
                for ru_phrase, en_phrase in test_phrases.items():
                    if en_phrase in content:
                        found_phrases.append(en_phrase)
                    else:
                        missing_phrases.append(en_phrase)
                
                print(f"    ✅ Найдено английских фраз: {len(found_phrases)}")
                if found_phrases:
                    print(f"    📝 Найденные: {', '.join(found_phrases[:5])}{'...' if len(found_phrases) > 5 else ''}")
                
                if missing_phrases:
                    print(f"    ❌ Отсутствуют: {len(missing_phrases)} фраз")
                    print(f"    📝 Отсутствующие: {', '.join(missing_phrases[:5])}{'...' if len(missing_phrases) > 5 else ''}")
            else:
                print(f"    ❌ Страница недоступна (HTTP {response.status_code})")
        except Exception as e:
            print(f"    ❌ Ошибка при тестировании английского: {e}")

def check_translation_system():
    """Проверяем систему переводов напрямую"""
    print("\n🔧 Диагностика системы переводов...")
    
    try:
        # Тестируем доступ к API переключения языка
        base_url = "http://localhost:5000"
        
        print("  🔄 Тестируем переключение на русский...")
        response = requests.get(f"{base_url}/set_language/ru", allow_redirects=False, timeout=10)
        print(f"    Статус: {response.status_code}")
        
        print("  🔄 Тестируем переключение на английский...")
        response = requests.get(f"{base_url}/set_language/en", allow_redirects=False, timeout=10)  
        print(f"    Статус: {response.status_code}")
        
        # Проверяем главную страницу с разными языками
        print("  🏠 Тестируем главную страницу с параметром lang...")
        
        # Русский
        response = requests.get(f"{base_url}/?lang=ru", timeout=10)
        ru_content = response.text
        print(f"    RU - Статус: {response.status_code}, Размер: {len(ru_content)} символов")
        
        # Английский  
        response = requests.get(f"{base_url}/?lang=en", timeout=10)
        en_content = response.text
        print(f"    EN - Статус: {response.status_code}, Размер: {len(en_content)} символов")
        
        # Сравниваем контент
        if ru_content == en_content:
            print("    ⚠️  ПРОБЛЕМА: Контент одинаковый для обоих языков!")
        else:
            print("    ✅ Контент различается между языками")
            
    except Exception as e:
        print(f"    ❌ Ошибка диагностики: {e}")

def analyze_template_issues():
    """Анализируем проблемы в шаблонах"""
    print("\n🔍 Анализ проблем переводов...")
    
    try:
        base_url = "http://localhost:5000"
        response = requests.get(f"{base_url}/transactions?lang=ru", timeout=10)
        
        if response.status_code == 200:
            content = response.text
            
            # Простой анализ русского текста в HTML
            hardcoded_russian = []
            lines = content.split('\n')
            
            for i, line in enumerate(lines):
                if re.search(r'>[А-Яа-я]', line) and '{{' not in line:
                    text_match = re.search(r'>([А-Яа-я][^<]*)', line)
                    if text_match:
                        hardcoded_russian.append(f"Строка {i+1}: {text_match.group(1).strip()}")
            
            print(f"  📋 Найдено потенциально неперевденных элементов: {len(hardcoded_russian)}")
            if hardcoded_russian:
                for item in hardcoded_russian[:10]:  # Показываем первые 10
                    print(f"    • {item}")
                    
        else:
            print(f"  ❌ Не удалось загрузить страницу: {response.status_code}")
            
    except Exception as e:
        print(f"  ❌ Ошибка анализа: {e}")

if __name__ == "__main__":
    print("🌍 Тест системы переводов Vesta")
    print("=" * 50)
    
    test_translations()
    check_translation_system() 
    analyze_template_issues()
    
    print("\n✨ Тестирование завершено")