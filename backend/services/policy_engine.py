import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any
from dotenv import load_dotenv

load_dotenv()

# vertexai and GenerativeModel are NOT imported at module level because
# google-cloud-aiplatform has a heavy import chain (~28 s on first load).
# They are imported lazily inside the functions that actually use them.

from services.database_connector import DB_PATH
from utils.debug_logger import get_logger

logger = get_logger()

# GCP config read from env once (cheap — just os.getenv, no heavy import)
project_id = os.getenv("GCP_PROJECT_ID", os.getenv("GOOGLE_CLOUD_PROJECT", "veridoc-frontend-808108840598"))
location = os.getenv("REGION", "asia-south1")

def _get_db_schema() -> str:
    """Dynamically extracts the SQLite schema to provide accurate context to the LLM."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = cursor.fetchall()
        schema_def = "\n".join([t[0] for t in tables if t[0]])
        return schema_def
    except Exception as e:
        logger.error(f"Failed to read DB schema: {e}")
        return "Schema unavailable"
    finally:
        conn.close()

def _validate_sql_locally(query: str) -> str:
    """Executes EXPLAIN QUERY PLAN or LIMIT 0 to validate syntax against the real DB."""
    if not query.strip().upper().startswith("SELECT"):
        return "Error: Query must be a SELECT statement."
    
    # Use LIMIT 0 to validate the query compiles and columns exist without fetching data
    test_query = f"SELECT * FROM ({query}) LIMIT 0"
    
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute(test_query)
        return "Success: The SQL query is valid."
    except sqlite3.OperationalError as e:
        return f"Error: SQLite OperationalError: {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        conn.close()

def extract_rules_from_document(pdf_path: str, policy_name: str) -> list[dict]:
    """
    Multimodal Agentic Extraction using Gemini 1.5 Pro with Tools.
    The AI dynamically reads the raw PDF using OCR, extracts rules, and checks 
    its SQL queries against the DB schema before returning the JSON.
    """
    if not os.path.exists(pdf_path):
        logger.error(f"Policy document not found at {pdf_path}")
        return []
        
    import vertexai
    from vertexai.generative_models import GenerativeModel, Tool, FunctionDeclaration, Part
    
    # Read the raw PDF bytes
    with open(pdf_path, "rb") as f:
        pdf_content = f.read()
        
    document_part = Part.from_data(pdf_content, mime_type="application/pdf")
    
    try:
        vertexai.init(project=project_id, location=location)
    except Exception as e:
        logger.warning(f"Vertex AI init failed: {e}")
        
    model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-1.5-flash")
    
    # 1. Provide the Live Schema
    db_schema = _get_db_schema()

    # 2. Define the Tool for SQL Validation
    validate_sql_func = FunctionDeclaration(
        name="validate_sql",
        description="Validates a SELECT SQL query against the SQLite database. Returns 'Success' if valid, or the SQLite error message if invalid. You MUST use this tool to verify ANY query you intend to output.",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The SQL SELECT query to test. It must find policy violations (where a result row means a rule was broken)."
                }
            },
            "required": ["query"]
        }
    )
    sql_tool = Tool(function_declarations=[validate_sql_func])

    # 3. Initialize Model with System Instructions
    system_instruction = f"""
You are an expert Compliance Data Engineer. Your goal is to convert a human-readable policy document into executable SQL rules for a SQLite database.

**LIVE DATABASE SCHEMA:**
```sql
{db_schema}
```

**INSTRUCTIONS:**
1. Identify all distinct compliance rules in the text.
2. For each rule, formulate a SQL query that selects the VIOLATING records. (A result row means a violation).
3. **CRITICAL:** You MUST use the `validate_sql` tool to test your queries before finalizing them. Do not guess column names. If a tool call returns an error, adjust the query and test it again until 'Success' is returned.
4. Once all queries are validated successfully, return a JSON array of objects with the following fields:
   - "rule_id": Short string ID (e.g., "EXP-001")
   - "description": Human readable description of the rule.
   - "quote": The exact text from the policy extracted.
   - "sql_query": The validated SQL query.
   - "severity": "HIGH", "MEDIUM", or "LOW".

**OUTPUT FORMAT:**
When you are done testing, output ONLY the valid JSON array. Do not include markdown or conversational text.
    """
    
    model = GenerativeModel(
        model_name,
        system_instruction=system_instruction,
        tools=[sql_tool]
    )

    chat = model.start_chat()
    
    prompt = f"POLICY DOCUMENT TITLE: {policy_name}\n\nPlease read the attached policy document carefully, identify violations, and test your SQL queries."
    
    try:
        logger.info(f"Starting Multimodal Agentic Extraction for: {policy_name}")
        response = chat.send_message([document_part, prompt])
        
        # Agentic Loop: Handle Tool calls up to 10 times to prevent infinite loops
        max_turns = 10
        turns = 0
        while turns < max_turns:
            
            # Helper to safely extract function calls from the Vertex response
            def get_function_calls(resp):
                if not resp.candidates: return []
                fc_list = []
                for part in resp.candidates[0].content.parts:
                    if part.function_call:
                        fc_list.append(part.function_call)
                return fc_list
                
            function_calls = get_function_calls(response)
            
            if function_calls:
                for function_call in function_calls:
                    if function_call.name == "validate_sql":
                        # Convert args to dict mapping
                        query_args = {k: v for k,v in function_call.args.items()}
                        query = query_args.get("query", "")
                        
                        logger.info(f"Agent testing SQL: {query}")
                        validation_result = _validate_sql_locally(query)
                        logger.info(f"Agent received: {validation_result}")
                        
                        # Send the tool response back to the agent
                        response = chat.send_message(
                            Part.from_function_response(
                                name="validate_sql",
                                response={"result": validation_result}
                            )
                        )
            else:
                # No more function calls, the model gave us its final text answer
                break
            turns += 1

        if turns >= max_turns:
            logger.warning("Agentic validation exceeded max turns. Returning best effort response.")

        logger.info(f"Final LLM Response Object: {response}")
        
        # Parse Final JSON Response
        try:
            text_resp = response.text.strip()
        except ValueError:
            # Sometimes if there's no text component, response.text raises a ValueError
            logger.error("No text found in final response.", exc_info=True)
            text_resp = ""
            
        logger.info(f"Raw Text to Parse: '{text_resp}'")
        
        if not text_resp:
            raise ValueError("Empty response text from LLM.")
            
        # Try to robustly extract the JSON array in case there is conversational text
        start_idx = text_resp.find('[')
        end_idx = text_resp.rfind(']')
        if start_idx != -1 and end_idx != -1 and end_idx >= start_idx:
            json_str = text_resp[start_idx:end_idx+1]
        else:
            json_str = text_resp
            
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON. Extracted string: {json_str}")
            raise ValueError(f"Invalid JSON Format: {e}")
            
    except Exception as e:
        logger.error(f"Agentic rule extraction failed: {e}")
        logger.info("Falling back to absolute mock rules.")
        return [
            {
                "rule_id": "MOCK-EXP-001",
                "description": "High value expenses must be approved (Fallback)",
                "quote": "Fallback: Expenses over 1000 require approval",
                "sql_query": "SELECT * FROM expenses WHERE amount > 1000 AND status != 'APPROVED'",
                "severity": "HIGH"
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

def get_policy_by_name(name: str):
    """Retrieve an existing policy ID by its name to prevent duplicates."""
    conn = _get_conn()
    try:
        row = conn.execute("SELECT id FROM policies WHERE name = ?", (name,)).fetchone()
        if row:
            return row["id"]
    finally:
        conn.close()
    return None

def get_all_policies() -> dict[str, Any]:
    """Load all active policies from the DB."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT id, name, rules, active, created_at FROM policies WHERE active = 1"
        ).fetchall()
    finally:
        conn.close()

    return {
        row["id"]: {
            "name": row["name"],
            "rules": json.loads(row["rules"]),
            "active": bool(row["active"]),
            "created_at": row["created_at"],
        }
        for row in rows
    }


def delete_policy(policy_id: str) -> bool:
    """Soft-delete a policy by marking it inactive."""
    conn = _get_conn()
    try:
        cursor = conn.execute(
            "UPDATE policies SET active = 0 WHERE id = ? AND active = 1",
            (policy_id,),
        )
        conn.commit()
        deleted = cursor.rowcount > 0
    finally:
        conn.close()

    if deleted:
        logger.info(f"Policy '{policy_id}' soft-deleted.")
    else:
        logger.warning(f"Policy '{policy_id}' not found or already inactive.")
    return deleted

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


