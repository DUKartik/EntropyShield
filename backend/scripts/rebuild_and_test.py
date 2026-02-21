import sqlite3
import os
import sys

db_path = r"c:\Users\kartik nath khatri\Desktop\EntropyShield\backend\company_data.db"
sys.path.insert(0, r"c:\Users\kartik nath khatri\Desktop\EntropyShield\backend")

from services.database_connector import init_mock_db
from services.policy_engine import seed_demo_policies
from services.dataset_loader import DatasetLoader

conn = sqlite3.connect(db_path)

print("Triggering DatasetLoader.load_all()...")
loader = DatasetLoader()
loader.load_all(conn)

print("Verifying Columns...")
cur = conn.cursor()
cur.execute("PRAGMA table_info(financial_transactions)")
cols = [row[1] for row in cur.fetchall()]
print(f"Columns in financial_transactions: {cols}")
if "is_laundering" in cols:
    print("ERROR: Data Leakage persists!")
else:
    print("SUCCESS: `is_laundering` is removed.")

# Verify Rules Work
cur.execute("SELECT name, rules FROM policies WHERE id = 'DEMO-POLICY-001'")
row = cur.fetchone()
if row:
    import json
    rules = json.loads(row[1])
    for r in rules:
        if r['rule_id'] in ['AML-001', 'AML-003']:
            print(f"Testing {r['rule_id']}: {r['description']}")
            print(f"SQL: {r['sql_query']}")
            count_q = f"SELECT COUNT(*) FROM ({r['sql_query']})"
            try:
                cur.execute(count_q)
                count = cur.fetchone()[0]
                print(f"  -> Found {count} violations with heuristic rule.")
            except Exception as e:
                print(f"  -> ERROR executing rule: {e}")
                
conn.close()
