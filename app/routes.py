from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from datetime import date, datetime, timedelta
from decimal import Decimal
import os
import uuid
from werkzeug.utils import secure_filename
from app import db
from app.models import (User, Account, Transaction, Category, DataVersion, 
                       TransactionSnapshot, AccountSnapshot, ImportPreview, ImportPreviewTransaction,
                       Contact, UserProfile, MerchantRule)
from app.bank_import import BankImportService
from app.version import get_app_version, get_version_info
from sqlalchemy import func, desc, text

bp = Blueprint('main', __name__)

# ============ SECURITY & VALIDATION FUNCTIONS ============

def create_linked_sbp_transaction(original_transaction, contact_phone):
    """Создать встречную транзакцию для СБП перевода"""
    if not contact_phone or original_transaction.transaction_type != 'transfer':
        return None
    
    # Нормализуем номер телефона перед поиском
    normalized_phone = Contact.normalize_phone(contact_phone)
    if not normalized_phone:
        return None
    
    # Ищем получателя по номеру телефона
    recipient_user = User.find_by_phone(normalized_phone)
    if not recipient_user:
        return None
    
    # Проверяем, что это не перевод самому себе
    sender_account = original_transaction.from_account
    if not sender_account or sender_account.user_id == recipient_user.id:
        return None
    
    # Получаем счет по умолчанию для СБП получателя
    recipient_account = recipient_user.default_sbp_account
    if not recipient_account:
        # Берем первый активный счет получателя
        recipient_account = recipient_user.accounts.filter_by(is_active=True).first()
        if not recipient_account:
            return None
    
    # Создаем встречную транзакцию (доход для получателя)
    linked_transaction = Transaction(
        transaction_type='income',
        amount=original_transaction.amount,
        description=f"СБП от {sender_account.owner.name}: {original_transaction.description or 'Перевод'}",
        category_id=original_transaction.category_id,
        date=original_transaction.date,
        to_account_id=recipient_account.id,
        contact_phone=Contact.normalize_phone(sender_account.owner.phone_numbers[0]) if sender_account.owner.phone_numbers else None,
        subcategory=original_transaction.subcategory,
        reference=original_transaction.reference
    )
    
    return linked_transaction

def validate_amount(amount_str):
    """Валидация суммы транзакции"""
    try:
        amount = Decimal(str(amount_str))
        if amount < 0:
            return False, "Сумма не может быть отрицательной"
        if amount > Decimal('999999999.99'):  # 999 млн максимум
            return False, "Сумма слишком большая"
        return True, amount
    except (ValueError, TypeError):
        return False, "Некорректное значение суммы"

def validate_date_input(date_str):
    """Валидация даты"""
    try:
        input_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        if input_date > date.today():
            return False, "Дата не может быть в будущем"
        if input_date < date(2000, 1, 1):
            return False, "Дата слишком старая"
        return True, input_date
    except (ValueError, TypeError):
        return False, "Некорректный формат даты"

def validate_text_input(text, field_name, min_length=1, max_length=255, required=True):
    """Валидация текстовых полей"""
    if not text:
        if required:
            return False, f"Поле '{field_name}' обязательно для заполнения"
        return True, ""
    
    text = str(text).strip()
    
    if len(text) < min_length:
        return False, f"'{field_name}' должно содержать минимум {min_length} символов"
    
    if len(text) > max_length:
        return False, f"'{field_name}' должно содержать максимум {max_length} символов"
    
    # Проверка на потенциально опасные символы
    dangerous_chars = ['<', '>', '"', "'", '&', 'script', 'javascript:', 'onload', 'onerror']
    text_lower = text.lower()
    for char in dangerous_chars:
        if char in text_lower:
            return False, f"Поле '{field_name}' содержит недопустимые символы"
    
    return True, text

def check_entity_access(entity, entity_type="entity"):
    """Проверка прав доступа к сущности"""
    if not entity:
        return False, f"Запрашиваемая {entity_type} не найдена"
    
    # В будущем здесь можно добавить проверки на принадлежность пользователю
    return True, entity

def sanitize_sql_input(text):
    """Очистка входных данных от потенциальных SQL инъекций"""
    if not text:
        return text
    
    dangerous_patterns = [
        'DROP ', 'DELETE ', 'UPDATE ', 'INSERT ', 'CREATE ', 'ALTER ', 'EXEC',
        'UNION ', 'SELECT ', '--', '/*', '*/', ';', 'xp_', 'sp_'
    ]
    
    text_upper = str(text).upper()
    for pattern in dangerous_patterns:
        if pattern in text_upper:
            # Логируем подозрительную активность (в будущем)
            return text.replace(pattern.strip(), '')
    
    return text

def validate_phone_number(phone):
    """Валидация номера телефона"""
    if not phone:
        return True, ""
    
    # Удаляем все символы кроме цифр
    digits_only = ''.join(filter(str.isdigit, phone))
    
    # Проверяем длину
    if len(digits_only) not in [10, 11]:
        return False, "Номер телефона должен содержать 10 или 11 цифр"
    
    # Проверяем российские номера
    if len(digits_only) == 11 and not digits_only.startswith(('7', '8')):
        return False, "Номер должен начинаться с 7 или 8"
    
    if len(digits_only) == 10 and not digits_only.startswith('9'):
        return False, "10-значный номер должен начинаться с 9"
    
    # Нормализуем к формату +7XXXXXXXXXX
    if len(digits_only) == 11:
        if digits_only.startswith('8'):
            digits_only = '7' + digits_only[1:]
    else:  # 10 цифр
        digits_only = '7' + digits_only
    
    return True, digits_only

@bp.route('/')
def dashboard():
    """Главная страница - дашборд"""
    # Получаем всех пользователей и их счета
    users = User.query.filter_by(is_active=True).all()
    
    # Статистика за текущий месяц
    current_month = date.today().month
    current_year = date.today().year
    monthly_stats = Transaction.get_monthly_stats(current_month, current_year)
    
    # Последние транзакции
    recent_transactions = Transaction.query.order_by(desc(Transaction.created_at)).limit(5).all()
    
    # Общий семейный баланс
    total_family_balance = sum(user.get_total_balance() for user in users)
    
    return render_template('dashboard.html', 
                         users=users,
                         monthly_stats=monthly_stats,
                         recent_transactions=recent_transactions,
                         total_family_balance=total_family_balance,
                         current_month=current_month,
                         current_year=current_year)

@bp.route('/transactions')
def transactions():
    """Страница со всеми транзакциями"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)
    
    # Фильтры
    transaction_type = request.args.get('type')
    user_id = request.args.get('user_id', type=int)
    category_id = request.args.get('category_id', type=int)
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    phone_filter = request.args.get('phone')
    
    # Базовый запрос
    query = Transaction.query
    
    # Применение фильтров
    if transaction_type:
        query = query.filter(Transaction.transaction_type == transaction_type)
    
    if category_id:
        query = query.filter(Transaction.category_id == category_id)
    
    if user_id:
        # Фильтр по пользователю (по счетам)
        user_accounts = Account.query.filter_by(user_id=user_id).all()
        account_ids = [acc.id for acc in user_accounts]
        query = query.filter(
            (Transaction.from_account_id.in_(account_ids)) |
            (Transaction.to_account_id.in_(account_ids))
        )
    
    if date_from:
        query = query.filter(Transaction.date >= datetime.strptime(date_from, '%Y-%m-%d').date())
    
    if date_to:
        query = query.filter(Transaction.date <= datetime.strptime(date_to, '%Y-%m-%d').date())
    
    if phone_filter:
        query = query.filter(Transaction.contact_phone == phone_filter)
    
    # Сортировка и пагинация
    transactions = query.order_by(desc(Transaction.date), desc(Transaction.created_at)).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Данные для фильтров
    users = User.query.filter_by(is_active=True).all()
    categories = Category.query.filter_by(is_active=True).all()
    
    return render_template('transactions.html',
                         transactions=transactions,
                         users=users,
                         categories=categories,
                         filters={
                             'type': transaction_type,
                             'user_id': user_id,
                             'category_id': category_id,
                             'date_from': date_from,
                             'date_to': date_to
                         })

@bp.route('/add_transaction', methods=['GET', 'POST'])
def add_transaction():
    """Добавление новой транзакции"""
    if request.method == 'POST':
        try:
            transaction_type = request.form['transaction_type']
            amount = Decimal(str(request.form['amount']))
            description = request.form.get('description', '')
            category_id = int(request.form['category_id'])
            transaction_date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
            
            from_account_id = request.form.get('from_account_id')
            to_account_id = request.form.get('to_account_id')
            contact_phone = request.form.get('contact_phone', '').strip()
            subcategory = request.form.get('subcategory', '').strip()
            reference = request.form.get('reference', '').strip()
            
            # Создаем транзакцию
            normalized_phone = Contact.normalize_phone(contact_phone) if contact_phone else None
            transaction = Transaction(
                transaction_type=transaction_type,
                amount=amount,
                description=description,
                category_id=category_id,
                date=transaction_date,
                from_account_id=int(from_account_id) if from_account_id else None,
                to_account_id=int(to_account_id) if to_account_id else None,
                contact_phone=normalized_phone,
                subcategory=subcategory if subcategory else None,
                reference=reference if reference else None
            )
            
            db.session.add(transaction)
            db.session.flush()  # Получаем ID транзакции
            
            # Автоматически создаем контакт если указан номер телефона
            if normalized_phone:
                Transaction.create_contact_from_phone(normalized_phone)
            
            # Создаем встречную транзакцию для СБП переводов
            linked_transaction = create_linked_sbp_transaction(transaction, contact_phone)
            if linked_transaction:
                db.session.add(linked_transaction)
                db.session.flush()
                # Связываем транзакции друг с другом
                transaction.linked_transaction_id = linked_transaction.id
                linked_transaction.linked_transaction_id = transaction.id
            
            # Обновляем балансы счетов
            if transaction_type == 'income' and to_account_id:
                account = Account.query.get(int(to_account_id))
                account.balance += amount
                
            elif transaction_type == 'expense' and from_account_id:
                account = Account.query.get(int(from_account_id))
                account.balance -= amount
                
            elif transaction_type == 'transfer' and from_account_id and to_account_id:
                from_account = Account.query.get(int(from_account_id))
                to_account = Account.query.get(int(to_account_id))
                from_account.balance -= amount
                to_account.balance += amount
            
            # Обновляем баланс для встречной транзакции СБП
            if linked_transaction:
                linked_account = Account.query.get(linked_transaction.to_account_id)
                if linked_account:
                    linked_account.balance += amount
            
            db.session.commit()
            flash('Транзакция успешно добавлена!', 'success')
            return redirect(url_for('main.transactions'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при добавлении транзакции: {str(e)}', 'error')
    
    # GET запрос - показываем форму
    users = User.query.filter_by(is_active=True).all()
    categories = Category.query.filter_by(is_active=True).all()
    accounts = Account.query.filter_by(is_active=True).all()
    
    return render_template('add_transaction.html',
                         users=users,
                         categories=categories,
                         accounts=accounts,
                         today=date.today().strftime('%Y-%m-%d'))

@bp.route('/accounts')
def accounts():
    """Управление счетами"""
    users = User.query.filter_by(is_active=True).all()
    
    # Подсчитываем статистику
    total_accounts = 0
    debit_count = 0
    credit_count = 0
    total_balance = 0
    
    for user in users:
        user_accounts = user.accounts.filter_by(is_active=True).all()
        total_accounts += len(user_accounts)
        total_balance += user.get_total_balance()
        
        for account in user_accounts:
            if account.account_type == 'debit':
                debit_count += 1
            elif account.account_type == 'credit':
                credit_count += 1
    
    stats = {
        'total_accounts': total_accounts,
        'debit_count': debit_count,
        'credit_count': credit_count,
        'total_balance': total_balance
    }
    
    return render_template('accounts.html', users=users, stats=stats)

@bp.route('/add_account', methods=['POST'])
def add_account():
    """Добавление нового счета"""
    try:
        name = request.form['name']
        account_type = request.form['account_type']
        user_id = int(request.form['user_id'])
        initial_balance = float(request.form.get('balance', 0))
        goal_amount = request.form.get('goal_amount')
        include_in_balance = 'include_in_balance' in request.form
        
        account = Account(
            name=name,
            account_type=account_type,
            user_id=user_id,
            balance=initial_balance,
            goal_amount=float(goal_amount) if goal_amount and goal_amount != '' else None,
            include_in_balance=include_in_balance
        )
        
        db.session.add(account)
        db.session.commit()
        flash('Счет успешно добавлен!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при добавлении счета: {str(e)}', 'error')
    
    return redirect(url_for('main.accounts'))

@bp.route('/accounts/<int:account_id>/edit', methods=['GET', 'POST'])
def edit_account(account_id):
    """Редактировать счет"""
    account = Account.query.get_or_404(account_id)
    users = User.query.filter_by(is_active=True).all()
    
    if request.method == 'POST':
        try:
            # Проверка прав доступа
            is_valid, entity = check_entity_access(account, "счет")
            if not is_valid:
                flash(entity, 'danger')
                return redirect(url_for('main.accounts'))
            
            # Валидация названия счета
            name = request.form.get('name', '')
            is_valid, name_clean = validate_text_input(name, 'название счета', min_length=2, max_length=100)
            if not is_valid:
                flash(name_clean, 'danger')
                return render_template('edit_account.html', account=account, users=users)
            
            # Валидация банка
            bank = request.form.get('bank', '')
            is_valid, bank_clean = validate_text_input(bank, 'банк', min_length=0, max_length=100, required=False)
            if not is_valid:
                flash(bank_clean, 'danger')
                return render_template('edit_account.html', account=account, users=users)
            
            # Валидация типа счета
            account_type = request.form.get('account_type', '')
            allowed_types = ['checking', 'savings', 'credit', 'cash', 'investment']
            if account_type not in allowed_types:
                flash('Некорректный тип счета', 'danger')
                return render_template('edit_account.html', account=account, users=users)
            
            # Валидация валюты
            currency = request.form.get('currency', 'RUB')
            allowed_currencies = ['RUB', 'USD', 'EUR', 'CNY', 'KZT']
            if currency not in allowed_currencies:
                flash('Неподдерживаемая валюта', 'danger')
                return render_template('edit_account.html', account=account, users=users)
            
            # Валидация баланса
            balance_str = request.form.get('balance', '0')
            is_valid, balance_value = validate_amount(balance_str)
            if not is_valid:
                flash(f'Ошибка в балансе: {balance_value}', 'danger')
                return render_template('edit_account.html', account=account, users=users)
            
            # Валидация пользователя
            user_id = request.form.get('user_id')
            if user_id:
                try:
                    user_id = int(user_id)
                    user = User.query.get(user_id)
                    if not user or not user.is_active:
                        flash('Выбранный пользователь не найден или неактивен', 'danger')
                        return render_template('edit_account.html', account=account, users=users)
                except (ValueError, TypeError):
                    flash('Некорректный ID пользователя', 'danger')
                    return render_template('edit_account.html', account=account, users=users)
            else:
                flash('Необходимо выбрать владельца счета', 'danger')
                return render_template('edit_account.html', account=account, users=users)
            
            # Обновляем поля счета
            account.name = sanitize_sql_input(name_clean)
            account.bank = sanitize_sql_input(bank_clean) if bank_clean else None
            account.account_type = account_type
            account.currency = currency
            account.balance = balance_value
            account.is_active = bool(request.form.get('is_active'))
            account.user_id = user_id
            
            db.session.commit()
            flash('Счет успешно обновлен!', 'success')
            return redirect(url_for('main.accounts'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении счета: {str(e)}', 'danger')
    
    return render_template('edit_account.html', account=account, users=users)

@bp.route('/delete_account/<int:account_id>', methods=['POST'])
def delete_account(account_id):
    """Удаление счета"""
    try:
        account = Account.query.get_or_404(account_id)
        
        # Проверяем, есть ли транзакции по этому счету
        transactions_count = Transaction.query.filter(
            (Transaction.from_account_id == account_id) |
            (Transaction.to_account_id == account_id)
        ).count()
        
        if transactions_count > 0:
            flash('Нельзя удалить счет с существующими транзакциями!', 'error')
        else:
            db.session.delete(account)
            db.session.commit()
            flash('Счет успешно удален!', 'success')
            
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении счета: {str(e)}', 'error')
    
    return redirect(url_for('main.accounts'))

@bp.route('/api/categories/<transaction_type>')
def api_categories(transaction_type):
    """API для получения категорий по типу транзакции"""
    categories = Category.query.filter_by(
        category_type=transaction_type,
        is_active=True
    ).all()
    
    return jsonify([{
        'id': cat.id,
        'name': cat.name
    } for cat in categories])

# ============ CATEGORIES MANAGEMENT ============

@bp.route('/categories')
def categories():
    """Управление категориями"""
    categories_by_type = {
        'income': Category.query.filter_by(category_type='income', is_active=True).order_by(Category.name).all(),
        'expense': Category.query.filter_by(category_type='expense', is_active=True).order_by(Category.name).all(),
        'transfer': Category.query.filter_by(category_type='transfer', is_active=True).order_by(Category.name).all()
    }
    
    stats = {
        'total_categories': Category.query.filter_by(is_active=True).count(),
        'income_count': len(categories_by_type['income']),
        'expense_count': len(categories_by_type['expense']),
        'transfer_count': len(categories_by_type['transfer'])
    }
    
    return render_template('categories.html', 
                         categories=categories_by_type,
                         stats=stats)

@bp.route('/categories/add', methods=['GET', 'POST'])
def add_category():
    """Добавление новой категории"""
    if request.method == 'POST':
        # Валидация названия
        name = request.form.get('name', '')
        is_valid, name_clean = validate_text_input(name, 'название категории', min_length=2, max_length=100)
        if not is_valid:
            flash(name_clean, 'danger')
            return render_template('add_category.html')
        
        # Валидация типа
        category_type = request.form.get('category_type', '')
        if category_type not in ['income', 'expense', 'transfer']:
            flash('Недопустимый тип категории', 'danger')
            return render_template('add_category.html')
        
        # Валидация описания
        description = request.form.get('description', '')
        is_valid, description_clean = validate_text_input(description, 'описание', min_length=0, max_length=255, required=False)
        if not is_valid:
            flash(description_clean, 'danger')
            return render_template('add_category.html')
        
        # Проверка на дубликат
        existing = Category.query.filter_by(name=name_clean, category_type=category_type).first()
        if existing:
            flash(f'Категория "{name_clean}" уже существует для типа "{category_type}"', 'warning')
            return render_template('add_category.html')
            
        category = Category(
            name=sanitize_sql_input(name_clean),
            category_type=category_type,
            description=sanitize_sql_input(description_clean) if description_clean else None,
            is_active=True
        )
        
        db.session.add(category)
        db.session.commit()
        
        flash(f'Категория "{name}" успешно добавлена', 'success')
        return redirect(url_for('main.categories'))
    
    return render_template('add_category.html')

@bp.route('/categories/<int:category_id>/edit', methods=['GET', 'POST'])
def edit_category(category_id):
    """Редактирование категории"""
    category = Category.query.get_or_404(category_id)
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category_type = request.form.get('category_type', '').strip()
        description = request.form.get('description', '').strip()
        is_active = request.form.get('is_active') == 'on'
        
        if not name or not category_type:
            flash('Название и тип категории обязательны', 'danger')
            return render_template('edit_category.html', category=category)
            
        if category_type not in ['income', 'expense', 'transfer']:
            flash('Недопустимый тип категории', 'danger')
            return render_template('edit_category.html', category=category)
            
        # Проверка на дубликат (кроме текущей категории)
        existing = Category.query.filter_by(name=name, category_type=category_type).filter(Category.id != category_id).first()
        if existing:
            flash(f'Категория "{name}" уже существует для типа "{category_type}"', 'warning')
            return render_template('edit_category.html', category=category)
            
        category.name = name
        category.category_type = category_type
        category.description = description or None
        category.is_active = is_active
        
        db.session.commit()
        
        flash(f'Категория "{name}" успешно обновлена', 'success')
        return redirect(url_for('main.categories'))
    
    return render_template('edit_category.html', category=category)

@bp.route('/categories/<int:category_id>/delete', methods=['POST'])
def delete_category(category_id):
    """Удаление категории"""
    category = Category.query.get_or_404(category_id)
    
    # Проверяем, есть ли транзакции с этой категорией
    transaction_count = Transaction.query.filter_by(category_id=category_id).count()
    
    if transaction_count > 0:
        flash(f'Нельзя удалить категорию "{category.name}", так как с ней связано {transaction_count} транзакций. Вы можете деактивировать категорию.', 'danger')
        return redirect(url_for('main.categories'))
    
    # Проверяем, есть ли правила мерчантов с этой категорией  
    rule_count = MerchantRule.query.filter_by(category_id=category_id).count()
    
    if rule_count > 0:
        flash(f'Нельзя удалить категорию "{category.name}", так как с ней связано {rule_count} правил мерчантов. Сначала удалите или измените эти правила.', 'danger')
        return redirect(url_for('main.categories'))
    
    category_name = category.name
    db.session.delete(category)
    db.session.commit()
    
    flash(f'Категория "{category_name}" успешно удалена', 'success')
    return redirect(url_for('main.categories'))

# ============ BULK OPERATIONS ============

@bp.route('/transactions/bulk-delete', methods=['POST'])
def bulk_delete_transactions():
    """Массовое удаление транзакций"""
    try:
        transaction_ids = request.form.get('transaction_ids', '')
        if not transaction_ids:
            flash('Не выбраны транзакции для удаления', 'warning')
            return redirect(url_for('main.transactions'))
        
        # Преобразуем строку ID в список чисел
        try:
            ids = [int(id.strip()) for id in transaction_ids.split(',') if id.strip()]
        except ValueError:
            flash('Некорректные ID транзакций', 'danger')
            return redirect(url_for('main.transactions'))
        
        if not ids:
            flash('Не выбраны транзакции для удаления', 'warning')
            return redirect(url_for('main.transactions'))
        
        # Проверяем права доступа и существование транзакций
        transactions = Transaction.query.filter(Transaction.id.in_(ids)).all()
        
        if len(transactions) != len(ids):
            flash('Некоторые транзакции не найдены', 'warning')
        
        deleted_count = 0
        total_amount = 0
        
        for transaction in transactions:
            total_amount += float(transaction.amount)
            db.session.delete(transaction)
            deleted_count += 1
        
        db.session.commit()
        
        flash(f'Успешно удалено {deleted_count} транзакций на общую сумму {total_amount:,.2f} ₽', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении транзакций: {str(e)}', 'danger')
    
    return redirect(url_for('main.transactions'))

@bp.route('/transactions/bulk-change-category', methods=['POST'])
def bulk_change_category():
    """Массовое изменение категории транзакций"""
    try:
        transaction_ids = request.form.get('transaction_ids', '')
        category_id = request.form.get('category_id')
        
        if not transaction_ids or not category_id:
            flash('Не указаны транзакции или категория', 'warning')
            return redirect(url_for('main.transactions'))
        
        # Валидация категории
        try:
            category_id = int(category_id)
            category = Category.query.get(category_id)
            if not category or not category.is_active:
                flash('Выбранная категория не найдена или неактивна', 'danger')
                return redirect(url_for('main.transactions'))
        except (ValueError, TypeError):
            flash('Некорректный ID категории', 'danger')
            return redirect(url_for('main.transactions'))
        
        # Преобразуем строку ID в список чисел
        try:
            ids = [int(id.strip()) for id in transaction_ids.split(',') if id.strip()]
        except ValueError:
            flash('Некорректные ID транзакций', 'danger')
            return redirect(url_for('main.transactions'))
        
        if not ids:
            flash('Не выбраны транзакции для изменения', 'warning')
            return redirect(url_for('main.transactions'))
        
        # Получаем транзакции для обновления
        transactions = Transaction.query.filter(Transaction.id.in_(ids)).all()
        
        if len(transactions) != len(ids):
            flash('Некоторые транзакции не найдены', 'warning')
        
        updated_count = 0
        
        for transaction in transactions:
            transaction.category_id = category_id
            updated_count += 1
        
        db.session.commit()
        
        flash(f'Успешно изменена категория для {updated_count} транзакций на "{category.name}"', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при изменении категории: {str(e)}', 'danger')
    
    return redirect(url_for('main.transactions'))

@bp.route('/transactions/bulk-delete-all', methods=['POST'])
def bulk_delete_all_transactions():
    """Удаление всех транзакций в базе данных"""
    try:
        # Подсчет всех транзакций для информации
        all_transactions = Transaction.query.all()
        total_count = len(all_transactions)
        total_amount = sum(float(t.amount) for t in all_transactions)
        
        # Сначала удаляем все связанные записи в transaction_snapshots
        db.session.execute(text("DELETE FROM transaction_snapshots"))
        
        # Затем удаляем все транзакции
        Transaction.query.delete()
        db.session.commit()
        
        flash(f'Успешно удалено {total_count} транзакций на общую сумму {total_amount:,.2f} ₽', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении всех транзакций: {str(e)}', 'danger')
    
    return redirect(url_for('main.transactions'))

@bp.route('/transactions/bulk-change-category-all', methods=['POST'])
def bulk_change_category_all():
    """Массовое изменение категории всех транзакций в базе данных"""
    try:
        category_id = request.form.get('category_id')
        
        if not category_id:
            flash('Не указана категория', 'warning')
            return redirect(url_for('main.transactions'))
        
        # Валидация категории
        try:
            category_id = int(category_id)
            category = Category.query.get(category_id)
            if not category or not category.is_active:
                flash('Выбранная категория не найдена или неактивна', 'danger')
                return redirect(url_for('main.transactions'))
        except (ValueError, TypeError):
            flash('Некорректный ID категории', 'danger')
            return redirect(url_for('main.transactions'))
        
        # Обновляем категорию для всех транзакций
        updated_count = Transaction.query.update({Transaction.category_id: category_id})
        db.session.commit()
        
        flash(f'Успешно изменена категория для {updated_count} транзакций на "{category.name}"', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при изменении категории всех транзакций: {str(e)}', 'danger')
    
    return redirect(url_for('main.transactions'))

@bp.route('/api/accounts/<int:user_id>')
def api_user_accounts(user_id):
    """API для получения счетов пользователя"""
    accounts = Account.query.filter_by(
        user_id=user_id,
        is_active=True
    ).all()
    
    return jsonify([{
        'id': acc.id,
        'name': acc.name,
        'balance': float(acc.balance)
    } for acc in accounts])

@bp.route('/import', methods=['GET', 'POST'])
def import_bank_statement():
    """Import bank statement with preview"""
    if request.method == 'GET':
        # Show import form
        import_service = BankImportService()
        supported_banks = import_service.get_supported_banks()
        users = User.query.filter_by(is_active=True).all()
        accounts = Account.query.filter_by(is_active=True).all()
        
        return render_template('import_statement.html', 
                             supported_banks=supported_banks,
                             users=users,
                             accounts=accounts)
    
    # Handle file upload and create preview
    try:
        if 'statement_file' not in request.files:
            flash('No file uploaded', 'error')
            return redirect(request.url)
        
        file = request.files['statement_file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)
        
        # Get form data
        bank_type = request.form.get('bank_type')
        default_account_id = request.form.get('default_account_id')
        
        if not default_account_id:
            flash('Please select a default account', 'error')
            return redirect(request.url)
        
        # Save uploaded file temporarily
        filename = secure_filename(file.filename)
        upload_path = os.path.join('instance', 'uploads')
        os.makedirs(upload_path, exist_ok=True)
        file_path = os.path.join(upload_path, filename)
        file.save(file_path)
        
        try:
            # Parse transactions for preview
            import_service = BankImportService()
            transactions, detected_bank = import_service.import_transactions(
                file_path, filename, bank_type
            )
            
            if not transactions:
                flash('No transactions found in the file', 'warning')
                return redirect(request.url)
            
            # Create preview session
            session_id = str(uuid.uuid4())
            preview = ImportPreview(
                session_id=session_id,
                filename=filename,
                bank_type=detected_bank,
                default_account_id=int(default_account_id),
                total_transactions=len(transactions),
                expires_at=datetime.utcnow() + timedelta(hours=24)
            )
            db.session.add(preview)
            db.session.flush()
            
            duplicates_count = 0
            
            # Process each transaction for preview
            for trans_data in transactions:
                # Check for duplicates
                existing = Transaction.query.filter_by(
                    date=trans_data.date,
                    amount=trans_data.amount,
                    description=trans_data.description
                ).first()
                
                is_duplicate = existing is not None
                if is_duplicate:
                    duplicates_count += 1
                
                # Create preview transaction
                preview_trans = ImportPreviewTransaction(
                    preview_id=preview.id,
                    date=trans_data.date,
                    amount=trans_data.amount,
                    description=trans_data.description,
                    subcategory=trans_data.subcategory,
                    transaction_type=trans_data.transaction_type,
                    category_name=trans_data.category,
                    contact_phone=trans_data.contact_phone,
                    reference=trans_data.reference,
                    is_duplicate=is_duplicate,
                    duplicate_reason='Identical transaction found' if is_duplicate else None,
                    status='excluded' if is_duplicate else 'selected'
                )
                db.session.add(preview_trans)
            
            preview.duplicates_found = duplicates_count
            db.session.commit()
            
            return redirect(url_for('main.import_preview', session_id=session_id))
            
        finally:
            # Clean up temporary file
            try:
                os.remove(file_path)
            except:
                pass
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error processing file: {str(e)}', 'error')
        return redirect(request.url)


@bp.route('/import/preview/<session_id>')
def import_preview(session_id):
    """Show import preview with transaction details"""
    preview = ImportPreview.query.filter_by(session_id=session_id).first_or_404()
    
    # Check if preview hasn't expired
    if datetime.utcnow() > preview.expires_at:
        flash('Preview session has expired', 'error')
        return redirect(url_for('main.import_bank_statement'))
    
    # Get preview transactions with pagination
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    preview_transactions = preview.preview_transactions.order_by(
        ImportPreviewTransaction.date.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    # Calculate summary statistics
    selected_transactions = preview.preview_transactions.filter_by(status='selected').all()
    excluded_transactions = preview.preview_transactions.filter_by(status='excluded').all()
    
    # Basic counts
    income_transactions = [t for t in selected_transactions if t.transaction_type == 'income']
    expense_transactions = [t for t in selected_transactions if t.transaction_type == 'expense']
    
    # Identify transfers (SBP, Financial category operations)
    transfers = [t for t in selected_transactions if 
                 'financial' in t.category_name.lower() or 
                 'сбп' in t.description.lower() or 
                 'sbp' in t.description.lower() or
                 'перевод' in t.description.lower()]
    
    # Identify salary/income (common salary keywords)
    salary_keywords = ['зарплата', 'заработная плата', 'оклад', 'salary', 'зп', 'premium', 'премия']
    salary_transactions = [t for t in income_transactions if 
                          any(keyword in t.description.lower() for keyword in salary_keywords)]
    
    # Calculate category breakdown for expenses
    expense_categories = {}
    for t in expense_transactions:
        category = t.category_name
        if category not in expense_categories:
            expense_categories[category] = {'count': 0, 'amount': 0}
        expense_categories[category]['count'] += 1
        expense_categories[category]['amount'] += float(t.amount)
    
    summary = {
        'total': preview.total_transactions,
        'selected': len(selected_transactions),
        'excluded': len(excluded_transactions),
        'duplicates': preview.duplicates_found,
        'total_amount_selected': sum(float(t.amount) for t in selected_transactions),
        'income_amount': sum(float(t.amount) for t in income_transactions),
        'expense_amount': sum(float(t.amount) for t in expense_transactions),
        
        # Detailed breakdowns
        'income_count': len(income_transactions),
        'expense_count': len(expense_transactions),
        'transfers_count': len(transfers),
        'transfers_amount': sum(float(t.amount) for t in transfers),
        'salary_count': len(salary_transactions),
        'salary_amount': sum(float(t.amount) for t in salary_transactions),
        
        # Category breakdown
        'expense_categories': dict(sorted(expense_categories.items(), key=lambda x: x[1]['amount'], reverse=True)),
        'top_categories': dict(list(sorted(expense_categories.items(), key=lambda x: x[1]['amount'], reverse=True))[:5])
    }
    
    return render_template('import_preview.html',
                         preview=preview,
                         transactions=preview_transactions,
                         summary=summary)


@bp.route('/import/confirm', methods=['POST'])
def import_confirm():
    """Confirm and execute the import"""
    session_id = request.form.get('session_id')
    if not session_id:
        flash('Invalid session', 'error')
        return redirect(url_for('main.import_bank_statement'))
    
    preview = ImportPreview.query.filter_by(session_id=session_id).first_or_404()
    
    try:
        # Create data version before import
        version = DataVersion(
            version_name=f"Import {preview.bank_type.title()} Bank - {preview.filename}",
            description=f"Imported {preview.total_transactions} transactions from {preview.filename}",
            created_by='System',
            is_current=False
        )
        db.session.add(version)
        db.session.flush()
        
        # Get account balance before import
        default_account = preview.default_account
        balance_before = default_account.balance
        
        # Import selected transactions
        selected_transactions = preview.preview_transactions.filter_by(status='selected').all()
        imported_count = 0
        
        for preview_trans in selected_transactions:
            try:
                # Find or create category
                category = Category.query.filter_by(
                    name=preview_trans.category_name,
                    category_type='expense' if preview_trans.transaction_type == 'expense' else 'income'
                ).first()
                
                if not category:
                    # Create new category
                    category = Category(
                        name=preview_trans.category_name,
                        category_type='expense' if preview_trans.transaction_type == 'expense' else 'income'
                    )
                    db.session.add(category)
                    db.session.flush()
                
                # Create transaction
                transaction = Transaction(
                    date=preview_trans.date,
                    amount=preview_trans.amount,
                    description=preview_trans.description,
                    subcategory=preview_trans.subcategory,
                    transaction_type=preview_trans.transaction_type,
                    contact_phone=preview_trans.contact_phone,
                    reference=preview_trans.reference,
                    category_id=category.id,
                    from_account_id=default_account.id if preview_trans.transaction_type == 'expense' else None,
                    to_account_id=default_account.id if preview_trans.transaction_type == 'income' else None
                )
                
                db.session.add(transaction)
                db.session.flush()
                
                # Автоматически создаем контакт если указан номер телефона
                if preview_trans.contact_phone:
                    Transaction.create_contact_from_phone(preview_trans.contact_phone)
                
                # Create transaction snapshot
                snapshot = TransactionSnapshot(
                    version_id=version.id,
                    transaction_id=transaction.id,
                    operation_type='created',
                    date=transaction.date,
                    amount=transaction.amount,
                    description=transaction.description,
                    transaction_type=transaction.transaction_type,
                    category_id=transaction.category_id,
                    from_account_id=transaction.from_account_id,
                    to_account_id=transaction.to_account_id,
                    created_at=transaction.created_at
                )
                db.session.add(snapshot)
                
                # Update account balance
                if preview_trans.transaction_type == 'expense':
                    default_account.balance -= preview_trans.amount
                else:
                    default_account.balance += preview_trans.amount
                
                imported_count += 1
                
            except Exception as e:
                # Skip problematic transactions
                continue
        
        # Create account balance snapshot
        balance_after = default_account.balance
        account_snapshot = AccountSnapshot(
            version_id=version.id,
            account_id=default_account.id,
            balance_before=balance_before,
            balance_after=balance_after,
            balance_change=balance_after - balance_before
        )
        db.session.add(account_snapshot)
        
        # Mark version as current
        version.is_current = True
        
        # Clean up preview data
        db.session.delete(preview)
        
        db.session.commit()
        
        flash(f'Successfully imported {imported_count} transactions from {preview.bank_type.title()} Bank', 'success')
        return redirect(url_for('main.transactions'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error importing transactions: {str(e)}', 'error')
        return redirect(url_for('main.import_preview', session_id=session_id))


@bp.route('/import/preview/toggle_transaction', methods=['POST'])
def toggle_preview_transaction():
    """Toggle transaction selection in preview"""
    data = request.get_json()
    transaction_id = data.get('transaction_id')
    
    preview_trans = ImportPreviewTransaction.query.get_or_404(transaction_id)
    
    # Toggle status (exclude duplicates from being selected)
    if not preview_trans.is_duplicate:
        preview_trans.status = 'excluded' if preview_trans.status == 'selected' else 'selected'
        db.session.commit()
        
        return jsonify({'status': 'success', 'new_status': preview_trans.status})
    
    return jsonify({'status': 'error', 'message': 'Cannot select duplicate transactions'})


@bp.route('/versions')
def data_versions():
    """Show data versions history"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    versions = DataVersion.query.order_by(desc(DataVersion.created_at)).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('data_versions.html', versions=versions)


@bp.route('/versions/<int:version_id>')
def version_details(version_id):
    """Show version details with changes"""
    version = DataVersion.query.get_or_404(version_id)
    
    # Get transaction changes
    transaction_snapshots = version.transaction_snapshots.order_by(
        desc(TransactionSnapshot.date)
    ).all()
    
    # Get account changes
    account_snapshots = version.account_snapshots.all()
    
    # Calculate statistics
    changes_summary = version.get_changes_summary()
    
    return render_template('version_details.html',
                         version=version,
                         transaction_snapshots=transaction_snapshots,
                         account_snapshots=account_snapshots,
                         changes_summary=changes_summary)


@bp.route('/versions/restore/<int:version_id>', methods=['POST'])
def restore_version(version_id):
    """Restore data to a specific version (placeholder for now)"""
    version = DataVersion.query.get_or_404(version_id)
    
    # This is a complex operation that would require careful implementation
    # For now, just show a message
    flash(f'Version restore functionality is under development. Version: {version.version_name}', 'info')
    return redirect(url_for('main.data_versions'))


@bp.route('/about')
def about():
    """Show application version and info"""
    version_info = get_version_info()
    return render_template('about.html', version_info=version_info)


@bp.route('/profile')
def profile():
    """Управление профилем пользователя"""
    # Получаем всех пользователей системы (Муж/Жена)
    users = User.query.filter_by(is_active=True).all()
    
    # Получаем общие настройки
    user_profile = UserProfile.query.first()
    if not user_profile:
        # Создаём профиль по умолчанию
        user_profile = UserProfile(name='Family')
        db.session.add(user_profile)
        db.session.commit()
    
    return render_template('profile.html', profile=user_profile, users=users)


@bp.route('/profile', methods=['POST'])
def update_profile():
    """Обновление профиля пользователя"""
    user_profile = UserProfile.query.first()
    if not user_profile:
        user_profile = UserProfile()
        db.session.add(user_profile)
    
    user_profile.name = request.form.get('name', 'User')
    user_profile.phone = request.form.get('phone', '').strip() or None
    user_profile.email = request.form.get('email', '').strip() or None
    user_profile.updated_at = datetime.utcnow()
    
    try:
        db.session.commit()
        flash('Профиль обновлён успешно!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при обновлении профиля: {str(e)}', 'danger')
    
    return redirect(url_for('main.profile'))


@bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
def edit_user(user_id):
    """Редактировать пользователя"""
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        user.name = request.form.get('name', user.name).strip()
        
        # Обработка номеров телефонов
        phone_numbers = request.form.getlist('phone_numbers[]')
        user.phone_numbers = []  # Сброс списка
        
        for phone in phone_numbers:
            phone = phone.strip()
            if phone:  # Если номер не пустой
                if user.add_phone_number(phone):
                    pass  # Номер добавлен успешно
                else:
                    flash(f'Неверный формат номера телефона: {phone}', 'warning')
        
        # Обработка счета по умолчанию для СБП
        default_sbp_account_id = request.form.get('default_sbp_account_id')
        if default_sbp_account_id and default_sbp_account_id != '':
            user.default_sbp_account_id = int(default_sbp_account_id)
        else:
            user.default_sbp_account_id = None
        
        try:
            db.session.commit()
            flash(f'Пользователь {user.name} обновлён успешно!', 'success')
            return redirect(url_for('main.profile'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении пользователя: {str(e)}', 'danger')
    
    return render_template('edit_user.html', user=user)


@bp.route('/contacts')
def contacts():
    """Телефонная книга для СБП"""
    page = request.args.get('page', 1, type=int)
    per_page = 25
    
    contacts_query = Contact.query.order_by(Contact.name)
    contacts_paginated = contacts_query.paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('contacts.html', contacts=contacts_paginated)


# API эндпоинты для статистики контактов
@bp.route('/api/contacts/stats')
def api_contact_stats():
    """API для получения статистики по номеру телефона"""
    phone = request.args.get('phone')
    period = request.args.get('period', 'all')
    
    if not phone:
        return jsonify({'error': 'Phone parameter is required'}), 400
    
    contact = Contact.get_by_phone(phone)
    if not contact:
        return jsonify({
            'total_transactions': 0,
            'incoming_count': 0,
            'outgoing_count': 0,
            'incoming_amount': 0.0,
            'outgoing_amount': 0.0,
            'last_transaction_date': None,
            'first_transaction_date': None,
            'period': period
        })
    
    stats = contact.get_statistics(period)
    # Преобразуем даты в строки для JSON
    if stats['last_transaction_date']:
        stats['last_transaction_date'] = stats['last_transaction_date'].isoformat()
    if stats['first_transaction_date']:
        stats['first_transaction_date'] = stats['first_transaction_date'].isoformat()
    
    return jsonify(stats)


@bp.route('/api/contacts/summary')
def api_contacts_summary():
    """API для получения сводной статистики по всем контактам"""
    period = request.args.get('period', 'all')
    
    # Получаем все контакты
    contacts = Contact.query.all()
    
    total_contacts = len(contacts)
    contacts_with_transactions = 0
    total_incoming = 0.0
    total_outgoing = 0.0
    total_transactions = 0
    
    for contact in contacts:
        stats = contact.get_statistics(period)
        if stats['total_transactions'] > 0:
            contacts_with_transactions += 1
        total_incoming += stats['incoming_amount']
        total_outgoing += stats['outgoing_amount']
        total_transactions += stats['total_transactions']
    
    return jsonify({
        'total_contacts': total_contacts,
        'contacts_with_transactions': contacts_with_transactions,
        'total_incoming': total_incoming,
        'total_outgoing': total_outgoing,
        'total_transactions': total_transactions,
        'period': period
    })


@bp.route('/contacts/add', methods=['GET', 'POST'])
def add_contact():
    """Добавить контакт"""
    # Получаем номер телефона из URL параметра
    prefill_phone = request.args.get('phone', '').strip()
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        description = request.form.get('description', '').strip()
        
        if not name or not phone:
            flash('Имя и телефон обязательны для заполнения', 'danger')
            return render_template('add_contact.html')
        
        # Нормализуем номер
        normalized_phone = Contact.normalize_phone(phone)
        if not normalized_phone:
            flash('Некорректный формат номера телефона', 'danger')
            return render_template('add_contact.html')
        
        # Проверяем уникальность
        existing = Contact.query.filter_by(phone=f"+7{normalized_phone[-10:]}").first()
        if existing:
            flash(f'Контакт с номером {phone} уже существует', 'warning')
            return redirect(url_for('main.contacts'))
        
        contact = Contact(
            name=name,
            phone=f"+7{normalized_phone[-10:]}",
            description=description or None
        )
        
        try:
            db.session.add(contact)
            db.session.commit()
            flash(f'Контакт {name} добавлен успешно!', 'success')
            return redirect(url_for('main.contacts'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при добавлении контакта: {str(e)}', 'danger')
    
    return render_template('add_contact.html', prefill_phone=prefill_phone)


@bp.route('/contacts/<int:contact_id>/edit', methods=['GET', 'POST'])
def edit_contact(contact_id):
    """Редактировать контакт"""
    contact = Contact.query.get_or_404(contact_id)
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        description = request.form.get('description', '').strip()
        
        if not name or not phone:
            flash('Имя и телефон обязательны для заполнения', 'danger')
            return render_template('edit_contact.html', contact=contact)
        
        # Нормализуем номер
        normalized_phone = Contact.normalize_phone(phone)
        if not normalized_phone:
            flash('Некорректный формат номера телефона', 'danger')
            return render_template('edit_contact.html', contact=contact)
        
        new_phone = f"+7{normalized_phone[-10:]}"
        
        # Проверяем уникальность, если номер изменился
        if new_phone != contact.phone:
            existing = Contact.query.filter_by(phone=new_phone).first()
            if existing:
                flash(f'Контакт с номером {phone} уже существует', 'warning')
                return render_template('edit_contact.html', contact=contact)
        
        contact.name = name
        contact.phone = new_phone
        contact.description = description or None
        contact.updated_at = datetime.utcnow()
        
        try:
            db.session.commit()
            flash(f'Контакт {name} обновлён успешно!', 'success')
            return redirect(url_for('main.contacts'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении контакта: {str(e)}', 'danger')
    
    return render_template('edit_contact.html', contact=contact)


@bp.route('/contacts/<int:contact_id>/history')
def contact_history(contact_id):
    """Просмотр истории транзакций контакта"""
    contact = Contact.query.get_or_404(contact_id)
    
    # Параметры пагинации
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    period = request.args.get('period', 'all')
    
    # Получаем все транзакции контакта
    transactions = contact.get_related_transactions()
    
    # Фильтруем по периоду если нужно
    if period != 'all' and transactions:
        from datetime import datetime, timedelta
        now = datetime.now().date()
        if period == 'week':
            start_date = now - timedelta(days=7)
        elif period == 'month':
            start_date = now - timedelta(days=30)
        elif period == 'year':
            start_date = now - timedelta(days=365)
        else:
            start_date = None
        
        if start_date:
            transactions = [t for t in transactions if t.date >= start_date]
    
    # Пагинация
    total = len(transactions)
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    transactions_page = transactions[start_idx:end_idx]
    
    # Создаем объект пагинации
    class MockPagination:
        def __init__(self, items, page, per_page, total):
            self.items = items
            self.page = page
            self.per_page = per_page
            self.total = total
            self.pages = (total + per_page - 1) // per_page
            self.has_prev = page > 1
            self.has_next = page < self.pages
            self.prev_num = page - 1 if self.has_prev else None
            self.next_num = page + 1 if self.has_next else None
        
        def iter_pages(self, left_edge=2, right_edge=2, left_current=2, right_current=3):
            last = self.pages
            for num in range(1, last + 1):
                if num <= left_edge or \
                   (self.page - left_current - 1 < num < self.page + right_current) or \
                   num > last - right_edge:
                    yield num
                elif num == left_edge + 1 or num == self.page - left_current - 1 or \
                     num == self.page + right_current or num == last - right_edge:
                    yield None
    
    pagination = MockPagination(transactions_page, page, per_page, total)
    
    # Получаем статистику
    stats = contact.get_statistics(period)
    
    return render_template('contact_history.html', 
                         contact=contact, 
                         transactions=pagination,
                         stats=stats,
                         period=period)


@bp.route('/contacts/<int:contact_id>/delete', methods=['POST'])
def delete_contact(contact_id):
    """Удалить контакт"""
    contact = Contact.query.get_or_404(contact_id)
    
    # Проверяем, можно ли удалить контакт
    if not contact.can_be_deleted():
        if contact.is_user_contact:
            linked_user = contact.get_linked_user()
            if linked_user:
                flash(f'Контакт {contact.name} нельзя удалить, так как он привязан к пользователю {linked_user.name}', 'warning')
            else:
                flash(f'Контакт {contact.name} нельзя удалить, так как он привязан к пользователю системы', 'warning')
        else:
            flash(f'Контакт {contact.name} нельзя удалить, так как у него есть связанные транзакции', 'warning')
        return redirect(url_for('main.contacts'))
    
    try:
        db.session.delete(contact)
        db.session.commit()
        flash(f'Контакт {contact.name} удалён', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении контакта: {str(e)}', 'danger')
    
    return redirect(url_for('main.contacts'))


@bp.route('/merchant-rules')
def merchant_rules():
    """Справочник правил категоризации мерчантов"""
    page = request.args.get('page', 1, type=int)
    per_page = 25
    
    rules_query = MerchantRule.query.order_by(MerchantRule.priority.desc(), MerchantRule.created_at.desc())
    rules_paginated = rules_query.paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('merchant_rules.html', rules=rules_paginated)


@bp.route('/merchant-rules/add', methods=['GET', 'POST'])
def add_merchant_rule():
    """Добавить правило категоризации"""
    if request.method == 'POST':
        pattern = request.form.get('pattern', '').strip()
        merchant_name = request.form.get('merchant_name', '').strip()
        category_id = request.form.get('category_id', type=int)
        subcategory = request.form.get('subcategory', '').strip()
        priority = request.form.get('priority', 1, type=int)
        rule_type = request.form.get('rule_type', 'contains')
        
        if not pattern or not merchant_name or not category_id:
            flash('Шаблон, название мерчанта и категория обязательны для заполнения', 'danger')
            return render_template('add_merchant_rule.html', categories=Category.query.filter_by(is_active=True).all())
        
        # Проверяем, что категория существует
        category = Category.query.get(category_id)
        if not category:
            flash('Выбранная категория не найдена', 'danger')
            return render_template('add_merchant_rule.html', categories=Category.query.filter_by(is_active=True).all())
        
        rule = MerchantRule(
            pattern=pattern,
            merchant_name=merchant_name,
            category_id=category_id,
            subcategory=subcategory or None,
            priority=priority,
            rule_type=rule_type
        )
        
        try:
            db.session.add(rule)
            db.session.commit()
            flash(f'Правило для "{merchant_name}" добавлено успешно!', 'success')
            return redirect(url_for('main.merchant_rules'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при добавлении правила: {str(e)}', 'danger')
    
    categories = Category.query.filter_by(is_active=True).all()
    return render_template('add_merchant_rule.html', categories=categories)


@bp.route('/merchant-rules/<int:rule_id>/edit', methods=['GET', 'POST'])
def edit_merchant_rule(rule_id):
    """Редактировать правило категоризации"""
    rule = MerchantRule.query.get_or_404(rule_id)
    
    if request.method == 'POST':
        pattern = request.form.get('pattern', '').strip()
        merchant_name = request.form.get('merchant_name', '').strip()
        category_id = request.form.get('category_id', type=int)
        subcategory = request.form.get('subcategory', '').strip()
        priority = request.form.get('priority', 1, type=int)
        rule_type = request.form.get('rule_type', 'contains')
        is_active = 'is_active' in request.form
        
        if not pattern or not merchant_name or not category_id:
            flash('Шаблон, название мерчанта и категория обязательны для заполнения', 'danger')
            return render_template('edit_merchant_rule.html', rule=rule, categories=Category.query.filter_by(is_active=True).all())
        
        # Проверяем, что категория существует
        category = Category.query.get(category_id)
        if not category:
            flash('Выбранная категория не найдена', 'danger')
            return render_template('edit_merchant_rule.html', rule=rule, categories=Category.query.filter_by(is_active=True).all())
        
        rule.pattern = pattern
        rule.merchant_name = merchant_name
        rule.category_id = category_id
        rule.subcategory = subcategory or None
        rule.priority = priority
        rule.rule_type = rule_type
        rule.is_active = is_active
        rule.updated_at = datetime.utcnow()
        
        try:
            db.session.commit()
            flash(f'Правило "{merchant_name}" обновлено успешно!', 'success')
            return redirect(url_for('main.merchant_rules'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении правила: {str(e)}', 'danger')
    
    categories = Category.query.filter_by(is_active=True).all()
    return render_template('edit_merchant_rule.html', rule=rule, categories=categories)


@bp.route('/merchant-rules/<int:rule_id>/delete', methods=['POST'])
def delete_merchant_rule(rule_id):
    """Удалить правило категоризации"""
    rule = MerchantRule.query.get_or_404(rule_id)
    
    try:
        db.session.delete(rule)
        db.session.commit()
        flash(f'Правило "{rule.merchant_name}" удалено', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении правила: {str(e)}', 'danger')
    
    return redirect(url_for('main.merchant_rules'))


@bp.route('/transactions/<int:transaction_id>/edit', methods=['GET', 'POST'])
def edit_transaction(transaction_id):
    """Редактировать транзакцию"""
    transaction = Transaction.query.get_or_404(transaction_id)
    categories = Category.query.all()
    users = User.query.filter_by(is_active=True).all()
    
    if request.method == 'POST':
        try:
            # Проверка прав доступа
            is_valid, entity = check_entity_access(transaction, "транзакция")
            if not is_valid:
                flash(entity, 'danger')
                return redirect(url_for('main.transactions'))
            
            # Валидация даты
            date_str = request.form.get('date', '')
            is_valid, date_value = validate_date_input(date_str)
            if not is_valid:
                flash(f'Ошибка в дате: {date_value}', 'danger')
                return render_template('edit_transaction.html', transaction=transaction, categories=categories, users=users)
            
            # Валидация суммы
            amount_str = request.form.get('amount', '0')
            is_valid, amount_value = validate_amount(amount_str)
            if not is_valid:
                flash(f'Ошибка в сумме: {amount_value}', 'danger')
                return render_template('edit_transaction.html', transaction=transaction, categories=categories, users=users)
            
            # Валидация описания
            description = request.form.get('description', '')
            is_valid, description_clean = validate_text_input(description, 'описание', min_length=0, max_length=500, required=False)
            if not is_valid:
                flash(description_clean, 'danger')
                return render_template('edit_transaction.html', transaction=transaction, categories=categories, users=users)
            
            # Валидация типа транзакции
            transaction_type = request.form.get('transaction_type', '')
            if transaction_type not in ['income', 'expense', 'transfer']:
                flash('Некорректный тип транзакции', 'danger')
                return render_template('edit_transaction.html', transaction=transaction, categories=categories, users=users)
            
            # Валидация телефона
            contact_phone = request.form.get('contact_phone', '')
            is_valid, phone_clean = validate_phone_number(contact_phone)
            if not is_valid:
                flash(f'Ошибка в телефоне: {phone_clean}', 'danger')
                return render_template('edit_transaction.html', transaction=transaction, categories=categories, users=users)
            
            # Валидация категории
            category_id = request.form.get('category_id')
            if category_id:
                try:
                    category_id = int(category_id)
                    category = Category.query.get(category_id)
                    if not category or not category.is_active:
                        flash('Выбранная категория не найдена или неактивна', 'danger')
                        return render_template('edit_transaction.html', transaction=transaction, categories=categories, users=users)
                except (ValueError, TypeError):
                    flash('Некорректный ID категории', 'danger')
                    return render_template('edit_transaction.html', transaction=transaction, categories=categories, users=users)
            
            # Валидация подкатегории
            subcategory = request.form.get('subcategory', '')
            is_valid, subcategory_clean = validate_text_input(subcategory, 'подкатегория', min_length=0, max_length=100, required=False)
            if not is_valid:
                flash(subcategory_clean, 'danger')
                return render_template('edit_transaction.html', transaction=transaction, categories=categories, users=users)
            
            # Обновляем поля транзакции
            transaction.date = date_value
            transaction.amount = amount_value
            transaction.description = sanitize_sql_input(description_clean)
            transaction.transaction_type = transaction_type
            transaction.contact_phone = phone_clean if phone_clean else None
            transaction.category_id = category_id
            transaction.subcategory = sanitize_sql_input(subcategory_clean) if subcategory_clean else None
            
            # Автоматически создаем контакт если указан номер телефона
            if phone_clean:
                Transaction.create_contact_from_phone(phone_clean)
            
            db.session.commit()
            flash('Транзакция успешно обновлена!', 'success')
            return redirect(url_for('main.transactions'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении транзакции: {str(e)}', 'danger')
    
    return render_template('edit_transaction.html', transaction=transaction, categories=categories, users=users)


@bp.route('/transactions/<int:transaction_id>/delete', methods=['POST'])
def delete_transaction(transaction_id):
    """Удалить транзакцию"""
    transaction = Transaction.query.get_or_404(transaction_id)
    
    try:
        # Сохраняем информацию для сообщения
        amount = transaction.amount
        description = transaction.description
        
        db.session.delete(transaction)
        db.session.commit()
        flash(f'Транзакция "{description}" на сумму {amount:,.2f} ₽ удалена', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении транзакции: {str(e)}', 'danger')
    
    return redirect(url_for('main.transactions'))


@bp.route('/merchant-rules/test', methods=['POST'])
def test_merchant_rule():
    """Тестировать правило на описании"""
    description = request.form.get('description', '').strip()
    
    if not description:
        return jsonify({'error': 'Описание не указано'}), 400
    
    matching_rule = MerchantRule.find_matching_rule(description)
    
    if matching_rule:
        return jsonify({
            'matched': True,
            'rule_id': matching_rule.id,
            'pattern': matching_rule.pattern,
            'merchant_name': matching_rule.merchant_name,
            'category': matching_rule.category.name,
            'subcategory': matching_rule.subcategory,
            'priority': matching_rule.priority
        })
    else:
        return jsonify({'matched': False})


# Context processor to make version available in all templates
@bp.app_context_processor
def inject_version():
    """Inject version info into all templates"""
    return {
        'app_version': get_app_version(),
        'app_simple_version': get_version_info()['version']
    }