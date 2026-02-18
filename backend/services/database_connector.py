import sqlite3
import random
from datetime import datetime, timedelta
import os
import sqlalchemy
from sqlalchemy import create_engine, text

# Using a file-based SQLite db for persistence across restarts in this demo
DB_PATH = "company_data.db"
# Connection string for SQLAlchemy
# Connection string for SQLAlchemy
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Global Engine Instance (Connection Pooling)
# check_same_thread=False is needed for SQLite in multithreaded (FastAPI) env
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_mock_db():
    """Initializes the mock database with sample company data."""
    start_fresh = False
    if os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM expenses")
            if cursor.fetchone()[0] > 0:
                print(f"Database {DB_PATH} exists and is populated. Skipping initialization.")
                conn.close()
                return
        except sqlite3.OperationalError:
            # Table might not exist, proceed with initialization
            pass
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # --- Create Tables ---
    
    # 1. Expenses Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER,
            category TEXT,
            amount REAL,
            currency TEXT,
            date DATE,
            description TEXT,
            status TEXT,
            merchant TEXT
        )
    ''')
    
    # 2. Employees Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            department TEXT,
            role TEXT,
            manager_id INTEGER,
            location TEXT
        )
    ''')

    # 3. Contracts Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_name TEXT,
            amount REAL,
            start_date DATE,
            end_date DATE,
            signed_by INTEGER,
            status TEXT
        )
    ''')

    # --- Seed Data ---
    
    # Seed Employees
    employees = [
        (1, "Alice Smith", "Sales", "Manager", None, "New York"),
        (2, "Bob Jones", "Engineering", "Developer", 1, "San Francisco"),
        (3, "Charlie Davis", "Marketing", "Director", None, "London"),
        (4, "David Wilson", "Sales", "Associate", 1, "New York"),
    ]
    cursor.executemany('INSERT INTO employees VALUES (?,?,?,?,?,?)', employees)

    # Seed Expenses (Mix of compliant and non-compliant)
    expenses = [
        # Compliant
        (1, "Travel", 150.00, "USD", "2023-10-01", "Client Lunch", "APPROVED", "Pret A Manger"),
        (1, "Office Supplies", 45.00, "USD", "2023-10-02", "Stationery", "APPROVED", "Staples"),
        (2, "Software", 1200.00, "USD", "2023-10-05", "Cloud Subscription", "APPROVED", "AWS"),
        
        # Violations (for demo)
        (4, "Travel", 2500.00, "USD", "2023-10-10", "First Class Flight", "PENDING", "Emirates"), # Violation: Over limit
        (2, "Entertainment", 600.00, "USD", "2023-10-12", "Team Dinner", "APPROVED", "Nobu"),     # Violation: No approval for >$500?
        (3, "Hardware", 5000.00, "USD", "2023-10-15", "New Laptop", "DRAFT", "Apple Store"),      # Violation: Procurement process
        (1, "Gifts", 200.00, "USD", "2023-10-20", "Client Gift", "APPROVED", "Tiffany & Co"),     # Violation: Policy might say no gifts >$100
    ]
    cursor.executemany('INSERT INTO expenses (employee_id, category, amount, currency, date, description, status, merchant) VALUES (?,?,?,?,?,?,?,?)', expenses)

    # --- Load Datasets ---
    try:
        import pandas as pd
        
        # Define paths
        # Go up 3 levels: services -> backend -> project_root
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        base_dataset_path = os.path.join(project_root, "datasets")
        
        if not os.path.exists(base_dataset_path):
             # Fallback: try ../datasets relative to CWD if running from backend
             if os.path.exists("../datasets"):
                 base_dataset_path = "../datasets"
             else:
                 base_dataset_path = "datasets"

        print(f"Loading datasets from: {base_dataset_path}")

        # 4. GDPR Articles
        gdpr_text_path = os.path.join(base_dataset_path, "gdpr_text.csv")
        if os.path.exists(gdpr_text_path):
            print("Loading GDPR Articles...")
            df_gdpr = pd.read_csv(gdpr_text_path)
            # Create table and insert
            df_gdpr.to_sql('gdpr_articles', conn, if_exists='replace', index=False)
            print(f"Loaded {len(df_gdpr)} GDPR articles.")
        else:
            print(f"Warning: {gdpr_text_path} not found.")

        # 5. GDPR Violations
        gdpr_violations_path = os.path.join(base_dataset_path, "gdpr_violations.csv")
        if os.path.exists(gdpr_violations_path):
            print("Loading GDPR Violations...")
            df_violations = pd.read_csv(gdpr_violations_path)
            df_violations.to_sql('gdpr_violations', conn, if_exists='replace', index=False)
            print(f"Loaded {len(df_violations)} GDPR violations.")
        else:
            print(f"Warning: {gdpr_violations_path} not found.")

        # 6. Financial Transactions (Sampled)
        trans_path = os.path.join(base_dataset_path, "LI-Medium_Trans.csv")
        if os.path.exists(trans_path):
            print("Loading Financial Transactions (Sampled)...")
            # Load only 10,000 rows for demo performance
            df_trans = pd.read_csv(trans_path, nrows=10000)
            
            # Rename duplicate columns if necessary
            # The inspection showed: ['Timestamp', 'From Bank', 'Account', 'To Bank', 'Account', ...]
            # Pandas handles duplicate names by adding .1, .2 etc. 
            # We should rename them for clarity.
            df_trans.columns = [
                'timestamp', 'from_bank', 'from_account', 'to_bank', 'to_account', 
                'amount_received', 'receiving_currency', 'amount_paid', 'payment_currency', 
                'payment_format', 'is_laundering'
            ]
            
            df_trans.to_sql('financial_transactions', conn, if_exists='replace', index=False)
            print(f"Loaded {len(df_trans)} financial transactions.")
        else:
            print(f"Warning: {trans_path} not found.")

    except ImportError:
        print("Error: pandas not installed. Skipping dataset loading.")
    except Exception as e:
        print(f"Error loading datasets: {e}")

    conn.commit()
    conn.close()
    print(f"Mock Database initialized at {DB_PATH}")

def execute_compliance_query(query: str):
    """
    Executes a read-only SQL query against the mock database.
    WARNING: vulnerable to injection if not careful, but this is a demo/internal tool.
    Returns: List of dictionaries representing the rows.
    """
    try:
        # Basic safety: ensure it starts with SELECT
        if not query.strip().upper().startswith("SELECT"):
            return {"error": "Only SELECT queries are allowed."}

        engine = create_engine(DATABASE_URL)
        with engine.connect() as connection:
            result = connection.execute(text(query))
            # Convert to list of dicts
            return [dict(row._mapping) for row in result]
    except Exception as e:
        return {"error": str(e)}

def execute_optimized_query(base_query: str, limit: int = 5):
    """
    Executes a query efficiently for large datasets.
    Returns:
        - count: Total number of matching rows (SELECT COUNT(*))
        - rows: The actual data slice (LIMIT n)
    """
    try:
        # Basic safety
        if not base_query.strip().upper().startswith("SELECT"):
            return {"count": 0, "rows": [], "error": "Only SELECT queries allowed"}
            
        # 1. Get Count
        # Replace 'SELECT *' with 'SELECT COUNT(*)'
        # This is a simple regex-free heuristic for this specific use case
        # For complex queries, this might need a proper parser, but for "SELECT * FROM x WHERE y", this is fine.
        count_query = f"SELECT COUNT(*) FROM ({base_query}) as subquery"
        
        # 2. Get Data Slice
        limit_query = f"{base_query} LIMIT {limit}"
        
        # Use global engine
        with engine.connect() as connection:
            # Execute Count
            count_result = connection.execute(text(count_query))
            total_count = count_result.scalar()
            
            # Execute Limit
            rows_result = connection.execute(text(limit_query))
            rows = [dict(row._mapping) for row in rows_result]
            
            return {
                "count": total_count, 
                "rows": rows,
                "dataset_too_large": total_count > limit
            }
            
    except Exception as e:
        return {"count": 0, "rows": [], "error": str(e)}

if __name__ == "__main__":
    init_mock_db()
