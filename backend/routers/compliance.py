"""
routers/compliance.py
Compliance automation endpoints: policy upload, compliance checks, DB preview,
and aggregated system stats.
"""
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel
# pypdf is lazily imported inside upload_policy() to avoid adding it to startup time

from services.compliance_monitor import run_compliance_check
from services.database_connector import get_db_connection
from services.pipeline_orchestrator import analyze_structural
from services.policy_engine import extract_rules_from_document, get_all_policies, save_policy, get_policy_by_name, delete_policy, clear_all_policies
from utils.debug_logger import get_logger

logger = get_logger()

router = APIRouter()

UPLOAD_DIR = Path("uploads")


@router.post("/policy/upload")
async def upload_policy(
    file: UploadFile = File(...),
    check_tampering: str = "false",
):
    """
    Ingest a policy PDF, optionally run a tamper check, extract compliance
    rules using AI, and persist the policy.

    Query param ``check_tampering=true`` triggers a fast structural forensic
    analysis before parsing.  If the document scores above 0.5 risk it is
    rejected.
    """
    temp_path = UPLOAD_DIR / f"temp_policy_{uuid.uuid4()}.pdf"
    try:
        content = await file.read()
        temp_path.write_bytes(content)
        logger.info(f"Policy upload: {file.filename} (tamper_check={check_tampering})")

        # ── Optional tamper check ─────────────────────────────────────────────
        if check_tampering.lower() == "true":
            logger.info("Running policy tamper check...")
            forensic_report = await analyze_structural(str(temp_path))
            score = forensic_report.get("score", 0.0)

            if score > 0.5:
                flags = forensic_report.get("flags", [])
                flag_msg = "; ".join(flags[:3])
                logger.warning(f"Policy tamper check FAILED (score={score:.2f}): {flag_msg}")
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Security Alert: Document integrity check failed "
                        f"(Score: {score:.2f}). Reasons: {flag_msg}"
                    ),
                )
            logger.info("Policy tamper check passed.")

        # ── AI rule extraction & persistence ─────────────────────────────────
        # Note: We now pass the absolute path of the PDF directly to Vertex AI 
        # for Multimodal OCR extraction instead of doing local text parsing.
        rules = extract_rules_from_document(str(temp_path), file.filename)
        
        # Prevent saving Null or empty policies
        if not rules:
            raise HTTPException(status_code=400, detail="No compliance rules could be extracted from this document." )

        # Prevent duplicate rows by reusing the same policy ID if the filename was uploaded before
        existing_policy_id = get_policy_by_name(file.filename)
        policy_id = existing_policy_id if existing_policy_id else str(uuid.uuid4())

        saved_policy = save_policy(policy_id, file.filename, rules)

        return {"status": "success", "policy_id": policy_id, "data": saved_policy}

    except HTTPException:
        raise  # Re-raise 400 integrity errors unchanged
    except Exception as e:
        logger.error(f"Policy upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_path.exists():
            temp_path.unlink()


@router.get("/policy/list")
def list_policies():
    """
    Return all active policies as a JSON list.
    """
    try:
        policies = get_all_policies()
        return [
            {
                "policy_id": pid,
                "name": pdata["name"],
                "rules": pdata["rules"],
                "rule_count": len(pdata["rules"]),
                "created_at": pdata.get("created_at"),
            }
            for pid, pdata in policies.items()
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/policy/{policy_id}")
def remove_policy(policy_id: str):
    """
    Soft-delete a policy by its ID.
    """
    try:
        deleted = delete_policy(policy_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Policy not found or already deleted.")
        return {"status": "success", "message": f"Policy {policy_id} deleted."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete policy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/policy/clear")
def clear_policies():
    """
    Clear all uploaded policies and triaged audit logs, resetting the system.
    """
    try:
        clear_all_policies()
        return {"status": "success", "message": "All policies cleared"}
    except Exception as e:
        logger.error(f"Failed to clear policies: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/compliance/run")
def trigger_compliance_check(policy_id: str = None):
    """
    Trigger the compliance monitor against all active policies (or a specific
    one when ``policy_id`` is supplied).
    """
    try:
        return run_compliance_check(policy_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/database/preview")
def preview_database():
    """
    Return the first 10 rows of each key table in the company database.
    Useful for the data-viewer component in the frontend.
    """
    tables = ["financial_transactions", "bank_accounts"]
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        data = {}
        for table in tables:
            cursor.execute(f"SELECT * FROM {table} LIMIT 10")  # noqa: S608
            data[table] = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/system/stats")
def get_system_stats():
    """
    Return aggregated dashboard statistics:
    active policy count, total violations, risk level, and real-time event
    count (financial transactions).
    """
    try:
        # Active policies
        policies = get_all_policies()
        active_policies = sum(1 for p in policies.values() if p.get("active", True))

        # Violations and risk score
        compliance_results = run_compliance_check()
        total_violations = compliance_results.get("total_violations", 0)
        high_risk_count = sum(
            1
            for v in compliance_results.get("details", [])
            if v.get("severity") == "HIGH"
        )

        if high_risk_count > 0:
            risk_score = "High"
        elif total_violations > 5:
            risk_score = "Medium"
        else:
            risk_score = "Low"

        # Real-time event count
        total_transactions = 0
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM financial_transactions")
            total_transactions = cursor.fetchone()[0]
            conn.close()
        except Exception as db_err:
            logger.warning(f"Could not count transactions: {db_err}")

        return {
            "risk_score": risk_score,
            "total_violations": total_violations,
            "active_policies": active_policies,
            "real_time_events": total_transactions,
        }
    except Exception as e:
        logger.error(f"System stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class AuditLogRequest(BaseModel):
    id: str
    rule_id: str
    description: str
    action: str
    timestamp: str
    record_preview: str

@router.post("/audit/log")
def log_audit_action(req: AuditLogRequest):
    """
    Log a human review action (APPROVED, REJECTED, or UNDO) for a violation.
    If action is 'UNDO', we delete the record. Otherwise, we upsert it.
    """
    try:
        conn = get_db_connection()
        if req.action == "UNDO":
            conn.execute("DELETE FROM audit_logs WHERE rule_id = ?", (req.rule_id,))
            conn.commit()
            conn.close()
            return {"status": "success", "message": "Audit log undone"}
        
        # Upsert the new action for this rule (only one active triaged state per rule)
        conn.execute(
            """
            INSERT INTO audit_logs (id, rule_id, description, action, timestamp, record_preview)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                description = excluded.description,
                action = excluded.action,
                timestamp = excluded.timestamp,
                record_preview = excluded.record_preview
            """,
            (req.id, req.rule_id, req.description, req.action, req.timestamp, req.record_preview)
        )
        # Also clean up any old logs for this rule ID to strictly keep 1 active state
        conn.execute("DELETE FROM audit_logs WHERE rule_id = ? AND id != ?", (req.rule_id, req.id))
        conn.commit()
        conn.close()
        return {"status": "success", "log_id": req.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/audit/logs")
def get_audit_logs():
    """Retrieve all audit logs."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM audit_logs ORDER BY timestamp DESC")
        logs = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return logs
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
