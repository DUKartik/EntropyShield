import sqlite3
import random
from datetime import datetime, timedelta
import os
import sqlalchemy
from sqlalchemy import create_engine, text

# Using a file-based SQLite db for persistence across restarts in this demo
DB_PATH = "company_data.db"
# Connection string for SQLAlchemy
DATABASE_URL = f"sqlite:///{DB_PATH}"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_mock_db():
    """Initializes the mock database with sample company data."""
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH) # Reset for the demo to ensure clean state

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

if __name__ == "__main__":
    init_mock_db()
