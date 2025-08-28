from flask import Flask, request, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from config import Config
import os

# Инициализация расширений
db = SQLAlchemy()
migrate = Migrate()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Конфигурация локализации
    app.config['LANGUAGES'] = {
        'ru': 'Русский',
        'en': 'English'
    }
    app.config['BABEL_DEFAULT_LOCALE'] = 'ru'
    app.config['BABEL_DEFAULT_TIMEZONE'] = 'Europe/Moscow'
    
    # Инициализация расширений
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Инициализация нашей системы локализации
    from app.i18n import load_translations, get_current_locale, gettext as _
    load_translations(app)
    
    # Глобальный контекстный процессор
    @app.context_processor
    def inject_conf_vars():
        from app.translation import get_locale, translate_text
        return {
            'LANGUAGES': app.config['LANGUAGES'],
            'CURRENT_LANGUAGE': get_locale(),
            '_': translate_text  # Делаем функцию перевода доступной в шаблонах
        }
    
    # Регистрация blueprints
    from app.routes import bp as main_bp
    app.register_blueprint(main_bp)
    
    return app

# Импорт моделей (важно для миграций)
from app import models