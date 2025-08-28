import os
from datetime import timedelta

class Config:
    # Секретный ключ для форм и сессий
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Конфигурация базы данных
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///./instance/familybudget.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Настройки приложения
    LANGUAGES = ['ru', 'en']
    DEFAULT_LANGUAGE = 'ru'
    
    # Настройки сессии
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    
    # Настройки CSV экспорта
    CSV_EXPORT_ENCODING = 'utf-8-sig'