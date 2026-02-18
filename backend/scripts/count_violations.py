import sqlite3
import sys

# Force UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('company_data.db')
cursor = conn.cursor()

print('=== VIOLATION COUNTS PER RULE ===\n')

rules = {
    'AML-001 (is_laundering = 1)':
        'SELECT COUNT(*) FROM financial_transactions WHERE is_laundering = 1',
    'AML-002 (amount_paid > 500000)':
        'SELECT COUNT(*) FROM financial_transactions WHERE amount_paid > 500000',
    'AML-003 (Reinvestment + laundering)':
        "SELECT COUNT(*) FROM financial_transactions WHERE payment_format = 'Reinvestment' AND is_laundering = 1",
    'GDPR-001 (fines > 1M EUR)':
        'SELECT COUNT(*) FROM gdpr_violations WHERE "Price (EUR)" > 1000000',
    'GDPR-002 (fines > 500K EUR)':
        'SELECT COUNT(*) FROM gdpr_violations WHERE "Price (EUR)" > 500000',
    'EXP-001 (unapproved > $1000)':
        "SELECT COUNT(*) FROM expenses WHERE amount > 1000 AND status != 'APPROVED'",
    'EXP-002 (weekend expenses)':
        "SELECT COUNT(*) FROM expenses WHERE strftime('%w', date) IN ('0', '6')",
    'EXP-003 (entertainment > $500 unapproved)':
        "SELECT COUNT(*) FROM expenses WHERE category = 'Entertainment' AND amount > 500 AND status != 'APPROVED'",
}

total = 0
for name, q in rules.items():
    try:
        cursor.execute(q)
        count = cursor.fetchone()[0]
        total += count
        flag = ' <-- HIGH VOLUME' if count > 100 else ''
        print(f'  {name}: {count}{flag}')
    except Exception as e:
        print(f'  {name}: ERROR - {e}')

print(f'\nTOTAL across all rules: {total}')

# Also check table row counts
print('\n=== TABLE ROW COUNTS ===')
for table in ['financial_transactions', 'bank_accounts', 'gdpr_violations', 'expenses', 'employees']:
    try:
        cursor.execute(f'SELECT COUNT(*) FROM {table}')
        print(f'  {table}: {cursor.fetchone()[0]} rows')
    except Exception as e:
        print(f'  {table}: ERROR - {e}')

conn.close()
