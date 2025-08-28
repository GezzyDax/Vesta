#!/usr/bin/env python3
"""
Тестовый скрипт для проверки работоспособности сайта Vesta
"""
import requests
import time
import sys
from datetime import datetime

def test_site():
    """Тестирует работоспособность сайта"""
    url = "http://localhost:5000"
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Тестирование сайта {url}")
    
    try:
        # Тест 1: Проверка доступности главной страницы
        print("  └─ Проверка доступности главной страницы...")
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            print("  ✅ Сайт доступен (HTTP 200)")
            
            # Тест 2: Проверка содержимого
            if "Vesta" in response.text or "title" in response.text:
                print("  ✅ Содержимое корректное")
            else:
                print("  ❌ Содержимое не корректное")
                return False
                
            # Тест 3: Проверка основных страниц
            pages = ['/dashboard', '/transactions', '/accounts', '/profile']
            for page in pages:
                try:
                    page_response = requests.get(url + page, timeout=5)
                    if page_response.status_code in [200, 302]:  # 302 для редиректов
                        print(f"  ✅ Страница {page} доступна")
                    else:
                        print(f"  ⚠️  Страница {page} вернула код {page_response.status_code}")
                except requests.exceptions.RequestException as e:
                    print(f"  ❌ Страница {page} недоступна: {e}")
            
            return True
            
        else:
            print(f"  ❌ Сайт недоступен (HTTP {response.status_code})")
            return False
            
    except requests.exceptions.ConnectionError:
        print("  ❌ Ошибка подключения - сайт недоступен")
        return False
    except requests.exceptions.Timeout:
        print("  ❌ Тайм-аут - сайт отвечает слишком медленно")
        return False
    except Exception as e:
        print(f"  ❌ Неожиданная ошибка: {e}")
        return False

def monitor_site(interval=30):
    """Непрерывный мониторинг сайта"""
    print(f"Запуск мониторинга с интервалом {interval} секунд...")
    print("Для остановки нажмите Ctrl+C")
    print("-" * 50)
    
    try:
        while True:
            success = test_site()
            if success:
                print("✅ Сайт работает нормально\n")
            else:
                print("❌ Сайт недоступен!\n")
            
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nМониторинг остановлен пользователем")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--monitor":
        monitor_site()
    else:
        success = test_site()
        sys.exit(0 if success else 1)