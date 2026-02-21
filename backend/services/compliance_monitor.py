from datetime import datetime

from services.database_connector import execute_compliance_query, execute_optimized_query, get_db_connection
from services.policy_engine import get_all_policies
from utils.debug_logger import get_logger

logger = get_logger()

def run_compliance_check(policy_id: str = None):
    """
    Runs compliance rules against the database.
    If policy_id is provided, runs only for that policy.
    Otherwise runs all active policies.
    """
    results = {
        "timestamp": datetime.now().isoformat(),
        "total_violations": 0,
        "details": []
    }
    
    # ── 1. Fetch Audit Logs (Triaged Rules & Records) ──
    audit_logs = {}
    record_audits = {}
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT rule_id, action, record_id FROM audit_logs")
        for row in cursor.fetchall():
            if row["record_id"]:
                # Record-level specific log
                if row["rule_id"] not in record_audits:
                    record_audits[row["rule_id"]] = {}
                record_audits[row["rule_id"]][row["record_id"]] = row["action"]
            else:
                # Rule-level log
                audit_logs[row["rule_id"]] = row["action"]
        conn.close()
    except Exception as e:
        logger.error(f"Failed to fetch audit logs: {e}")
        
    # ── 2. Run Checks ──
    
    policies = get_all_policies()
    
    policies_to_check = []
    if policy_id:
        if policy_id in policies:
            policies_to_check.append((policy_id, policies[policy_id]))
    else:
        for pid, pdata in policies.items():
            if pdata.get("active", True):
                policies_to_check.append((pid, pdata))
                
    for pid, pdata in policies_to_check:
        policy_name = pdata["name"]
        rules = pdata["rules"]
        
        for rule in rules:
            try:
                query_result = execute_optimized_query(rule["sql_query"], limit=5)
                
                violations_count = query_result.get("count", 0)
                violations_rows = query_result.get("rows", [])
                
                if violations_count > 0:
                    rule_id = rule.get("rule_id", "Unknown")
                    review_status = audit_logs.get(rule_id)
                    
                    # Compute effectively how many records are overridden/approved locally
                    local_record_audits = record_audits.get(rule_id, {})
                    
                    # Filter out approved records from the sample rows
                    filtered_rows = []
                    for row in violations_rows:
                        rec_id = str(row.get("id", ""))
                        if local_record_audits.get(rec_id) == "APPROVED":
                            continue
                        filtered_rows.append(row)
                    
                    # Adjust totals
                    approved_records_count = sum(1 for status in local_record_audits.values() if status == "APPROVED")
                    effective_count = violations_count - approved_records_count
                    if effective_count < 0:
                        effective_count = 0
                        
                    # If all records were individually approved, we might effectively treat the rule as triaged if count hits 0
                    if effective_count == 0 and violations_count > 0 and not review_status:
                        review_status = "APPROVED"
                    
                    # Only add to KPIs if NOT triaged at the rule level
                    if not review_status:
                        results["total_violations"] += effective_count
                        
                    if effective_count > 0 or review_status:
                        results["details"].append({
                            "policy_id": pid,
                            "policy_name": policy_name,
                            "rule_id": rule_id,
                            "severity": rule.get("severity", "MEDIUM"),
                            "description": rule.get("description", "No description"),
                            "quote": rule.get("quote", ""),
                            "violation_reason": rule.get("description", "Policy specific violation"),
                            "violating_records": filtered_rows,
                            "total_matches": effective_count,
                            "review_status": review_status # null if untested, else 'APPROVED'/'REJECTED'
                        })
            except Exception as e:
                logger.error(f"Error executing rule {rule.get('rule_id')}: {e}")
    
    # --- GLOBAL OPTIMIZATION: CAP RESULTS ---
    # Sort results to show most critical first:
    # 1. Severity (High < Medium < Low) -> We can map to int
    # 2. Total Matches (Descending)
    
    severity_map = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
    
    results["details"].sort(
        key=lambda x: (severity_map.get(x.get("severity"), 0), x.get("total_matches", 0)),
        reverse=True
    )
    
    # STRICT CAP: Only return top 20 violated rules to Frontend
    # This ensures O(1) payload size regardless of how many rules exist.
    results["details"] = results["details"][:20]
                
    return results
