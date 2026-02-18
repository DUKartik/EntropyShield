
import sys
import os
import json
from fastapi.testclient import TestClient

# Add backend to sys.path
sys.path.append(os.path.abspath(os.getcwd()))
try:
    from main import app
except ImportError:
    sys.path.append(os.path.dirname(os.path.abspath(os.getcwd())))
    from main import app

client = TestClient(app)

def test_compliance_run():
    print("\n--- Testing /api/compliance/run ---")
    response = client.get("/api/compliance/run")
    if response.status_code != 200:
        print(f"FAILED: Status {response.status_code}")
        print(response.text)
        return

    data = response.json()
    print("Structure Check:")
    
    # Expected: ComplianceReport interface
    # interface ComplianceReport {
    #   policy_id: string;
    #   timestamp: string;
    #   status: 'PASS' | 'FAIL' | 'WARNING';
    #   details: ViolationDetail[];
    # }
    
    missing = []
    if 'policy_id' not in data: missing.append('policy_id')
    if 'timestamp' not in data: missing.append('timestamp')
    if 'status' not in data: missing.append('status')
    if 'details' not in data: missing.append('details')
    
    if missing:
        print(f"FAILED: Missing keys: {missing}")
    else:
        print("SUCCESS: Root structure matches ComplianceReport.")
        
    if 'details' in data and isinstance(data['details'], list) and len(data['details']) > 0:
        v = data['details'][0]
        # interface ViolationDetail {
        #   rule_id: string;
        #   violation_reason: string;
        #   severity: 'LOW' | 'MEDIUM' | 'HIGH';
        #   transaction_id?: string;
        # }
        v_missing = []
        if 'rule_id' not in v: v_missing.append('rule_id')
        if 'violation_reason' not in v: v_missing.append('violation_reason')
        if 'severity' not in v: v_missing.append('severity')
        
        if v_missing:
            print(f"FAILED: ViolationDetail missing keys: {v_missing}")
        else:
             print("SUCCESS: ViolationDetail structure matches.")
    elif 'details' in data:
        print("WARNING: 'details' is empty, cannot verify ViolationDetail structure.")

def test_database_preview():
    print("\n--- Testing /api/database/preview ---")
    response = client.get("/api/database/preview")
    if response.status_code != 200:
        print(f"FAILED: Status {response.status_code}")
        print(response.text)
        return

    data = response.json()
    print("Structure Check:")
    
    # Expected: DatabaseTables interface
    # interface DatabaseTables {
    #   expenses: any[];
    #   employees: any[];
    #   contracts: any[];
    # }
    
    missing = []
    if 'expenses' not in data: missing.append('expenses')
    if 'employees' not in data: missing.append('employees')
    if 'contracts' not in data: missing.append('contracts')
    
    if missing:
        print(f"FAILED: Missing keys: {missing}")
    else:
        print("SUCCESS: Root structure matches DatabaseTables.")
        print(f"Counts: Expenses={len(data.get('expenses',[]))}, Employees={len(data.get('employees',[]))}, Contracts={len(data.get('contracts',[]))}")

if __name__ == "__main__":
    test_compliance_run()
    test_database_preview()
