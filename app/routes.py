from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from datetime import date, datetime
from app import db
from app.models import User, Account, Transaction, Category
from sqlalchemy import func, desc

bp = Blueprint('main', __name__)

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
            amount = float(request.form['amount'])
            description = request.form.get('description', '')
            category_id = int(request.form['category_id'])
            transaction_date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
            
            from_account_id = request.form.get('from_account_id')
            to_account_id = request.form.get('to_account_id')
            
            # Создаем транзакцию
            transaction = Transaction(
                transaction_type=transaction_type,
                amount=amount,
                description=description,
                category_id=category_id,
                date=transaction_date,
                from_account_id=int(from_account_id) if from_account_id else None,
                to_account_id=int(to_account_id) if to_account_id else None
            )
            
            db.session.add(transaction)
            
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