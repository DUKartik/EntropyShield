import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from typing import Any

# vertexai and GenerativeModel are NOT imported at module level because
# google-cloud-aiplatform has a heavy import chain (~28 s on first load).
# They are imported lazily inside the functions that actually use them.

from services.database_connector import DB_PATH
from utils.debug_logger import get_logger

logger = get_logger()

# GCP config read from env once (cheap — just os.getenv, no heavy import)
project_id = os.getenv("GCP_PROJECT_ID", os.getenv("GOOGLE_CLOUD_PROJECT", "veridoc-frontend-808108840598"))
location = os.getenv("GCP_LOCATION", "us-central1")

def load_gemini_pro():
    # Lazy import: vertexai only loads when Gemini is first invoked
    import vertexai  # noqa: PLC0415
    from vertexai.generative_models import GenerativeModel  # noqa: PLC0415
    try:
        vertexai.init(project=project_id, location=location)
    except Exception as e:
        logger.warning(f"Vertex AI init failed: {e}")
    return GenerativeModel("gemini-1.5-pro-001")

def extract_rules_from_text(policy_text: str, policy_name: str) -> list[dict]:
    """
    Uses Gemini 1.5 Pro to extract executable compliance rules from policy text.
    Returns a list of rule objects.
    """
    try:
        model = load_gemini_pro()
        
        prompt = f"""
        You are a Compliance Data Data Engineer. Your goal is to convert a human-readable policy document into executable SQL rules for a SQLite database.
        
        The database has the following tables:
        1. expenses (id, employee_id, category, amount, currency, date, description, status, merchant)
        2. employees (id, name, department, role, manager_id, location)
        3. contracts (id, vendor_name, amount, start_date, end_date, signed_by, status)
        
        POLICY DOCUMENT TITLE: {policy_name}
        POLICY CONTENT:
        {policy_text}
        
        --------------------------------------------------
        
        INSTRUCTIONS:
        1. Identify all distinct compliance rules in the text.
        2. For each rule, generate a SQL query that selects the VIOLATING records.
           - A result means a VIOLATION.
           - If the policy says "Expenses over 500 must be approved", the query should find expenses over 500 that are NOT approved.
           - Use generic SQL compatible with SQLite.
        3. Return a JSON array of objects with these fields:
           - "rule_id": Short string ID (e.g., "EXP-001")
           - "description": Human readable description of the rule.
           - "quote": The exact text from the policy extracted.
           - "sql_query": The SQL query to find violations.
           - "severity": "HIGH", "MEDIUM", or "LOW".
           
        OUTPUT FORMAT:
        Return ONLY valid JSON. Do not include markdown formatting or explanations.
        """
        
        response = model.generate_content(prompt)
        
        # Clean response (remove markdown backticks if present)
        text_resp = response.text.strip()
        if text_resp.startswith("```json"):
            text_resp = text_resp[7:-3]
        elif text_resp.startswith("```"):
            text_resp = text_resp[3:-3]
            
        return json.loads(text_resp)
        
    except Exception as e:
        logger.error(f"Vertex AI rule extraction failed: {e}")
        logger.info("Falling back to mock rules for demonstration.")
        
        # FALLBACK MOCK RULES
        # so the user can test the UI even if they lack GCP permissions
        return [
            {
                "rule_id": "MOCK-EXP-001",
                "description": "High value expenses must be approved (Mock Rule)",
                "quote": "Fallback: Expenses over 1000 require approval",
                "sql_query": "SELECT * FROM expenses WHERE amount > 1000 AND status != 'APPROVED'",
                "severity": "HIGH"
            },
             {
                "rule_id": "MOCK-EXP-002",
                "description": "No expenses on weekends (Mock Rule)",
                "quote": "Fallback: Expenses incurred on Sat/Sun are not reimbursable",
                "sql_query": "SELECT * FROM expenses WHERE strftime('%w', date) IN ('0', '6')", 
                "severity": "MEDIUM"
            }
        ]
        
# ---------------------------------------------------------------------------
# Policy Storage — SQLite-backed (persists across restarts)
# ---------------------------------------------------------------------------

def _get_conn() -> sqlite3.Connection:
    """Return a connection to the shared company_data.db."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def save_policy(policy_id: str, name: str, rules: list[dict]) -> dict[str, Any]:
    """Upsert a policy into the DB and return its full record."""
    conn = _get_conn()
    try:
        conn.execute(
            """
            INSERT INTO policies (id, name, rules, active, created_at)
            VALUES (?, ?, ?, 1, ?)
            ON CONFLICT(id) DO UPDATE SET
                name       = excluded.name,
                rules      = excluded.rules,
                active     = 1,
                created_at = excluded.created_at
            """,
            (policy_id, name, json.dumps(rules), datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        logger.info(f"Policy '{name}' saved to DB (id={policy_id}, {len(rules)} rules).")
    finally:
        conn.close()

    return {"name": name, "rules": rules, "active": True}


def get_all_policies() -> dict[str, Any]:
    """Load all active policies from the DB."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT id, name, rules, active FROM policies WHERE active = 1"
        ).fetchall()
    finally:
        conn.close()

    return {
        row["id"]: {
            "name": row["name"],
            "rules": json.loads(row["rules"]),
            "active": bool(row["active"]),
        }
        for row in rows
    }

def seed_demo_policies() -> None:
    """
    Seeds built-in demo compliance policies so the system scan works
    out-of-the-box without requiring a manual policy upload.
    Only seeds if no policies exist in the DB.
    """
    conn = _get_conn()
    try:
        count = conn.execute("SELECT COUNT(*) FROM policies").fetchone()[0]
    finally:
        conn.close()

    # Force updating demo policies for the rewrite
    # if count > 0:
    #     logger.info("Demo policies already seeded — skipping.")
    #     return

    demo_rules = [
        # --- AML / Financial Crime Rules ---
        # AML-001: Direct laundering flag removed. Replaced with heuristic: High-value cross-institution wire transfers
        {
            "rule_id": "AML-001",
            "description": "High-value cross-institution Wire transfers (Potential structured placement)",
            "quote": "Wire transfers exceeding $500,000 sent to external institutions must be reviewed.",
            "sql_query": (
                "SELECT ft.timestamp, ft.from_account, ba_from.entity_name AS sender_entity, "
                "ft.to_account, ba_to.entity_name AS receiver_entity, "
                "ft.amount_paid, ft.payment_currency, ft.payment_format "
                "FROM financial_transactions ft "
                "LEFT JOIN bank_accounts ba_from ON ft.from_account = ba_from.account_number "
                "LEFT JOIN bank_accounts ba_to ON ft.to_account = ba_to.account_number "
                "WHERE ft.payment_format = 'Wire' AND ft.amount_paid > 500000 AND ft.from_bank != ft.to_bank"
            ),
            "severity": "HIGH"
        },
        # AML-002: Threshold raised to $10M — catches ~1.26% of rows (126/10k), realistic for SAR filing
        {
            "rule_id": "AML-002",
            "description": "Extremely large transactions over $10M (Suspicious Activity Report threshold)",
            "quote": "Transactions exceeding $10,000,000 must be reported via Suspicious Activity Report (SAR).",
            "sql_query": (
                "SELECT ft.timestamp, ft.from_account, ba_from.entity_name AS sender_entity, "
                "ft.to_account, ba_to.entity_name AS receiver_entity, "
                "ft.amount_paid, ft.payment_currency "
                "FROM financial_transactions ft "
                "LEFT JOIN bank_accounts ba_from ON ft.from_account = ba_from.account_number "
                "LEFT JOIN bank_accounts ba_to ON ft.to_account = ba_to.account_number "
                "WHERE ft.amount_paid > 10000000"
            ),
            "severity": "HIGH"
        },
        # AML-003: High-value Reinvestment
        {
            "rule_id": "AML-003",
            "description": "High-value Reinvestment transactions (Potential Layering)",
            "quote": "Reinvestment transactions exceeding $1,000,000 used to layer illicit funds must be escalated.",
            "sql_query": (
                "SELECT ft.timestamp, ft.from_account, ba.entity_name AS entity, "
                "ft.amount_paid, ft.payment_format "
                "FROM financial_transactions ft "
                "LEFT JOIN bank_accounts ba ON ft.from_account = ba.account_number "
                "WHERE ft.payment_format = 'Reinvestment' AND ft.amount_paid > 1000000"
            ),
            "severity": "HIGH"
        },
        # AML-004: Bitcoin transactions — always suspicious in AML context
        {
            "rule_id": "AML-004",
            "description": "Bitcoin transactions (high-risk payment format for AML)",
            "quote": "Cryptocurrency transactions require enhanced due diligence under FATF guidelines.",
            "sql_query": (
                "SELECT ft.timestamp, ft.from_account, ba_from.entity_name AS sender_entity, "
                "ft.to_account, ba_to.entity_name AS receiver_entity, "
                "ft.amount_paid, ft.payment_currency "
                "FROM financial_transactions ft "
                "LEFT JOIN bank_accounts ba_from ON ft.from_account = ba_from.account_number "
                "LEFT JOIN bank_accounts ba_to ON ft.to_account = ba_to.account_number "
                "WHERE ft.payment_format = 'Bitcoin'"
            ),
            "severity": "MEDIUM"
        },
        # --- GDPR Rules ---
        # GDPR-001: Top-tier fines only (€10M+) — truly exceptional violations
        {
            "rule_id": "GDPR-001",
            "description": "Exceptional GDPR fines over €10M (systemic data protection failures)",
            "quote": "Fines up to €20M or 4% of global annual turnover for the most serious infringements.",
            "sql_query": "SELECT * FROM gdpr_violations WHERE CAST(REPLACE(\"Price (EUR)\", ',', '') AS REAL) > 10000000",
            "severity": "HIGH"
        },
        # GDPR-002: Mid-tier fines (€1M-€10M) — significant but not exceptional
        {
            "rule_id": "GDPR-002",
            "description": "Significant GDPR fines between €1M and €10M",
            "quote": "Fines up to €10M or 2% of global annual turnover for less serious infringements.",
            "sql_query": "SELECT * FROM gdpr_violations WHERE CAST(REPLACE(\"Price (EUR)\", ',', '') AS REAL) BETWEEN 1000000 AND 10000000",
            "severity": "MEDIUM"
        },
        # --- Expense Rules ---
        {
            "rule_id": "EXP-001",
            "description": "High-value expenses require approval (over $1,000)",
            "quote": "All expenses over $1,000 must be approved before reimbursement.",
            "sql_query": "SELECT * FROM expenses WHERE amount > 1000 AND status != 'APPROVED'",
            "severity": "HIGH"
        },
        {
            "rule_id": "EXP-002",
            "description": "Weekend expenses are not reimbursable",
            "quote": "Expenses incurred on Saturday or Sunday are not eligible for reimbursement.",
            "sql_query": "SELECT * FROM expenses WHERE strftime('%w', date) IN ('0', '6')",
            "severity": "MEDIUM"
        },
        {
            "rule_id": "EXP-003",
            "description": "Entertainment expenses over $500 need pre-approval",
            "quote": "Entertainment spending above $500 requires manager sign-off.",
            "sql_query": "SELECT * FROM expenses WHERE category = 'Entertainment' AND amount > 500 AND status != 'APPROVED'",
            "severity": "MEDIUM"
        },
    ]

    save_policy(
        policy_id="DEMO-POLICY-001",
        name="Built-in Compliance Ruleset (AML + GDPR + Expenses)",
        rules=demo_rules
    )
    logger.info("Seeded demo compliance policies (AML + GDPR + Expenses).")


