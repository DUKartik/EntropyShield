import sqlite3
import sys
sys.path.insert(0, r"c:\Users\kartik nath khatri\Desktop\EntropyShield\backend")

from services.policy_engine import seed_demo_policies

print("Seeding policies...")
seed_demo_policies()

conn = sqlite3.connect(r"c:\Users\kartik nath khatri\Desktop\EntropyShield\backend\company_data.db")
cur = conn.cursor()

try:
    cur.execute("SELECT rules FROM policies WHERE id='DEMO-POLICY-001'")
    row = cur.fetchone()
    if row:
        import json
        rules = json.loads(row[0])
        for r in rules:
            if r['rule_id'] in ['AML-001', 'AML-003']:
                print(f"Testing {r['rule_id']}...")
                try:
                    cur.execute(f"SELECT COUNT(*) FROM ({r['sql_query']})")
                    print(f"  -> Found {cur.fetchone()[0]} violations.")
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    print(f"  -> QUERY FAILED: {e}")
except Exception as e:
    print(f"Error fetching rules: {e}")
conn.close()
