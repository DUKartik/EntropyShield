
import sys
import os

# Add backend to sys.path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.database_connector import init_mock_db

print("Running init_mock_db verification...")
init_mock_db()
print("Verification complete.")
