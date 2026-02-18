
import sqlite3
import pandas as pd
import os

# Adjust path to find the db. 
# Code ran from root, so DB is in root.
# Script is in backend/scripts/verify_datasets.py
# ROOT/backend/scripts/verify_datasets.py
# dirname -> ROOT/backend/scripts
# dirname -> ROOT/backend
# dirname -> ROOT
db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "company_data.db")

print(f"Connecting to database at: {db_path}")

if not os.path.exists(db_path):
    print("Database file not found!")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

def check_table(table_name):
    print(f"\n--- Checking table: {table_name} ---")
    try:
        cursor.execute(f"SELECT count(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        print(f"Row count: {count}")
        
        if count > 0:
            print("Sample data:")
            df = pd.read_sql_query(f"SELECT * FROM {table_name} LIMIT 3", conn)
            print(df)
        else:
            print("Table exists but is empty.")
            
    except sqlite3.OperationalError as e:
        print(f"Error: {e}")

tables = ['gdpr_articles', 'gdpr_violations', 'financial_transactions']
for t in tables:
    check_table(t)

conn.close()
