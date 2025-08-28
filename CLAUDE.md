# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Language Preference
**IMPORTANT**: Always communicate in Russian language when working in this repository. This is a Russian-language project and all communication should be in Russian.

## Architecture Overview

Vesta is a personal finance management application built with Flask and SQLAlchemy. The application features:

- **Multi-user support** for families/couples
- **Multi-language support** (Russian/English) with Flask-Babel
- **Bank import functionality** for various Russian banks
- **Hierarchical categories** for expense tracking
- **Account management** with balance calculations
- **Transaction versioning** and data snapshots

### Core Components

- **app/models.py**: Core data models (User, Account, Transaction, Category, etc.)
- **app/routes.py**: All Flask routes and business logic
- **app/bank_import.py**: Bank statement parsing (Alpha Bank, Tinkoff, etc.)
- **app/i18n.py**: Custom internationalization system
- **app/translation.py**: Translation utilities and locale management

### Database Architecture

The application uses SQLAlchemy with these key relationships:
- Users have multiple Accounts
- Transactions link to from_account/to_account (for transfers)
- Categories have hierarchical parent/child relationships
- DataVersions track changes with AccountSnapshot/TransactionSnapshot

## Development Commands

### Local Development
```bash
# Set up virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Run development server
python run.py
```

### Docker Development
```bash
# Build and start services
./build.sh

# Or manually:
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Translation Management
```bash
# Extract translatable strings
pybabel extract -F babel.cfg -o messages.pot .

# Update existing translations
pybabel update -i messages.pot -d translations

# Compile translations (custom script)
python compile_translations.py
```

### Testing
```bash
# Test site availability
python test_site.py

# Test bank parsers
python test_parser.py

# Monitor site continuously
python test_site.py --monitor
```

## Key Features

### Bank Import System
Located in `app/bank_import.py`. Supports multiple Russian banks with automatic:
- Transaction categorization using MCC codes
- Contact detection from phone numbers
- Duplicate transaction prevention
- SBP (Fast Payment System) transfer linking

### Internationalization
Custom i18n system in `app/i18n.py` and `app/translation.py`:
- Dynamic language switching via session
- Translation files in `translations/` directory
- Template integration with `_()` function

### Transaction Versioning
DataVersion system tracks changes:
- AccountSnapshot and TransactionSnapshot for historical data
- Version-based rollback capability
- Import preview system for bank statements

### Contact Management
Automatic contact creation from:
- Transaction descriptions (phone number extraction)
- User phone numbers for SBP transfers
- Merchant rule matching

## Database Models Key Methods

- **User.get_total_balance()**: Calculates balance excluding credit cards
- **Transaction.update_account_balances()**: Updates related account balances
- **Category.get_full_path()**: Returns hierarchical category path
- **Contact.normalize_phone()**: Standardizes phone number format

## File Structure Notes

- `instance/`: Database and uploaded files storage
- `translations/`: i18n files (messages.po/messages.mo)
- `app/templates/`: Jinja2 templates with Bootstrap styling
- `app/static/`: CSS, JavaScript assets
- `migrations/`: Database migration files

## Important Configuration

Environment variables (see config.py):
- `SECRET_KEY`: Flask secret key
- `DATABASE_URL`: Database connection string  
- Default locale: Russian (ru)
- Session lifetime: 30 days