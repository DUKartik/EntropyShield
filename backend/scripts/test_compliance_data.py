
import sys
import os
import time

# Add backend to sys.path
sys.path.append(os.path.abspath(os.getcwd()))
try:
    from services.compliance_monitor import run_compliance_check
    from services.database_connector import init_mock_db
except ImportError:
    sys.path.append(os.path.dirname(os.path.abspath(os.getcwd())))
    from services.compliance_monitor import run_compliance_check
    from services.database_connector import init_mock_db

def test_data_shape():
    print("Initializing DB...")
    init_mock_db() # Ensure DB exists and has data
    
    print("Running Compliance Check...")
    results = run_compliance_check()
    
    print("\n--- Compliance Results ---")
    print(f"Total Violations: {results['total_violations']}")
    
    if results['details']:
        first = results['details'][0]
        print(f"First Violation Keys: {list(first.keys())}")
        
        required_keys = ['rule_id', 'violation_reason', 'severity', 'description']
        missing = [k for k in required_keys if k not in first]
        
        if missing:
            print(f"FAILED: Missing keys in violation detail: {missing}")
        else:
            print("SUCCESS: Violation details have all required keys.")
            print(f"Sample Reason: {first['violation_reason']}")
    else:
        print("WARNING: No violations found to test structure against.")

if __name__ == "__main__":
    test_data_shape()
