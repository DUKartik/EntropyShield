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
                # Execute the SQL rule (returns violating rows)
                violations = execute_compliance_query(rule["sql_query"])
                
                if isinstance(violations, list) and len(violations) > 0:
                    results["total_violations"] += len(violations)
                    results["details"].append({
                        "policy_id": pid,
                        "policy_name": policy_name,
                        "rule_id": rule.get("rule_id", "Unknown"),
                        "severity": rule.get("severity", "MEDIUM"),
                        "description": rule.get("description", "No description"),
                        "quote": rule.get("quote", ""),
                        "violating_records": violations # The actual rows
                    })
            except Exception as e:
                print(f"Error executing rule {rule.get('rule_id')}: {e}")
                
    return results
