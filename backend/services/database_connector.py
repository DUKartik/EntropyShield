import os
import sqlite3
from datetime import datetime, timedelta

from sqlalchemy import create_engine, text

from services.dataset_loader import DatasetLoader
from utils.debug_logger import get_logger

logger = get_logger()

# File-based SQLite — persists across restarts in this demo environment
DB_PATH = "company_data.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Module-level pooled engine — created once, reused for all queries
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_mock_db() -> None:
    """
    Initialise the mock company database.

    - Creates schema tables (employees, expenses, contracts) with seed rows.
    - Delegates all CSV dataset ingestion to DatasetLoader, which handles
      chunked reading, stratified sampling, and per-table idempotency checks.
    """
    # Fast-path: if expenses already has data the DB is ready.
    if os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        try:
            # Always ensure the policies table exists (may be missing in older DBs)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS policies (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    rules TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                )
            """)
            # Always ensure the audit_logs table exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id TEXT PRIMARY KEY,
                    rule_id TEXT NOT NULL,
                    description TEXT,
                    action TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    record_preview TEXT
                )
            """)
            conn.commit()
            cursor.execute("SELECT COUNT(*) FROM expenses")
            if cursor.fetchone()[0] > 0:
                logger.info(f"Database {DB_PATH} already populated — skipping init.")
                conn.close()
                return
        except sqlite3.OperationalError:
            pass   # Table doesn't exist yet — proceed with full init
        finally:
            conn.close()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    cursor.execute("""
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
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            department TEXT,
            role TEXT,
            manager_id INTEGER,
            location TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_name TEXT,
            amount REAL,
            start_date DATE,
            end_date DATE,
            signed_by INTEGER,
            status TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS policies (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            rules TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id TEXT PRIMARY KEY,
            rule_id TEXT NOT NULL,
            description TEXT,
            action TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            record_preview TEXT
        )
    """)

    # ------------------------------------------------------------------
    # Seed data
    # ------------------------------------------------------------------

    employees = [
        (1, "Alice Smith",    "Sales",       "Manager",   None, "New York"),
        (2, "Bob Jones",      "Engineering", "Developer", 1,    "San Francisco"),
        (3, "Charlie Davis",  "Marketing",   "Director",  None, "London"),
        (4, "David Wilson",   "Sales",       "Associate", 1,    "New York"),
    ]
    cursor.executemany("INSERT INTO employees VALUES (?,?,?,?,?,?)", employees)

    expenses = [
        # Compliant
        (1, "Travel",          150.00, "USD", "2023-10-01", "Client Lunch",        "APPROVED", "Pret A Manger"),
        (1, "Office Supplies",  45.00, "USD", "2023-10-02", "Stationery",          "APPROVED", "Staples"),
        (2, "Software",       1200.00, "USD", "2023-10-05", "Cloud Subscription",  "APPROVED", "AWS"),
        # Violations (for demo compliance checks)
        (4, "Travel",         2500.00, "USD", "2023-10-10", "First Class Flight",  "PENDING",  "Emirates"),
        (2, "Entertainment",   600.00, "USD", "2023-10-12", "Team Dinner",         "APPROVED", "Nobu"),
        (3, "Hardware",       5000.00, "USD", "2023-10-15", "New Laptop",          "DRAFT",    "Apple Store"),
        (1, "Gifts",           200.00, "USD", "2023-10-20", "Client Gift",         "APPROVED", "Tiffany & Co"),
    ]
    cursor.executemany(
        "INSERT INTO expenses (employee_id, category, amount, currency, date, description, status, merchant) "
        "VALUES (?,?,?,?,?,?,?,?)",
        expenses,
    )

    conn.commit()

    # ------------------------------------------------------------------
    # Dataset ingestion — fully delegated to DatasetLoader
    # ------------------------------------------------------------------
    DatasetLoader().load_all(conn)

    conn.close()
    logger.info(f"Mock database initialised at {DB_PATH}")


def execute_compliance_query(query: str):
    """
    Executes a read-only SQL query against the mock database.
    WARNING: vulnerable to injection if not careful, but this is a demo/internal tool.
    Returns: List of dictionaries representing the rows.
    """
    try:
        # Basic safety: only allow read-only queries
        if not query.strip().upper().startswith("SELECT"):
            return {"error": "Only SELECT queries are allowed."}

        # Reuse the module-level engine (connection pooling)
        with engine.connect() as connection:
            result = connection.execute(text(query))
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
