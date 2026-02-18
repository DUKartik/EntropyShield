
import sys
import os
import json

# Add backend to sys.path
sys.path.append(os.path.abspath(os.getcwd()))
try:
    from services.compliance_monitor import run_compliance_check
    from services.database_connector import init_mock_db
except ImportError:
    sys.path.append(os.path.dirname(os.path.abspath(os.getcwd())))
    from services.compliance_monitor import run_compliance_check
    from services.database_connector import init_mock_db

def check_response_size():
    print("Initializing DB...")
    init_mock_db()
    
    print("Running Compliance Check...")
    results = run_compliance_check()
    
    # Serialize to measure JSON size
    json_str = json.dumps(results)
    size_mb = len(json_str) / (1024 * 1024)
    print(f"\nResponse Size: {size_mb:.2f} MB")
    
    total_records = 0
    for d in results.get('details', []):
        count = len(d.get('violating_records', []))
        print(f"Rule {d.get('rule_id')}: {count} violating records")
        total_records += count
        
    print(f"Total Violating Records in Payload: {total_records}")

if __name__ == "__main__":
    check_response_size()
