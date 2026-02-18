import sqlite3
import sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('company_data.db')
cursor = conn.cursor()

print('=== FINANCIAL TRANSACTIONS: amount_paid distribution ===')
cursor.execute('''
    SELECT 
        COUNT(*) as total,
        MIN(amount_paid) as min_val,
        MAX(amount_paid) as max_val,
        AVG(amount_paid) as avg_val,
        SUM(CASE WHEN amount_paid > 1000000 THEN 1 ELSE 0 END) as over_1M,
        SUM(CASE WHEN amount_paid > 5000000 THEN 1 ELSE 0 END) as over_5M,
        SUM(CASE WHEN amount_paid > 10000000 THEN 1 ELSE 0 END) as over_10M,
        SUM(CASE WHEN is_laundering = 1 THEN 1 ELSE 0 END) as laundering_flagged
    FROM financial_transactions
''')
row = cursor.fetchone()
print(f'  Total rows: {row[0]}')
print(f'  Min: ${row[1]:,.2f}  Max: ${row[2]:,.2f}  Avg: ${row[3]:,.2f}')
print(f'  Over $1M: {row[4]}  Over $5M: {row[5]}  Over $10M: {row[6]}')
print(f'  is_laundering=1: {row[7]}')

print('\n=== PAYMENT FORMAT distribution ===')
cursor.execute('SELECT payment_format, COUNT(*) as cnt FROM financial_transactions GROUP BY payment_format ORDER BY cnt DESC')
for r in cursor.fetchall():
    print(f'  {r[0]}: {r[1]}')

print('\n=== GDPR VIOLATIONS: Price (EUR) distribution ===')
cursor.execute('''
    SELECT 
        COUNT(*) as total,
        MIN("Price (EUR)") as min_val,
        MAX("Price (EUR)") as max_val,
        AVG("Price (EUR)") as avg_val,
        SUM(CASE WHEN "Price (EUR)" > 5000000 THEN 1 ELSE 0 END) as over_5M,
        SUM(CASE WHEN "Price (EUR)" > 10000000 THEN 1 ELSE 0 END) as over_10M,
        SUM(CASE WHEN "Price (EUR)" > 50000000 THEN 1 ELSE 0 END) as over_50M
    FROM gdpr_violations
''')
row = cursor.fetchone()
print(f'  Total rows: {row[0]}')
print(f'  Min: EUR {row[1]:,.0f}  Max: EUR {row[2]:,.0f}  Avg: EUR {row[3]:,.0f}')
print(f'  Over EUR 5M: {row[4]}  Over EUR 10M: {row[5]}  Over EUR 50M: {row[6]}')

conn.close()
