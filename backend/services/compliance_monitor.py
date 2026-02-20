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
    
    # ── 1. Fetch Audit Logs (Triaged Rules) ──
    audit_logs = {}
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT rule_id, action FROM audit_logs")
        for row in cursor.fetchall():
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
                    
                    # Only add to KPIs if NOT triaged
                    if not review_status:
                        results["total_violations"] += violations_count
                        
                    results["details"].append({
                        "policy_id": pid,
                        "policy_name": policy_name,
                        "rule_id": rule_id,
                        "severity": rule.get("severity", "MEDIUM"),
                        "description": rule.get("description", "No description"),
                        "quote": rule.get("quote", ""),
                        "violation_reason": rule.get("description", "Policy specific violation"),
                        "violating_records": violations_rows, # Already limited by optimized query
                        "total_matches": violations_count,
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
