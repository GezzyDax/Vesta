#!/usr/bin/env python3
"""Database migration script"""

from app import create_app, db

def migrate_database():
    """Recreate database with new schema"""
    app = create_app()
    
    with app.app_context():
        print("Dropping all tables...")
        db.drop_all()
        print("Creating all tables...")
        db.create_all()
        print("Database migration completed!")

if __name__ == '__main__':
    migrate_database()