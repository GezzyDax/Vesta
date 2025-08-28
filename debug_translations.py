#!/usr/bin/env python3
"""
Отладка системы переводов
"""
import os
import gettext as gettext_module

def debug_translations():
    print("🔍 Отладка системы переводов...")
    
    # Проверяем структуру файлов
    translations_dir = "/home/gezzy/pyprod/Vesta/translations"
    print(f"📁 Папка переводов: {translations_dir}")
    print(f"   Существует: {os.path.exists(translations_dir)}")
    
    if os.path.exists(translations_dir):
        print("📋 Содержимое папки:")
        for item in os.listdir(translations_dir):
            item_path = os.path.join(translations_dir, item)
            print(f"   • {item} {'(папка)' if os.path.isdir(item_path) else '(файл)'}")
            
            if os.path.isdir(item_path):
                lc_messages = os.path.join(item_path, "LC_MESSAGES")
                if os.path.exists(lc_messages):
                    print(f"     └─ LC_MESSAGES:")
                    for file in os.listdir(lc_messages):
                        file_path = os.path.join(lc_messages, file)
                        size = os.path.getsize(file_path)
                        print(f"        • {file} ({size} байт)")
    
    # Пробуем загрузить переводы напрямую
    print("\n🔄 Попытка загрузки переводов:")
    
    for lang in ['ru', 'en']:
        print(f"  🌍 Язык: {lang}")
        try:
            translation = gettext_module.translation('messages', translations_dir, languages=[lang])
            print(f"    ✅ Загружен успешно")
            
            # Тестируем перевод
            test_strings = ['Type', 'All Types', 'Income', 'Expenses']
            for test_str in test_strings:
                result = translation.gettext(test_str)
                status = "✅" if result != test_str else "❌"
                print(f"    {status} '{test_str}' -> '{result}'")
                
        except Exception as e:
            print(f"    ❌ Ошибка загрузки: {e}")
    
    print("\n🧪 Проверка конкретных .mo файлов:")
    
    for lang in ['ru', 'en']:
        mo_path = os.path.join(translations_dir, lang, 'LC_MESSAGES', 'messages.mo')
        print(f"  📄 {mo_path}")
        print(f"    Существует: {os.path.exists(mo_path)}")
        
        if os.path.exists(mo_path):
            size = os.path.getsize(mo_path)
            print(f"    Размер: {size} байт")
            
            # Попробуем открыть файл напрямую
            try:
                with open(mo_path, 'rb') as f:
                    magic = f.read(4)
                    print(f"    Magic bytes: {magic.hex()}")
                    # Правильные magic bytes для .mo файла: 950412de или de120495
                    if magic in [b'\x95\x04\x12\xde', b'\xde\x12\x04\x95']:
                        print(f"    ✅ Формат .mo корректный")
                    else:
                        print(f"    ❌ Неверный формат .mo файла")
            except Exception as e:
                print(f"    ❌ Ошибка чтения файла: {e}")

if __name__ == "__main__":
    debug_translations()