from services.database_connector import execute_compliance_query
from services.policy_engine import get_all_policies
from datetime import datetime

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
                # Execute Optimized SQL rule
                # This returns { count, rows } instead of full list
                from services.database_connector import execute_optimized_query
                query_result = execute_optimized_query(rule["sql_query"], limit=5)
                
                violations_count = query_result.get("count", 0)
                violations_rows = query_result.get("rows", [])
                
                if violations_count > 0:
                    results["total_violations"] += violations_count
                    results["details"].append({
                        "policy_id": pid,
                        "policy_name": policy_name,
                        "rule_id": rule.get("rule_id", "Unknown"),
                        "severity": rule.get("severity", "MEDIUM"),
                        "description": rule.get("description", "No description"),
                        "quote": rule.get("quote", ""),
                        "violation_reason": rule.get("description", "Policy specific violation"),
                        "violating_records": violations_rows, # Already limited by optimized query
                        "total_matches": violations_count
                    })
            except Exception as e:
                print(f"Error executing rule {rule.get('rule_id')}: {e}")
    
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
