"""
Fresh translation module without any caching issues
"""
import os
import gettext as gettext_module
from flask import session, request, current_app

def get_locale():
    """Get current locale"""
    # 1. Check URL parameter
    if 'lang' in request.args:
        language = request.args['lang']
        if language in current_app.config['LANGUAGES']:
            session['language'] = language
            return language
    
    # 2. Check session
    if 'language' in session and session['language'] in current_app.config['LANGUAGES']:
        return session['language']
    
    # 3. Check browser headers
    return request.accept_languages.best_match(current_app.config['LANGUAGES'].keys()) or 'ru'

def translate_text(message):
    """Fresh translation function"""
    locale = get_locale()
    
    # Always load fresh - no caching
    try:
        # Project root translations folder
        project_root = os.path.dirname(current_app.root_path)
        localedir = os.path.join(project_root, 'translations')
        
        # Load translation
        translation = gettext_module.translation('messages', localedir, languages=[locale])
        return translation.gettext(message)
    except:
        # Fallback to original message
        return message