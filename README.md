# 🏛️ Vesta - Personal Finance Tracker

A modern, self-hosted personal finance management application for families and couples. Track expenses, manage multiple accounts, and gain insights into your financial health with an intuitive web interface.

## ✨ Features

### 💳 Account Management
- **Multiple Account Types**: Debit cards, credit cards, savings, cash, and savings goals
- **Balance Tracking**: Real-time balance updates with transaction history
- **Smart Balance Calculation**: Exclude credit cards from total family balance
- **Savings Goals**: Set targets with progress tracking

### 💰 Transaction Tracking
- **Income & Expenses**: Comprehensive transaction logging
- **Account Transfers**: Move money between accounts seamlessly
- **Hierarchical Categories**: Organized expense categories with subcategories
- **Flexible Filtering**: Filter by date, user, category, and transaction type

### 👥 Multi-User Support
- **Family-Friendly**: Support for couples, families, or any group
- **User-Specific Accounts**: Each user manages their own accounts
- **Shared Overview**: Combined family financial dashboard

### 📊 Financial Insights
- **Monthly Statistics**: Income vs expenses breakdown
- **Recent Activity**: Latest transactions at a glance
- **Category Analysis**: Spending patterns by category
- **Balance Trends**: Track your financial progress over time

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- Git

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/your-username/vesta.git
cd vesta
```

2. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your preferred settings
```

3. **Start the application**
```bash
docker-compose up -d
```

4. **Access Vesta**
Open your browser and navigate to `http://localhost:5000`

The application will automatically create the database and sample users on first run.

## 🛠️ Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
# Database Configuration
DATABASE_URL=sqlite:///instance/vesta.db

# Flask Configuration
SECRET_KEY=your-secret-key-here
FLASK_ENV=production
FLASK_DEBUG=False

# Application Settings
DEFAULT_CURRENCY=USD
```

### Default Users

On first startup, Vesta creates two sample users:
- **User 1** and **User 2**

You can modify these in the admin interface or database directly.

## 📱 Usage

### Adding Accounts
1. Navigate to "Accounts" section
2. Click "Add Account"
3. Select owner, account type, and initial balance
4. For savings goals, set your target amount

### Recording Transactions
1. Use "Add Transaction" button
2. Choose transaction type (Income/Expense/Transfer)
3. Select appropriate category and accounts
4. Add description and amount

### Managing Categories
The system includes pre-configured categories:
- **Income**: Salary, Freelance, Investments, Gifts
- **Expenses**: Food, Transport, Housing, Health, Entertainment, etc.
- **Transfers**: Regular transfers, Credit payments, Savings deposits

## 🏗️ Development

### Local Development

1. **Set up virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Run development server**
```bash
python run.py
```

### Project Structure
```
vesta/
├── app/
│   ├── models.py       # Database models
│   ├── routes.py       # Application routes
│   ├── __init__.py     # Flask app factory
│   └── templates/      # HTML templates
├── instance/           # Database storage
├── requirements.txt    # Python dependencies
├── docker-compose.yml  # Docker configuration
├── Dockerfile         # Container definition
└── run.py             # Application entry point
```

## 🔒 Security

- All sensitive configuration moved to environment variables
- SQLite database stored in persistent Docker volume
- No hardcoded secrets in source code
- Input validation and CSRF protection

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with Flask, SQLAlchemy, and Bootstrap
- Icons by Bootstrap Icons
- Containerized with Docker

---

**Vesta** - Taking control of your family finances, one transaction at a time! 🏛️✨