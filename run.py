from app import create_app, db
from app.models import User, Account, Transaction, Category

app = create_app()

@app.shell_context_processor
def make_shell_context():
    return {
        'db': db, 
        'User': User, 
        'Account': Account, 
        'Transaction': Transaction,
        'Category': Category
    }

def create_tables():
    """Create tables and initial data on first startup"""
    db.create_all()
    
    # Create default users if none exist
    if User.query.count() == 0:
        user1 = User(name='User 1', is_active=True)
        user2 = User(name='User 2', is_active=True)
        db.session.add(user1)
        db.session.add(user2)
        db.session.commit()
        
        # Create income categories
        income_categories = [
            Category(name='Salary', category_type='income'),
            Category(name='Freelance', category_type='income'),
            Category(name='Investments', category_type='income'),
            Category(name='Gifts', category_type='income'),
        ]
        
        for category in income_categories:
            db.session.add(category)
        
        db.session.flush()  # Save categories to get their IDs
        
        # Create main expense categories and their subcategories
        expense_structure = {
            'Food': ['Groceries', 'Restaurants & Cafes', 'Food Delivery', 'Street Food'],
            'Transport': ['Public Transport', 'Taxi', 'Car - Fuel', 
                         'Car - Repairs/Service', 'Car - Insurance/Taxes'],
            'Housing': ['Utilities', 'Rent', 'Home Repairs/Improvements', 
                       'Furniture/Appliances', 'Internet/Phone/TV'],
            'Health': ['Pharmacy', 'Medical Services'],
            'Clothing': ['Casual Clothing', 'Seasonal Clothing', 'Shoes', 'Accessories'],
            'Entertainment': ['Movies', 'Subscriptions', 'Games/Books/Hobbies', 'Travel/Vacation'],
            'Pets': ['Pet Food', 'Veterinary', 'Pet Toys/Accessories'],
            'Financial': ['Loans/Mortgage', 'Taxes'],
            'Gifts & Events': ['Gifts for Family', 'Flowers/Souvenirs', 'Celebrations'],
            'Other': ['Cash Expenses (Untracked)', 'Charity', 'Fines/Fees']
        }
        
        for parent_name, subcategories in expense_structure.items():
            # Create parent category
            parent_category = Category(name=parent_name, category_type='expense')
            db.session.add(parent_category)
            db.session.flush()
            
            # Create subcategories
            for sub_name in subcategories:
                sub_category = Category(
                    name=sub_name, 
                    category_type='expense',
                    parent_id=parent_category.id
                )
                db.session.add(sub_category)
        
        # Create transfer categories
        transfer_categories = [
            Category(name='Regular Transfer', category_type='transfer'),
            Category(name='Credit Payment', category_type='transfer'),
            Category(name='Savings Deposit', category_type='transfer'),
        ]
        
        for category in transfer_categories:
            db.session.add(category)
        
        db.session.commit()

if __name__ == '__main__':
    try:
        with app.app_context():
            create_tables()
        print("Database initialized successfully!")
        app.run(host='0.0.0.0', port=5000, debug=True)
    except Exception as e:
        print(f"Error starting application: {e}")
        import traceback
        traceback.print_exc()