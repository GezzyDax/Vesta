from datetime import datetime, date
from app import db
from sqlalchemy import func, desc

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
    subcategory = db.Column(db.String(100))  # Подкатегория (например, "Пятерочка", "Аптека 36.6")
    transaction_type = db.Column(db.String(20), nullable=False)  # income, expense, transfer
    contact_phone = db.Column(db.String(20))  # Номер телефона для СБП переводов
    reference = db.Column(db.String(100))  # Ссылка на банковскую операцию
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
    
    def get_contact(self):
        """Получить связанный контакт по номеру телефона"""
        if self.contact_phone and self.transaction_type in ['transfer', 'income']:
            return Contact.get_by_phone(self.contact_phone)
        return None
    
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


class Contact(db.Model):
    """Модель контакта для телефонной книги"""
    __tablename__ = 'contacts'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False, unique=True)
    description = db.Column(db.Text)  # Дополнительная информация
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Contact {self.name} ({self.phone})>'
    
    @staticmethod
    def get_by_phone(phone):
        """Получить контакт по номеру телефона"""
        # Normalize phone number (remove +7, 8, spaces, etc.)
        normalized = Contact.normalize_phone(phone)
        if normalized:
            return Contact.query.filter(
                db.or_(
                    Contact.phone == phone,
                    Contact.phone == normalized,
                    Contact.phone == f"+7{normalized[-10:]}",
                    Contact.phone == f"8{normalized[-10:]}"
                )
            ).first()
        return None
    
    @staticmethod
    def normalize_phone(phone):
        """Нормализация номера телефона"""
        if not phone:
            return None
        
        # Remove all non-digits
        digits = ''.join(filter(str.isdigit, phone))
        
        if len(digits) == 11 and digits.startswith('8'):
            # 8XXXXXXXXXX -> 7XXXXXXXXXX
            digits = '7' + digits[1:]
        elif len(digits) == 10:
            # XXXXXXXXXX -> 7XXXXXXXXXX
            digits = '7' + digits
        
        return digits if len(digits) == 11 else None
    
    def get_related_transactions(self):
        """Получить связанные СБП переводы"""
        return Transaction.query.filter_by(contact_phone=self.phone).order_by(desc(Transaction.date)).all()


class UserProfile(db.Model):
    """Модель профиля пользователя"""
    __tablename__ = 'user_profiles'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, default='User')
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<UserProfile {self.name}>'
    


class DataVersion(db.Model):
    """Модель для системы версионирования данных"""
    __tablename__ = 'data_versions'
    
    id = db.Column(db.Integer, primary_key=True)
    version_name = db.Column(db.String(200), nullable=False)  # "v1a2b3c4: Add Alpha Bank import"
    description = db.Column(db.Text)  # Описание изменений
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(100), default='System')
    is_current = db.Column(db.Boolean, default=False)  # Текущая версия
    
    # Git-related fields
    git_commit_hash = db.Column(db.String(40))  # Full commit hash
    git_short_hash = db.Column(db.String(10))   # Short commit hash
    git_branch = db.Column(db.String(100))      # Branch name
    git_tag = db.Column(db.String(100))         # Git tag if exists
    git_author = db.Column(db.String(100))      # Commit author
    git_commit_date = db.Column(db.DateTime)    # Commit date
    git_commit_message = db.Column(db.Text)     # Original commit message
    
    # Version type
    version_type = db.Column(db.String(20), default='manual')  # 'manual', 'import', 'git_auto'
    
    # Связи
    transaction_snapshots = db.relationship('TransactionSnapshot', backref='version', lazy='dynamic', cascade='all, delete-orphan')
    account_snapshots = db.relationship('AccountSnapshot', backref='version', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<DataVersion {self.version_name} ({self.created_at})>'
    
    def get_changes_summary(self):
        """Получить краткое описание изменений в версии"""
        transactions_count = self.transaction_snapshots.count()
        accounts_affected = len(set(snap.account_id for snap in self.account_snapshots.all() if snap.account_id))
        
        return {
            'transactions_count': transactions_count,
            'accounts_affected': accounts_affected,
            'created_at': self.created_at,
            'description': self.description
        }


class TransactionSnapshot(db.Model):
    """Снимок транзакции для версионирования"""
    __tablename__ = 'transaction_snapshots'
    
    id = db.Column(db.Integer, primary_key=True)
    version_id = db.Column(db.Integer, db.ForeignKey('data_versions.id'), nullable=False)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id'), nullable=True)  # None для удаленных
    operation_type = db.Column(db.String(20), nullable=False)  # 'created', 'updated', 'deleted'
    
    # Данные транзакции на момент снимка
    date = db.Column(db.Date, nullable=False)
    amount = db.Column(db.Numeric(15, 2), nullable=False)
    description = db.Column(db.Text)
    transaction_type = db.Column(db.String(20), nullable=False)
    category_id = db.Column(db.Integer, nullable=False)
    from_account_id = db.Column(db.Integer, nullable=True)
    to_account_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False)
    
    # Связи
    transaction = db.relationship('Transaction', backref='snapshots')
    
    def __repr__(self):
        return f'<TransactionSnapshot {self.amount} {self.operation_type}>'


class AccountSnapshot(db.Model):
    """Снимок баланса счета для версионирования"""
    __tablename__ = 'account_snapshots'
    
    id = db.Column(db.Integer, primary_key=True)
    version_id = db.Column(db.Integer, db.ForeignKey('data_versions.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    
    # Данные баланса на момент снимка
    balance_before = db.Column(db.Numeric(15, 2), nullable=False)
    balance_after = db.Column(db.Numeric(15, 2), nullable=False)
    balance_change = db.Column(db.Numeric(15, 2), nullable=False)
    
    # Связи
    account = db.relationship('Account', backref='balance_snapshots')
    
    def __repr__(self):
        return f'<AccountSnapshot {self.account_id}: {self.balance_before} -> {self.balance_after}>'


class ImportPreview(db.Model):
    """Модель для предпросмотра импорта"""
    __tablename__ = 'import_previews'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), nullable=False)  # Уникальный ID сессии импорта
    filename = db.Column(db.String(200), nullable=False)
    bank_type = db.Column(db.String(50), nullable=False)
    default_account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    total_transactions = db.Column(db.Integer, default=0)
    duplicates_found = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)  # Время истечения превью
    
    # Связи
    default_account = db.relationship('Account')
    preview_transactions = db.relationship('ImportPreviewTransaction', backref='preview', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<ImportPreview {self.filename} ({self.total_transactions} transactions)>'


class ImportPreviewTransaction(db.Model):
    """Транзакция в предпросмотре импорта"""
    __tablename__ = 'import_preview_transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    preview_id = db.Column(db.Integer, db.ForeignKey('import_previews.id'), nullable=False)
    
    # Данные транзакции
    date = db.Column(db.Date, nullable=False)
    amount = db.Column(db.Numeric(15, 2), nullable=False)
    description = db.Column(db.Text)
    subcategory = db.Column(db.String(100))  # Подкатегория
    transaction_type = db.Column(db.String(20), nullable=False)
    category_name = db.Column(db.String(100), nullable=False)
    contact_phone = db.Column(db.String(20))  # Номер телефона для СБП
    reference = db.Column(db.String(100))  # Ссылка на операцию
    is_duplicate = db.Column(db.Boolean, default=False)
    duplicate_reason = db.Column(db.String(200))  # Причина дубликата
    status = db.Column(db.String(20), default='pending')  # 'pending', 'selected', 'excluded'
    
    def __repr__(self):
        return f'<ImportPreviewTransaction {self.amount} {self.category_name}>'


class MerchantRule(db.Model):
    """Правила категоризации мерчантов"""
    __tablename__ = 'merchant_rules'
    
    id = db.Column(db.Integer, primary_key=True)
    pattern = db.Column(db.String(200), nullable=False)  # Шаблон для поиска (например, "GORZDRAV_5620")
    merchant_name = db.Column(db.String(200), nullable=False)  # Название мерчанта (например, "RU/Voronezh/GORZDRAV_5620")
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    subcategory = db.Column(db.String(100))  # Подкатегория (например, "Горздрав")
    priority = db.Column(db.Integer, default=1)  # Приоритет правила (1 = высший)
    is_active = db.Column(db.Boolean, default=True)
    rule_type = db.Column(db.String(20), default='contains')  # 'contains', 'starts_with', 'ends_with', 'regex'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связи
    category = db.relationship('Category', backref='merchant_rules')
    
    def __repr__(self):
        return f'<MerchantRule {self.pattern} -> {self.category.name}>'
    
    def matches(self, description):
        """Проверить, подходит ли описание под это правило"""
        if not self.is_active:
            return False
            
        description_lower = description.lower()
        pattern_lower = self.pattern.lower()
        
        if self.rule_type == 'contains':
            return pattern_lower in description_lower
        elif self.rule_type == 'starts_with':
            return description_lower.startswith(pattern_lower)
        elif self.rule_type == 'ends_with':
            return description_lower.endswith(pattern_lower)
        elif self.rule_type == 'regex':
            import re
            try:
                return bool(re.search(self.pattern, description, re.IGNORECASE))
            except re.error:
                return False
        
        return False
    
    @staticmethod
    def find_matching_rule(description):
        """Найти наиболее подходящее правило для описания"""
        rules = MerchantRule.query.filter_by(is_active=True).order_by(MerchantRule.priority.desc()).all()
        
        for rule in rules:
            if rule.matches(description):
                return rule
        
        return None