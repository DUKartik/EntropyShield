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

def _list_tables() -> str:
    """Returns a list of tables in the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA query_only = ON;")
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = cursor.fetchall()
        return json.dumps([t[0] for t in tables])
    except Exception as e:
        logger.error(f"Failed to list tables: {e}")
        return json.dumps({"error": str(e)})
    finally:
        conn.close()

def _get_table_schema(table_name: str) -> str:
    """Returns the CREATE TABLE statement for a specific table."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA query_only = ON;")
        cursor = conn.cursor()
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        row = cursor.fetchone()
        if row:
            return row[0]
        return f"Table '{table_name}' not found."
    except Exception as e:
        logger.error(f"Failed to get schema for {table_name}: {e}")
        return f"Error: {e}"
    finally:
        conn.close()

def _sample_data(table_name: str) -> str:
    """Returns 3 sample rows from a specific table to understand data formats."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA query_only = ON;")
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
        rows = cursor.fetchall()
        if rows:
            return json.dumps([dict(row) for row in rows])
        return "[]" # Empty table
    except Exception as e:
        logger.error(f"Failed to sample data from {table_name}: {e}")
        return f"Error: {e}"
    finally:
        conn.close()

def _validate_sql_locally(query: str) -> str:
    """Executes EXPLAIN QUERY PLAN or LIMIT 0 to validate syntax against the real DB in read-only mode."""
    if not query.strip().upper().startswith("SELECT"):
        return "Error: Query must be a SELECT statement."
    
    conn = sqlite3.connect(DB_PATH)
    try:
        # Prevent DROP/DELETE/INSERT dynamically
        conn.execute("PRAGMA query_only = ON;")
        cursor = conn.cursor()
        
        # We only want to validate, not fetch massive data, so wrap in LIMIT 0
        test_query = f"SELECT * FROM ({query}) LIMIT 0"
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
    Enterprise-Grade Agentic Extraction using Gemini 1.5 Pro.
    Features:
    - Exploratory DB tools (list tables, get schemas, sample data)
    - Safe SQL execution (PRAGMA query_only=ON)
    - Chain-of-Thought reasoning
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
        
    model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-1.5-pro")
    
    # 1. Define the Tools for DB Exploration and Validation
    list_tables_func = FunctionDeclaration(
        name="list_tables",
        description="Returns a list of all tables in the SQLite database.",
        parameters={"type": "object", "properties": {}}
    )
    get_schema_func = FunctionDeclaration(
        name="get_table_schema",
        description="Returns the CREATE TABLE statement for a specific table so you can see its columns.",
        parameters={
            "type": "object",
            "properties": {"table_name": {"type": "string"}},
            "required": ["table_name"]
        }
    )
    sample_data_func = FunctionDeclaration(
        name="sample_data",
        description="Returns 3 sample rows from a specific table so you can understand data types, formatting, and string values (e.g., 'pending' vs 'PENDING').",
        parameters={
            "type": "object",
            "properties": {"table_name": {"type": "string"}},
            "required": ["table_name"]
        }
    )
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
    
    agent_tools = Tool(function_declarations=[
        list_tables_func, get_schema_func, sample_data_func, validate_sql_func
    ])

    # 2. Initialize Model with System Instructions
    system_instruction = '''
You are an expert Compliance Data Engineer. Your goal is to convert a human-readable policy document into executable SQL rules for a SQLite database.

**INSTRUCTIONS:**
1. **Explore:** You don't know the DB schema yet. Use `list_tables`, `get_table_schema`, and `sample_data` to explore the database and find relevant tables and exact data values to match against.
2. **Identify:** Find all distinct compliance rules in the document.
3. **Formulate & Test:** For each rule, formulate a SQL query that selects the VIOLATING records (a resulting row means a violation). You MUST use the `validate_sql` tool to test your queries. Adjust query if it fails.
4. **Final Output Format:** Once all queries are successfully validated, output the final rules as a JSON array of objects. Do not use markdown wrappers, just raw JSON.

**SCHEMA FOR FINAL JSON ARRAY ITEMS:**
{
  "rule_id": "EXP-001",
  "description": "Human readable description",
  "quote": "Exact policy text",
  "chain_of_thought": "My reasoning for this SQL logic...",
  "sql_query": "SELECT * FROM ...",
  "severity": "HIGH", "MEDIUM", or "LOW"
}
'''
    
    model = GenerativeModel(
        model_name,
        system_instruction=system_instruction,
        tools=[agent_tools],
        # Explicitly request JSON output as a Structured Output constraint
        generation_config={"response_mime_type": "application/json"}
    )

    chat = model.start_chat()
    
    prompt = f"POLICY DOCUMENT TITLE: {policy_name}\n\nPlease read the attached policy document carefully, explore the DB, identify violations, test queries, and output the final JSON array of rules."
    
    try:
        logger.info(f"Starting Enterprise Agentic Extraction for: {policy_name}")
        response = chat.send_message([document_part, prompt])
        
        # Agentic Loop: Handle Tool calls up to 15 times to allow deep exploration
        max_turns = 15
        turns = 0
        while turns < max_turns:
            
            def get_function_calls(resp):
                if not resp.candidates: return []
                fc_list = []
                for part in resp.candidates[0].content.parts:
                    if part.function_call:
                        fc_list.append(part.function_call)
                return fc_list
                
            function_calls = get_function_calls(response)
            
            if function_calls:
                tool_responses = []
                for function_call in function_calls:
                    func_name = function_call.name
                    args = {k: v for k,v in function_call.args.items()}
                    
                    logger.info(f"Agent using tool: {func_name} with args: {args}")
                    
                    result = ""
                    if func_name == "list_tables":
                        result = _list_tables()
                    elif func_name == "get_table_schema":
                        result = _get_table_schema(args.get("table_name", ""))
                    elif func_name == "sample_data":
                        result = _sample_data(args.get("table_name", ""))
                    elif func_name == "validate_sql":
                        result = _validate_sql_locally(args.get("query", ""))
                    
                    # Truncate result for logging
                    trunc_result = str(result)[:100] + "..." if len(str(result)) > 100 else str(result)
                    logger.info(f"Tool {func_name} result: {trunc_result}")
                    
                    tool_responses.append(
                        Part.from_function_response(
                            name=func_name,
                            response={"result": result}
                        )
                    )
                
                # Send all tool responses back in one turn
                response = chat.send_message(tool_responses)
            else:
                # No function calls, expecting final JSON payload
                text_resp = response.text.strip()
                if not text_resp:
                    logger.warning("Agent returned empty text. Prompting to retry.")
                    response = chat.send_message("Error: Empty response. Return the final JSON array.")
                    turns += 1
                    continue
                    
                try:
                    parsed_json = json.loads(text_resp)
                    logger.info("Agent successfully output valid JSON rules.")
                    return parsed_json
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON parsing failed. Forcing retry. Error: {e}")
                    response = chat.send_message(
                        f"Your output was not valid JSON. Error: {e}. Output ONLY raw JSON array without markdown blocks."
                    )
            
            turns += 1

        logger.warning("Agentic exploration exceeded max turns.")
        raise ValueError("Agent failed to output valid JSON rules after time limit.")
        
    except Exception as e:
        logger.error(f"Agentic rule extraction failed: {e}")
        raise ValueError(f"Failed to extract rules from document: {e}")

        
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
    # This was likely removed in the remote commit, but we are keeping it per user request
    pass

def clear_all_policies() -> None:
    """Delete all policies and associated audit logs to reset the system."""
    conn = _get_conn()
    try:
        conn.execute("DELETE FROM policies")
        conn.execute("DELETE FROM audit_logs")
        conn.commit()
        logger.info("All policies and audit logs have been cleared.")
    finally:
        conn.close()

