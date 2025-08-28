"""
Простая система локализации без Flask-Babel
Использует gettext напрямую
"""
import gettext as gettext_module
import os
from flask import session, request, current_app

# Глобальные переводчики
_translations = {}

def load_translations(app):
    """Загрузка переводов при инициализации приложения"""
    global _translations
    
    # Translations folder is at project root, not app root
    localedir = os.path.join(os.path.dirname(app.root_path), 'translations')
    
    # Clear existing translations
    _translations.clear()
    
    for lang in app.config['LANGUAGES'].keys():
        try:
            translation = gettext_module.translation('messages', localedir, languages=[lang])
            _translations[lang] = translation
        except Exception as e:
            # Fallback to NullTranslations
            _translations[lang] = gettext_module.NullTranslations()
    
    # Force immediate verification for Russian
    if 'ru' in _translations:
        test_result = _translations['ru'].gettext('Main')
        if test_result == 'Main':
            # Reload Russian translation
            try:
                _translations['ru'] = gettext_module.translation('messages', localedir, languages=['ru'])
            except:
                pass

def get_current_locale():
    """Получение текущей локали"""
    # 1. Проверяем URL параметр
    if 'lang' in request.args:
        language = request.args['lang']
        if language in current_app.config['LANGUAGES']:
            session['language'] = language
            return language
    
    # 2. Проверяем сессию
    if 'language' in session and session['language'] in current_app.config['LANGUAGES']:
        return session['language']
    
    # 3. Проверяем заголовки браузера
    return request.accept_languages.best_match(current_app.config['LANGUAGES'].keys()) or 'ru'

def gettext(message):
    """Функция перевода с прямой загрузкой"""
    locale = get_current_locale()
    
    # Always load directly to avoid caching issues
    try:
        from flask import current_app
        localedir = os.path.join(os.path.dirname(current_app.root_path), 'translations')
        translation = gettext_module.translation('messages', localedir, languages=[locale])
        return translation.gettext(message)
    except Exception:
        # Fallback
        return message

# Алиасы для совместимости
_ = gettext
lazy_gettext = gettext  # Для простоты, не делаем lazy в данной реализации