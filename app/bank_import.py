"""
Bank Statement Import Module for Vesta
Supports Alpha Bank (XLSX), Sberbank (PDF), and Raiffeisen (CSV)
"""

import pandas as pd
import PyPDF2
import csv
import re
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import chardet


@dataclass
class Transaction:
    """Standard transaction data structure"""
    date: date
    amount: float
    description: str
    transaction_type: str  # 'income' or 'expense'
    category: str = "Other"
    reference: str = ""
    subcategory: Optional[str] = None
    contact_phone: Optional[str] = None
    

class BankStatementParser:
    """Base class for bank statement parsers"""
    
    def __init__(self):
        self.transactions = []
        
    def parse_file(self, file_path: str) -> List[Transaction]:
        """Parse bank statement file and return transactions"""
        raise NotImplementedError
        
    def detect_encoding(self, file_path: str) -> str:
        """Detect file encoding"""
        with open(file_path, 'rb') as f:
            raw_data = f.read()
            result = chardet.detect(raw_data)
            return result['encoding'] or 'utf-8'


class AlphaBankParser(BankStatementParser):
    """Parser for Alpha Bank XLSX statements"""
    
    def parse_file(self, file_path: str) -> List[Transaction]:
        """Parse Alpha Bank XLSX file with enhanced categorization"""
        try:
            df = pd.read_excel(file_path, header=None)
            
            # Based on our analysis, transactions start at row 19
            transactions = []
            
            # Parse each transaction row
            for i in range(19, len(df)):
                row = df.iloc[i]
                
                # Debug: print entire row data for troubleshooting
                print(f"Row {i}: {[str(row[j]) if j < len(row) and pd.notna(row[j]) else 'N/A' for j in range(min(len(row), 15))]}")
                
                # Check if this is a valid transaction row (has date in Col0)
                if pd.isna(row[0]):
                    print(f"Row {i}: Skipped - no date in Col0")
                    continue
                
                try:
                    # Parse date from Col0
                    date_val = row[0]
                    if isinstance(date_val, str):
                        trans_date = datetime.strptime(date_val, '%d.%m.%Y').date()
                    else:
                        trans_date = date_val.date()
                    
                    # Get code from Col3
                    code = str(row[3]) if pd.notna(row[3]) else ""
                    
                    # Get category from Col4
                    category = str(row[4]) if pd.notna(row[4]) else ""
                    
                    # Get description from Col11 (contains MCC, merchant info)
                    description = str(row[11]) if pd.notna(row[11]) else ""
                    
                    # Get amount from various possible columns (Col5, Col12, Col13, etc)
                    amount = 0.0
                    amount_col = None
                    
                    # Try different columns for amount
                    for col_idx in [5, 12, 13, 14]:
                        if col_idx < len(row) and pd.notna(row[col_idx]):
                            amount_str = str(row[col_idx])
                            # Handle amount formatting - remove non-breaking spaces (\xa0) and regular spaces
                            amount_str = amount_str.replace('\xa0', '').replace(' ', '').replace(',', '.')
                            # Look for amount patterns
                            amount_match = re.search(r'([+-]?)([\d.]+)', amount_str)
                            if amount_match:
                                sign = -1 if amount_match.group(1) == '-' else 1
                                clean_amount = amount_match.group(2)
                                try:
                                    test_amount = float(clean_amount) * sign
                                    if abs(test_amount) > 0:  # Valid non-zero amount found
                                        amount = test_amount
                                        amount_col = col_idx
                                        print(f"Row {i}: Found amount {amount} in Col{col_idx}")
                                        break
                                except:
                                    continue
                    
                    if amount == 0 and amount_col is None:
                        print(f"Row {i}: No valid amount found in any column")
                    
                    # Skip status check - import all transactions regardless of status
                    
                    if amount == 0:
                        print(f"Row {i}: Skipped - zero amount")
                        continue
                    
                    print(f"Row {i}: Processing - amount={amount}")
                    
                    # Create full description combining category and detailed info
                    full_description = f"{category} - {description}" if description else category
                    
                    # Enhanced categorization using MCC codes and merchant patterns
                    enhanced_category = self._map_alpha_category(full_description, category)
                    
                    # Better transaction type detection
                    trans_type = self._determine_transaction_type(full_description, category, amount)
                    
                    # Extract subcategory and contact info
                    subcategory = self._extract_subcategory(description, enhanced_category)
                    contact_phone = self._extract_phone_number(description) if 'сбп' in full_description.lower() else None
                    
                    transaction = Transaction(
                        date=trans_date,
                        amount=abs(amount),
                        description=full_description,
                        transaction_type=trans_type,
                        category=enhanced_category,
                        subcategory=subcategory,
                        contact_phone=contact_phone,
                        reference=code
                    )
                    transactions.append(transaction)
                    
                except Exception as e:
                    # Skip problematic rows
                    print(f"Row {i}: Exception - {str(e)}")
                    continue
            
            return transactions
            
        except Exception as e:
            raise ValueError(f"Error parsing Alpha Bank file: {str(e)}")
    
    def _extract_amount_from_row(self, df: pd.DataFrame, row_idx: int) -> float:
        """Extract amount from Alpha Bank row (complex logic needed)"""
        row = df.iloc[row_idx]
        
        # Look for amount patterns in the entire row
        for val in row:
            if pd.notna(val):
                val_str = str(val)
                # Look for amount patterns like "1 234,56" or "-1234.56"
                amount_match = re.search(r'([+-]?)(\d{1,3}(?:\s\d{3})*(?:[,.]\d{2})?)', val_str.replace('\xa0', ' '))
                if amount_match:
                    amount_str = amount_match.group(2).replace(' ', '').replace(',', '.')
                    sign = -1 if amount_match.group(1) == '-' else 1
                    try:
                        return float(amount_str) * sign
                    except:
                        continue
        return 0.0
    
    def _determine_transaction_type(self, description: str, category: str, amount: float) -> str:
        """Determine transaction type based on description, category, and amount"""
        desc_lower = description.lower()
        cat_lower = category.lower() if category else ""
        
        # Income indicators
        income_keywords = [
            'заработная плата', 'зарплата', 'оклад', 'salary', 'зп', 'выплата заработной платы',
            'премия', 'premium', 'бонус', 'отпускных', 'внесение средств', 'от +7'
        ]
        
        # Transfer indicators (neutral - neither income nor expense)
        transfer_keywords = [
            'перевод по сбп', 'через систему быстрых платежей', 'внутрибанковский перевод',
            'перевод между счетами', 'со счёта', 'на счёт'
        ]
        
        # Check for income patterns
        if any(keyword in desc_lower for keyword in income_keywords):
            return 'income'
        
        # Check for transfer patterns - these should be classified by amount direction
        if any(keyword in desc_lower for keyword in transfer_keywords):
            # For transfers, positive amount = incoming transfer (income), negative = outgoing (expense)
            return 'income' if amount > 0 else 'expense'
        
        # Special cases for specific categories
        if 'финансовые операции' in cat_lower:
            # SBP QR payments are usually expenses
            if 'qr по сбп' in desc_lower or 'qr коду' in desc_lower:
                return 'expense'
            # Other financial operations - classify by amount
            return 'income' if amount > 0 else 'expense'
        
        # Default classification by amount sign
        return 'income' if amount > 0 else 'expense'
    
    def _extract_subcategory(self, description: str, main_category: str) -> str:
        """Extract subcategory from merchant/location information"""
        if not description:
            return None
            
        desc_lower = description.lower()
        
        # Common merchant patterns
        merchant_patterns = {
            'пятерочка': 'Пятёрочка',
            'pyaterochka': 'Пятёрочка',
            'magnit': 'Магнит',
            'магнит': 'Магнит',
            'okey': 'О`КЕЙ',
            'окей': 'О`КЕЙ',
            'gorzdrav': 'Горздрав',
            'горздрав': 'Горздрав',
            'apteka': 'Аптека',
            'аптека': 'Аптека',
            'tele2': 'Теле2',
            'теле2': 'Теле2',
            'megafon': 'МегаФон',
            'мегафон': 'МегаФон',
            'beeline': 'Билайн',
            'билайн': 'Билайн',
            'mts': 'МТС',
            'мтс': 'МТС',
            'sberbank': 'Сбербанк',
            'сбербанк': 'Сбербанк',
            'alfabank': 'Альфа-Банк',
            'альфа': 'Альфа-Банк',
            'mcdonalds': "McDonald's",
            'kfc': 'KFC',
            'burger king': 'Burger King',
            'subway': 'Subway',
            'rosinter': 'Росинтер',
            'shokoladnitsa': 'Шоколадница',
            'coffeehouse': 'Кофе Хаус'
        }
        
        # Search for merchant patterns
        for pattern, merchant in merchant_patterns.items():
            if pattern in desc_lower:
                return merchant
        
        # Extract from location patterns like "RU/Voronezh/MERCHANT_NAME"
        location_match = re.search(r'RU/[^/]+/([^,\s]+)', description)
        if location_match:
            merchant_code = location_match.group(1)
            # Clean merchant code
            merchant_clean = merchant_code.replace('_', ' ').strip()
            if len(merchant_clean) > 3:  # Only return if meaningful
                return merchant_clean.title()
        
        # Extract from company names in transfers
        company_patterns = [
            r'в пользу\s+([^,\s]+)', 
            r'получатель\s+([^,\s]+)',
            r'платеж.*?в\s+([^,\s]+)'
        ]
        
        for pattern in company_patterns:
            match = re.search(pattern, desc_lower)
            if match:
                company = match.group(1).strip()
                if len(company) > 3:
                    return company.title()
        
        return None
    
    def _extract_phone_number(self, description: str) -> str:
        """Extract phone number from SBP transfer description"""
        if not description:
            return None
        
        # Patterns for phone numbers in descriptions
        phone_patterns = [
            r'\+7(\d{10})',  # +7XXXXXXXXXX
            r'\+7\d{3}\+{3}(\d{4})',  # +7XXX+++XXXX (masked)
            r'на\s+\+7(\d{10})',  # на +7XXXXXXXXXX
            r'от\s+\+7(\d{10})',  # от +7XXXXXXXXXX
            r'на\s+\+7\d{3}\+{3}(\d{4})',  # на +7XXX+++XXXX
            r'от\s+\+7\d{3}\+{3}(\d{4})'   # от +7XXX+++XXXX
        ]
        
        for pattern in phone_patterns:
            match = re.search(pattern, description)
            if match:
                phone_digits = match.group(1)
                if len(phone_digits) >= 4:  # At least partial number
                    if len(phone_digits) == 10:
                        return f"+7{phone_digits}"
                    else:
                        # For masked numbers, return what we have
                        return f"+7***{phone_digits}"
        
        return None
    
    def _map_alpha_category(self, description: str, category: str = None) -> str:
        """Map Alpha Bank transaction to category using MCC codes and merchant names"""
        desc_lower = description.lower()
        
        # Extract MCC code from description
        mcc_match = re.search(r'mcc:\s*(\d{4})', desc_lower)
        if mcc_match:
            mcc_code = mcc_match.group(1)
            category_from_mcc = self._categorize_by_mcc(mcc_code)
            if category_from_mcc != 'Other':
                return category_from_mcc
        
        # Classify by merchant name patterns
        category_from_merchant = self._categorize_by_merchant_name(desc_lower)
        if category_from_merchant != 'Other':
            return category_from_merchant
        
        # Check for SBP transfers
        if 'сбп' in desc_lower or 'sbp' in desc_lower:
            return 'Financial'
        
        # Fallback to original Alpha category mapping
        if category:
            mapping = {
                'продукты': 'Food',
                'финансовые операции': 'Financial',
                'штрафы и налоги': 'Financial',
                'прочие операции': 'Other',
                'транспорт': 'Transport',
                'развлечения': 'Entertainment',
                'здоровье': 'Health',
                'одежда': 'Clothing'
            }
            
            for key, value in mapping.items():
                if key in category.lower():
                    return value
        
        return 'Other'
    
    def _categorize_by_mcc(self, mcc_code: str) -> str:
        """Categorize transaction by MCC code using comprehensive Alpha Bank mapping"""
        mcc_mapping = {
            # Авто (4784, 5013, 5271, 5511, 5521, 5531-5533, 5551, 5561, 5571, 5592, 5598, 5599, 7511, 7523, 7531, 7534, 7535, 7538, 7542, 7549, 3991)
            '4784': 'Auto', '5013': 'Auto', '5271': 'Auto', '5511': 'Auto', '5521': 'Auto',
            '5531': 'Auto', '5532': 'Auto', '5533': 'Auto', '5551': 'Auto', '5561': 'Auto',
            '5571': 'Auto', '5592': 'Auto', '5598': 'Auto', '5599': 'Auto', '7511': 'Auto',
            '7523': 'Auto', '7531': 'Auto', '7534': 'Auto', '7535': 'Auto', '7538': 'Auto',
            '7542': 'Auto', '7549': 'Auto',
            
            # АЗС (5172, 5541, 5542, 5552, 5983, 9752, 3990)
            '5172': 'Fuel', '5541': 'Fuel', '5542': 'Fuel', '5552': 'Fuel', 
            '5983': 'Fuel', '9752': 'Fuel',
            
            # Аксессуары (5948, 7251, 7631)
            '5948': 'Accessories', '7251': 'Accessories', '7631': 'Accessories',
            
            # Активный отдых (7032, 7932, 7933, 7996, 7998, 7999, 7941, 7992, 7997)
            '7032': 'Entertainment', '7932': 'Entertainment', '7933': 'Entertainment', 
            '7996': 'Entertainment', '7998': 'Entertainment', '7999': 'Entertainment',
            '7941': 'Entertainment', '7992': 'Entertainment', '7997': 'Entertainment',
            
            # Алкоголь (5921)
            '5921': 'Alcohol',
            
            # Аптеки (5122, 5912)
            '5122': 'Health', '5912': 'Health',
            
            # Аренда авто (3351-3398, 3400-3410, 3412-3423, 3425-3439, 3441, 7512, 7513, 7519, 3990, 3991)
            **{str(i): 'Transport' for i in range(3351, 3399)},
            **{str(i): 'Transport' for i in range(3400, 3411)},
            **{str(i): 'Transport' for i in range(3412, 3424)},
            **{str(i): 'Transport' for i in range(3425, 3440)},
            '3441': 'Transport', '7512': 'Transport', '7513': 'Transport', '7519': 'Transport',
            
            # Детские товары (5641, 5945)
            '5641': 'Children', '5945': 'Children',
            
            # Дом и ремонт
            '0780': 'Home', '1520': 'Home', '1711': 'Home', '1731': 'Home', '1740': 'Home',
            '1750': 'Home', '1761': 'Home', '1771': 'Home', '2842': 'Home', '5021': 'Home',
            '5039': 'Home', '5046': 'Home', '5051': 'Home', '5072': 'Home', '5074': 'Home',
            '5085': 'Home', '5198': 'Home', '5200': 'Home', '5211': 'Home', '5231': 'Home',
            '5251': 'Home', '5261': 'Home', '5712': 'Home', '5713': 'Home', '5714': 'Home',
            '5718': 'Home', '5719': 'Home', '5950': 'Home', '5996': 'Home', '7217': 'Home',
            '7641': 'Home', '7692': 'Home', '7699': 'Home',
            
            # Животные (0742, 5995)
            '0742': 'Pets', '5995': 'Pets',
            
            # Здоровье
            '4119': 'Health', '5047': 'Health', '5122': 'Health', '5912': 'Health',
            '5975': 'Health', '5976': 'Health', '8011': 'Health', '8021': 'Health',
            '8031': 'Health', '8041': 'Health', '8042': 'Health', '8043': 'Health',
            '8044': 'Health', '8049': 'Health', '8050': 'Health', '8062': 'Health',
            '8071': 'Health', '8099': 'Health',
            
            # Кафе и рестораны (5811, 5812, 5813, 3990)
            '5811': 'Restaurants', '5812': 'Restaurants', '5813': 'Restaurants',
            
            # Книги (2741, 5111, 5192, 5942, 5943, 5994)
            '2741': 'Books', '5111': 'Books', '5192': 'Books', '5942': 'Books', 
            '5943': 'Books', '5994': 'Books',
            
            # Красота (5977, 7230, 7297, 7298)
            '5977': 'Beauty', '7230': 'Beauty', '7297': 'Beauty', '7298': 'Beauty',
            
            # Культура и искусство
            '5970': 'Culture', '5971': 'Culture', '5972': 'Culture', '7911': 'Culture',
            '7922': 'Culture', '7991': 'Culture', '7829': 'Culture', '7832': 'Culture',
            '7841': 'Culture', '5733': 'Culture', '5735': 'Culture', '7929': 'Culture',
            
            # Маркетплейсы (5262, 5300, 5399, 5964, 3990, 3991)
            '5262': 'Shopping', '5300': 'Shopping', '5399': 'Shopping', '5964': 'Shopping',
            
            # Медицинские услуги
            '4119': 'Medical', '5047': 'Medical', '8011': 'Medical', '8031': 'Medical',
            '8041': 'Medical', '8042': 'Medical', '8043': 'Medical', '8049': 'Medical',
            '8050': 'Medical', '8062': 'Medical', '8071': 'Medical', '8099': 'Medical',
            '8021': 'Medical',
            
            # Образование (8211, 8220, 8241, 8244, 8249, 8299, 8351, 3990)
            '8211': 'Education', '8220': 'Education', '8241': 'Education', '8244': 'Education',
            '8249': 'Education', '8299': 'Education', '8351': 'Education',
            
            # Одежда и обувь
            '5137': 'Clothing', '5611': 'Clothing', '5621': 'Clothing', '5631': 'Clothing',
            '5651': 'Clothing', '5681': 'Clothing', '5691': 'Clothing', '5699': 'Clothing',
            '5931': 'Clothing', '7296': 'Clothing', '5139': 'Clothing', '5661': 'Clothing',
            
            # Покупка авто (5521, 5551, 5561, 5571, 5592, 5598, 5599)
            '5521': 'Auto', '5551': 'Auto', '5561': 'Auto', '5571': 'Auto',
            '5592': 'Auto', '5598': 'Auto', '5599': 'Auto',
            
            # Продукты
            '5310': 'Food', '5311': 'Food', '5331': 'Food', '5411': 'Food', '5422': 'Food',
            '5441': 'Food', '5451': 'Food', '5462': 'Food', '5499': 'Food', '7278': 'Food',
            '9751': 'Food',
            
            # Развлечения
            '5733': 'Entertainment', '5945': 'Entertainment', '5946': 'Entertainment',
            '5947': 'Entertainment', '5949': 'Entertainment', '5970': 'Entertainment',
            '5971': 'Entertainment', '5972': 'Entertainment', '5998': 'Entertainment',
            '7032': 'Entertainment', '7221': 'Entertainment', '7395': 'Entertainment',
            '7829': 'Entertainment', '7832': 'Entertainment', '7841': 'Entertainment',
            '7911': 'Entertainment', '7922': 'Entertainment', '7929': 'Entertainment',
            '7932': 'Entertainment', '7933': 'Entertainment', '7941': 'Entertainment',
            '7991': 'Entertainment', '7992': 'Entertainment', '7993': 'Entertainment',
            '7994': 'Entertainment', '7996': 'Entertainment', '7997': 'Entertainment',
            '7998': 'Entertainment', '7999': 'Entertainment',
            
            # Связь, интернет и ТВ (4813-4816, 4821, 4899, 7372, 7375)
            '4813': 'Communication', '4814': 'Communication', '4815': 'Communication',
            '4816': 'Communication', '4821': 'Communication', '4899': 'Communication',
            '7372': 'Communication', '7375': 'Communication',
            
            # Спортивные товары (5655, 5940, 5941)
            '5655': 'Sports', '5940': 'Sports', '5941': 'Sports',
            
            # Супермаркеты
            '5262': 'Food', '5300': 'Food', '5310': 'Food', '5311': 'Food', '5331': 'Food',
            '5399': 'Food', '5411': 'Food', '5422': 'Food', '5441': 'Food', '5451': 'Food',
            '5462': 'Food', '5499': 'Food', '5964': 'Food', '7278': 'Food', '9751': 'Food',
            
            # Такси (4121, 3990)
            '4121': 'Transport',
            
            # Техника
            '5044': 'Electronics', '5045': 'Electronics', '5065': 'Electronics',
            '5722': 'Electronics', '5732': 'Electronics', '5978': 'Electronics',
            '5997': 'Electronics', '7379': 'Electronics', '7622': 'Electronics',
            '7623': 'Electronics', '7629': 'Electronics',
            
            # Товары для здоровья (5975, 5976, 8044)
            '5975': 'Health', '5976': 'Health', '8044': 'Health',
            
            # Транспорт (4011-4112, 4131, 4729, 4789, 3990)
            **{str(i): 'Transport' for i in range(4011, 4113)},
            '4131': 'Transport', '4729': 'Transport', '4789': 'Transport',
            
            # Фастфуд (5814, 3990)
            '5814': 'Fastfood',
            
            # Хобби (5946, 5947, 5949, 5998, 7221, 7395, 7993, 7994)
            '5946': 'Hobby', '5947': 'Hobby', '5949': 'Hobby', '5998': 'Hobby',
            '7221': 'Hobby', '7395': 'Hobby', '7993': 'Hobby', '7994': 'Hobby',
            
            # Цветы (5193, 5992)
            '5193': 'Flowers', '5992': 'Flowers',
            
            # Цифровые товары (5734, 5735, 5815-5818)
            '5734': 'Digital', '5735': 'Digital', '5815': 'Digital', '5816': 'Digital',
            '5817': 'Digital', '5818': 'Digital',
            
            # Ювелирные изделия (5094, 5944)
            '5094': 'Jewelry', '5944': 'Jewelry',
            
            # Специальные коды экосистем
            '3990': 'Ecosystem',  # Яндекс экосистема
            '3991': 'Ecosystem',  # Сбер экосистема
        }
        
        return mcc_mapping.get(mcc_code, 'Other')
    
    def _categorize_by_merchant_name(self, description: str) -> str:
        """Categorize transaction by merchant name patterns"""
        merchant_patterns = {
            'Health': [
                'gorzdrav', 'аптека', 'pharmacy', 'медицин', 'больниц', 'клиника',
                'hospital', 'доктор', 'врач', 'лекарств', 'поликлиника'
            ],
            'Food': [
                'magnit', 'магнит', 'perekrestok', 'перекресток', 'пятерочка', 'pyaterochka',
                'ашан', 'auchan', 'metro', 'метро', 'дикси', 'dixi', 'лента', 'lenta',
                'супермаркет', 'продукт', 'market', 'grocery'
            ],
            'Fuel': [
                'lukoil', 'лукойл', 'rosneft', 'роснефть', 'газпром', 'gazprom',
                'shell', 'bp', 'total', 'азс', 'заправк'
            ],
            'Restaurants': [
                'mcdonalds', 'макдональдс', 'kfc', 'burger', 'бургер', 'pizza',
                'пицца', 'кафе', 'cafe', 'ресторан', 'restaurant', 'столов'
            ],
            'Transport': [
                'metro', 'метро', 'такси', 'taxi', 'яндекс', 'yandex', 'uber',
                'автобус', 'bus', 'поезд', 'train', 'самолет', 'plane'
            ],
            'Entertainment': [
                'кино', 'cinema', 'театр', 'theatre', 'музей', 'museum',
                'развлечен', 'entertainment', 'игр', 'game', 'спорт', 'sport'
            ],
            'Clothing': [
                'zara', 'h&m', 'uniqlo', 'adidas', 'nike', 'одежд', 'clothes',
                'обув', 'shoes', 'fashion', 'мода'
            ],
            'Financial': [
                'банк', 'bank', 'сбп', 'sbp', 'перевод', 'transfer', 'пополнение',
                'снятие', 'cash', 'комиссия', 'commission'
            ]
        }
        
        for category, patterns in merchant_patterns.items():
            for pattern in patterns:
                if pattern in description:
                    return category
        
        return 'Other'


class RaiffeisenBankParser(BankStatementParser):
    """Parser for Raiffeisen Bank CSV statements"""
    
    def parse_file(self, file_path: str) -> List[Transaction]:
        """Parse Raiffeisen CSV file"""
        try:
            encoding = self.detect_encoding(file_path)
            
            with open(file_path, 'r', encoding=encoding) as f:
                # Read CSV with semicolon delimiter
                reader = csv.DictReader(f, delimiter=';')
                transactions = []
                
                for row in reader:
                    try:
                        # Parse date
                        date_str = row['Дата операции'].strip()
                        trans_date = datetime.strptime(date_str, '%d.%m.%Y').date()
                        
                        # Get amounts
                        income_amount = self._parse_amount(row.get('Сумма в валюте операции (поступления)', ''))
                        expense_amount = self._parse_amount(row.get('Сумма в валюте операции (расходы)', ''))
                        
                        # Determine transaction type and amount
                        if income_amount > 0:
                            amount = income_amount
                            trans_type = 'income'
                        elif expense_amount > 0:
                            amount = expense_amount
                            trans_type = 'expense'
                        else:
                            continue  # Skip zero transactions
                        
                        # Get description
                        description = row.get('Детали операции (назначение платежа)', '').strip()
                        
                        transaction = Transaction(
                            date=trans_date,
                            amount=amount,
                            description=description,
                            transaction_type=trans_type,
                            category=self._categorize_raiffeisen(description),
                            reference=row.get('Номер документа', '')
                        )
                        transactions.append(transaction)
                        
                    except Exception as e:
                        # Skip problematic rows
                        continue
                
                return transactions
                
        except Exception as e:
            raise ValueError(f"Error parsing Raiffeisen CSV file: {str(e)}")
    
    def _parse_amount(self, amount_str: str) -> float:
        """Parse amount from string"""
        if not amount_str or amount_str.strip() == '':
            return 0.0
        
        # Remove currency and spaces, replace comma with dot
        clean_amount = re.sub(r'[^\d,.-]', '', amount_str).replace(',', '.')
        
        try:
            return float(clean_amount)
        except:
            return 0.0
    
    def _categorize_raiffeisen(self, description: str) -> str:
        """Categorize transaction based on description"""
        desc_lower = description.lower()
        
        if any(word in desc_lower for word in ['магазин', 'продукты', 'супермаркет', 'market']):
            return 'Food'
        elif any(word in desc_lower for word in ['транспорт', 'метро', 'автобус', 'такси']):
            return 'Transport'
        elif any(word in desc_lower for word in ['аптека', 'медицин', 'клиника']):
            return 'Health'
        elif any(word in desc_lower for word in ['кафе', 'ресторан', 'кино', 'развлечен']):
            return 'Entertainment'
        elif any(word in desc_lower for word in ['коммунальн', 'жку', 'электричеств']):
            return 'Housing'
        elif any(word in desc_lower for word in ['зарплата', 'salary', 'доход']):
            return 'Salary'
        else:
            return 'Other'


class SberbankPDFParser(BankStatementParser):
    """Parser for Sberbank PDF statements"""
    
    def parse_file(self, file_path: str) -> List[Transaction]:
        """Parse Sberbank PDF file"""
        try:
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                text = ""
                
                # Extract text from all pages
                for page in reader.pages:
                    text += page.extract_text()
                
                return self._parse_sberbank_text(text)
                
        except Exception as e:
            raise ValueError(f"Error parsing Sberbank PDF file: {str(e)}")
    
    def _parse_sberbank_text(self, text: str) -> List[Transaction]:
        """Parse extracted text from Sberbank PDF"""
        transactions = []
        lines = text.split('\n')
        
        # Look for transaction patterns
        date_pattern = r'(\d{2}\.\d{2}\.\d{4})'
        amount_pattern = r'([+-]?\d+[,.]?\d*)'
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines and headers
            if not line or 'выписка' in line.lower() or 'сбербанк' in line.lower():
                continue
            
            # Look for date at the beginning of line
            date_match = re.search(date_pattern, line)
            if date_match:
                try:
                    trans_date = datetime.strptime(date_match.group(1), '%d.%m.%Y').date()
                    
                    # Extract amount
                    amounts = re.findall(amount_pattern, line)
                    if amounts:
                        # Usually the last amount in the line is the transaction amount
                        amount_str = amounts[-1].replace(',', '.')
                        amount = float(amount_str)
                        
                        # Determine transaction type based on context or amount sign
                        trans_type = 'expense' if amount < 0 else 'income'
                        
                        # Extract description (everything between date and last amount)
                        desc_start = date_match.end()
                        desc_end = line.rfind(amounts[-1])
                        description = line[desc_start:desc_end].strip()
                        
                        if description:  # Only add if we have a description
                            transaction = Transaction(
                                date=trans_date,
                                amount=abs(amount),
                                description=description,
                                transaction_type=trans_type,
                                category=self._categorize_sberbank(description),
                                reference=""
                            )
                            transactions.append(transaction)
                            
                except Exception:
                    continue
        
        return transactions
    
    def _categorize_sberbank(self, description: str) -> str:
        """Categorize Sberbank transaction based on description"""
        desc_lower = description.lower()
        
        if any(word in desc_lower for word in ['покупка', 'магазин', 'супермаркет']):
            return 'Food'
        elif any(word in desc_lower for word in ['метро', 'транспорт', 'такси']):
            return 'Transport'
        elif any(word in desc_lower for word in ['аптека', 'медицина']):
            return 'Health'
        elif any(word in desc_lower for word in ['кафе', 'ресторан']):
            return 'Entertainment'
        elif any(word in desc_lower for word in ['перевод', 'пополнение']):
            return 'Financial'
        else:
            return 'Other'


class BankImportService:
    """Main service for importing bank statements"""
    
    def __init__(self):
        self.parsers = {
            'alpha': AlphaBankParser(),
            'raiffeisen': RaiffeisenBankParser(),
            'sberbank': SberbankPDFParser()
        }
    
    def create_counterpart_transactions(self, transactions: List[Transaction], importing_user_id: int) -> List[Transaction]:
        """Создать встречные транзакции для СБП переводов между пользователями системы"""
        from app.models import User as UserModel, Account as AccountModel
        from app import db
        
        counterpart_transactions = []
        
        for transaction in transactions:
            # Обрабатываем только СБП переводы с номером телефона
            if not transaction.contact_phone or 'сбп' not in transaction.description.lower():
                continue
                
            # Находим пользователя по номеру телефона
            recipient_user = UserModel.find_by_phone(transaction.contact_phone)
            if not recipient_user or recipient_user.id == importing_user_id:
                continue  # Не найден пользователь или это тот же пользователь
            
            # Получаем первый активный счет получателя
            # TODO: Использовать поле default_sbp_account после добавления через миграцию
            recipient_account = recipient_user.accounts.filter_by(is_active=True).first()
            if not recipient_account:
                continue  # Нет активных счетов у получателя
            
            # Создаем встречную транзакцию
            if transaction.transaction_type == 'expense':
                # Исходящий перевод -> создаем входящий для получателя
                counterpart_type = 'income'
                counterpart_description = f"СБП перевод от пользователя системы - {transaction.description}"
            else:
                # Входящий перевод -> создаем исходящий для отправителя
                counterpart_type = 'expense'
                counterpart_description = f"СБП перевод пользователю системы - {transaction.description}"
            
            counterpart_transaction = Transaction(
                date=transaction.date,
                amount=transaction.amount,
                description=counterpart_description,
                transaction_type=counterpart_type,
                category='Financial',
                subcategory='СБП перевод',
                contact_phone=transaction.contact_phone,
                reference=f"auto_{transaction.reference}"
            )
            
            # Добавляем информацию о счете получателя для последующего создания в БД
            counterpart_transaction._recipient_account_id = recipient_account.id
            counterpart_transactions.append(counterpart_transaction)
        
        return counterpart_transactions
    
    def detect_bank_type(self, file_path: str, filename: str) -> Optional[str]:
        """Auto-detect bank type based on file format and content"""
        filename_lower = filename.lower()
        
        if filename_lower.endswith('.xlsx'):
            return 'alpha'  # Alpha Bank uses XLSX
        elif filename_lower.endswith('.csv'):
            return 'raiffeisen'  # Raiffeisen uses CSV
        elif filename_lower.endswith('.pdf'):
            return 'sberbank'  # Sberbank uses PDF
        
        return None
    
    def import_transactions(self, file_path: str, filename: str, bank_type: str = None) -> Tuple[List[Transaction], str]:
        """Import transactions from bank statement file"""
        
        if not bank_type:
            bank_type = self.detect_bank_type(file_path, filename)
        
        if not bank_type or bank_type not in self.parsers:
            raise ValueError(f"Unsupported bank type or file format: {filename}")
        
        parser = self.parsers[bank_type]
        transactions = parser.parse_file(file_path)
        
        return transactions, bank_type
    
    def get_supported_banks(self) -> List[Dict[str, str]]:
        """Get list of supported banks and their formats"""
        return [
            {'name': 'Alpha Bank', 'code': 'alpha', 'format': 'XLSX'},
            {'name': 'Raiffeisen Bank', 'code': 'raiffeisen', 'format': 'CSV'},
            {'name': 'Sberbank', 'code': 'sberbank', 'format': 'PDF'}
        ]