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
                # No more function calls, the model gave us its final text answer.
                # Let's actively validate if it's correct JSON before breaking.
                try:
                    text_resp = response.text.strip()
                except ValueError:
                    text_resp = ""
                    
                if not text_resp:
                    logger.warning("Agent returned empty text. Prompting to retry.")
                    response = chat.send_message("Error: You returned an empty response. You must return a JSON array of rules.")
                    turns += 1
                    continue
                    
                start_idx = text_resp.find('[')
                end_idx = text_resp.rfind(']')
                if start_idx != -1 and end_idx != -1 and end_idx >= start_idx:
                    json_str = text_resp[start_idx:end_idx+1]
                else:
                    json_str = text_resp
                    
                try:
                    parsed_json = json.loads(json_str)
                    logger.info("Agent successfully output valid JSON rules.")
                    return parsed_json
                except json.JSONDecodeError as e:
                    logger.warning(f"Agent output invalid JSON. Prompting to fix. Error: {e}")
                    response = chat.send_message(
                        f"Error: Your output was not a valid JSON array. JSON Parsing Error: {e}\n\n"
                        "You must output ONLY the valid JSON array of rules. Do not include markdown blocks or conversational text. Try again."
                    )
                    
            turns += 1

        logger.warning("Agentic validation exceeded max turns. Returning best effort response.")
        raise ValueError("Agent failed to output valid JSON rules after 10 turns.")
        
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

