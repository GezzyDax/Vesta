#!/usr/bin/env python3
"""
Миграционный скрипт для создания таблицы правил мерчантов
"""

import os
import sys
from app import create_app, db
from app.models import MerchantRule, Category

def create_merchant_rules_table():
    """Создать таблицу правил мерчантов"""
    print("Creating merchant_rules table...")
    
    # Создаем таблицу
    db.create_all()
    
    print("✅ merchant_rules table created successfully")

def add_sample_rules():
    """Добавить примеры правил"""
    print("Adding sample merchant rules...")
    
    # Получаем категории
    health_category = Category.query.filter_by(name='Здоровье').first()
    food_category = Category.query.filter_by(name='Продукты').first()
    transport_category = Category.query.filter_by(name='Транспорт').first()
    
    sample_rules = []
    
    if health_category:
        sample_rules.append(MerchantRule(
            pattern='GORZDRAV',
            merchant_name='RU/Voronezh/GORZDRAV_5620',
            category_id=health_category.id,
            subcategory='Горздрав',
            priority=1,
            rule_type='contains'
        ))
        
        sample_rules.append(MerchantRule(
            pattern='APTEKA',
            merchant_name='RU/Moscow/APTEKA_366',
            category_id=health_category.id,
            subcategory='Аптека 36.6',
            priority=2,
            rule_type='contains'
        ))
    
    if food_category:
        sample_rules.append(MerchantRule(
            pattern='PYATEROCHKA',
            merchant_name='RU/Moscow/PYATEROCHKA_1234',
            category_id=food_category.id,
            subcategory='Пятёрочка',
            priority=1,
            rule_type='contains'
        ))
        
        sample_rules.append(MerchantRule(
            pattern='MAGNIT',
            merchant_name='RU/Krasnodar/MAGNIT_5678',
            category_id=food_category.id,
            subcategory='Магнит',
            priority=1,
            rule_type='contains'
        ))
    
    if transport_category:
        sample_rules.append(MerchantRule(
            pattern='LUKOIL',
            merchant_name='RU/Moscow/LUKOIL_AZS_123',
            category_id=transport_category.id,
            subcategory='Лукойл',
            priority=1,
            rule_type='contains'
        ))
    
    # Добавляем правила в базу
    for rule in sample_rules:
        existing = MerchantRule.query.filter_by(pattern=rule.pattern).first()
        if not existing:
            db.session.add(rule)
    
    try:
        db.session.commit()
        print(f"✅ Added {len(sample_rules)} sample merchant rules")
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error adding sample rules: {e}")

def main():
    """Основная функция миграции"""
    app = create_app()
    
    with app.app_context():
        try:
            print("🚀 Starting merchant rules migration...")
            
            # Создаем таблицы
            create_merchant_rules_table()
            
            # Добавляем примеры правил
            add_sample_rules()
            
            print("✅ Merchant rules migration completed successfully!")
            
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            sys.exit(1)

if __name__ == '__main__':
    main()