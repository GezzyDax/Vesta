from datetime import datetime, date
from app import db
from sqlalchemy import func

class User(db.Model):
    """Модель пользователя (Муж/Жена)"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # Муж/Жена
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Связи
    accounts = db.relationship('Account', backref='owner', lazy='dynamic')
    
    def __repr__(self):
        return f'<User {self.name}>'
    
    def get_total_balance(self):
        """Общий баланс всех счетов пользователя (исключая кредитки)"""
        return sum(account.balance for account in self.accounts 
                  if account.is_active and account.include_in_balance)
    
    def get_total_balance_with_credit(self):
        """Общий баланс включая кредитки"""
        return sum(account.balance for account in self.accounts if account.is_active)

class Account(db.Model):
    """Модель банковского счета/карты"""
    __tablename__ = 'accounts'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # Название счета
    account_type = db.Column(db.String(20), nullable=False)  # debit, credit, savings, cash, savings_goal
    balance = db.Column(db.Numeric(15, 2), default=0.00)
    currency = db.Column(db.String(3), default='RUB')
    is_active = db.Column(db.Boolean, default=True)
    include_in_balance = db.Column(db.Boolean, default=True)  # Включать в общий баланс (false для кредиток)
    goal_amount = db.Column(db.Numeric(15, 2), default=None)  # Цель накопления (для savings_goal)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Связи
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    def __repr__(self):
        return f'<Account {self.name}: {self.balance} {self.currency}>'
    
    def get_account_type_display(self):
        """Отображаемое название типа счета"""
        types = {
            'debit': 'Дебетовая карта',
            'credit': 'Кредитная карта', 
            'savings': 'Сберегательный счет',
            'cash': 'Наличные',
            'savings_goal': 'Накопления'
        }
        return types.get(self.account_type, self.account_type)
    
    def get_savings_progress(self):
        """Прогресс накопления (для savings_goal)"""
        if self.account_type == 'savings_goal' and self.goal_amount:
            progress = (float(self.balance) / float(self.goal_amount)) * 100
            return min(100, max(0, progress))
        return None

class Category(db.Model):
    """Модель категории доходов/расходов"""
    __tablename__ = 'categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category_type = db.Column(db.String(20), nullable=False)  # income, expense, transfer
    parent_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True)  # Родительская категория
    color = db.Column(db.String(7), default='#007bff')  # HEX цвет
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    parent = db.relationship('Category', remote_side=[id], backref='children')
    
    def __repr__(self):
        return f'<Category {self.name} ({self.category_type})>'
    
    def get_category_type_display(self):
        """Отображаемое название типа категории"""
        types = {
            'income': 'Доходы',
            'expense': 'Расходы',
            'transfer': 'Переводы'
        }
        return types.get(self.category_type, self.category_type)
    
    def get_full_name(self):
        """Полное название с родительской категорией"""
        if self.parent:
            return f"{self.parent.name} → {self.name}"
        return self.name

class Transaction(db.Model):
    """Модель транзакции"""
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=date.today)
    amount = db.Column(db.Numeric(15, 2), nullable=False)
    description = db.Column(db.Text)
    transaction_type = db.Column(db.String(20), nullable=False)  # income, expense, transfer
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Связи
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    from_account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=True)  # Счет списания
    to_account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=True)    # Счет зачисления
    
    # Relationships
    category = db.relationship('Category', backref='transactions')
    from_account = db.relationship('Account', foreign_keys=[from_account_id], backref='outgoing_transactions')
    to_account = db.relationship('Account', foreign_keys=[to_account_id], backref='incoming_transactions')
    
    def __repr__(self):
        return f'<Transaction {self.amount} {self.transaction_type} on {self.date}>'
    
    def get_transaction_type_display(self):
        """Отображаемое название типа транзакции"""
        types = {
            'income': 'Доход',
            'expense': 'Расход',
            'transfer': 'Перевод'
        }
        return types.get(self.transaction_type, self.transaction_type)
    
    def get_account_display(self):
        """Отображение счетов для транзакции"""
        if self.transaction_type == 'income':
            return f"→ {self.to_account.owner.name}: {self.to_account.name}" if self.to_account else ""
        elif self.transaction_type == 'expense':
            return f"{self.from_account.owner.name}: {self.from_account.name} →" if self.from_account else ""
        elif self.transaction_type == 'transfer':
            from_acc = f"{self.from_account.owner.name}: {self.from_account.name}" if self.from_account else ""
            to_acc = f"{self.to_account.owner.name}: {self.to_account.name}" if self.to_account else ""
            return f"{from_acc} → {to_acc}"
        return ""
    
    @staticmethod
    def get_monthly_stats(month=None, year=None):
        """Получить статистику за месяц"""
        if not month:
            month = date.today().month
        if not year:
            year = date.today().year
            
        query = Transaction.query.filter(
            func.extract('month', Transaction.date) == month,
            func.extract('year', Transaction.date) == year
        )
        
        stats = {
            'total_income': 0,
            'total_expense': 0,
            'total_transfers': 0,
            'transactions_count': query.count()
        }
        
        for transaction in query.all():
            if transaction.transaction_type == 'income':
                stats['total_income'] += float(transaction.amount)
            elif transaction.transaction_type == 'expense':
                stats['total_expense'] += float(transaction.amount)
            elif transaction.transaction_type == 'transfer':
                stats['total_transfers'] += float(transaction.amount)
        
        return stats