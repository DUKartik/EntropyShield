
import sys
import os
import sqlite3

# Add backend to sys.path to allow imports
# Assuming script is run from backend/ directory
sys.path.append(os.path.abspath(os.getcwd()))

try:
    from services.database_connector import init_mock_db, DB_PATH
except ImportError:
    # If run from backend/scripts/
    sys.path.append(os.path.dirname(os.path.abspath(os.getcwd())))
    from services.database_connector import init_mock_db, DB_PATH

def verify_tables():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database file {DB_PATH} not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    tables = ['gdpr_articles', 'gdpr_violations', 'financial_transactions']
    all_passed = True
    
    print(f"Verifying tables in {DB_PATH}...")
    
    for table in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"Table '{table}': {count} rows")
            if count == 0:
                print(f"WARNING: Table '{table}' is empty!")
                all_passed = False
        except sqlite3.OperationalError:
            print(f"ERROR: Table '{table}' does not exist!")
            all_passed = False
            
    conn.close()
    
    if all_passed:
        print("\nSUCCESS: All datasets loaded correctly.")
    else:
        print("\nFAILURE: Some datasets missing or empty.")

if __name__ == "__main__":
    print("Initializing Mock DB...")
    init_mock_db()
    verify_tables()
