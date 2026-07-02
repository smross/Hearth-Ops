import os
import sqlite3
import hashlib
import sys
import json

# We are running inside /app in the docker container, where database.py and database path are located
from database import DB_PATH, get_db_connection
from main import app, hash_pin

# Load expected parent and pin dynamically (from family_members.json or fallback)
parent_name = "Parent 1"
parent_pin = "1234"
config_paths = [
    "family_members.json",
    "backend/family_members.json",
    "/app/family_members.json",
    "/app/backend/family_members.json"
]
for path in config_paths:
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                members = json.load(f)
                for m in members:
                    if m.get("is_parent"):
                        parent_name = m["name"]
                        parent_pin = m["pin"]
                        break
            break
        except Exception:
            pass

def test_database_and_pin_hashing():
    print("=== Testing Database and PIN Hashing ===")
    print(f"Database path: {DB_PATH}")
    if not os.path.exists(DB_PATH):
        print(f"Error: Database file does not exist at {DB_PATH}")
        sys.exit(1)
        
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Check users table
        cursor.execute("SELECT id, name, pin_hash, token_balance FROM users")
        users = cursor.fetchall()
        print(f"Found {len(users)} users:")
        parent_found = False
        for user in users:
            print(f" - ID: {user['id']}, Name: {user['name']}, Token Balance: {user['token_balance']}")
            if user['name'] == parent_name:
                parent_found = True
                expected_hash = hash_pin(parent_pin)
                if user['pin_hash'] == expected_hash:
                    print(f"   [PASS] PIN hash matches expected SHA-256 hash for {parent_name}.")
                else:
                    print(f"   [FAIL] Hash mismatch for {parent_name}. Got {user['pin_hash']}, expected {expected_hash}")
                    sys.exit(1)
        
        if not parent_found:
            print(f"Error: {parent_name} not found in database users.")
            sys.exit(1)

        # Check chores table
        cursor.execute("SELECT COUNT(*) as count FROM chores")
        chores_count = cursor.fetchone()['count']
        print(f"Found {chores_count} chores in database.")
        if chores_count == 0:
            print("Error: No chores found in database.")
            sys.exit(1)

        # Check rewards table
        cursor.execute("SELECT COUNT(*) as count FROM rewards")
        rewards_count = cursor.fetchone()['count']
        print(f"Found {rewards_count} rewards in database.")
        if rewards_count == 0:
            print("Error: No rewards found in database.")
            sys.exit(1)
            
        print("[PASS] Database queries, PIN hashing, and rewards verified successfully.")

def test_api_routing_internally():
    print("\n=== Testing API Routing Internally ===")
    try:
        # Import inside the try to avoid module load errors
        import httpx
        from fastapi.testclient import TestClient
        client = TestClient(app)
        
        # Test health check endpoint
        response = client.get("/health")
        if response.status_code == 200 and response.json().get("status") == "healthy":
            print("[PASS] TestClient GET /health returned 200 healthy.")
        else:
            print(f"[FAIL] TestClient GET /health returned {response.status_code}: {response.text}")
            sys.exit(1)

        # Test verify endpoint (valid pin)
        response = client.post("/api/verify", json={"name": parent_name, "pin": parent_pin})
        if response.status_code == 200:
            user_data = response.json()
            print(f"[PASS] TestClient POST /api/verify succeeded for {parent_name} (ID: {user_data.get('id')}).")
        else:
            print(f"[FAIL] TestClient POST /api/verify failed for {parent_name}: {response.status_code} {response.text}")
            sys.exit(1)
            
        # Test verify endpoint (invalid pin)
        response = client.post("/api/verify", json={"name": parent_name, "pin": "9999"})
        if response.status_code == 401:
            print("[PASS] TestClient POST /api/verify returned 401 Unauthorized for incorrect PIN.")
        else:
            print(f"[FAIL] TestClient POST /api/verify with wrong PIN returned status {response.status_code} instead of 401.")
            sys.exit(1)
            
    except ImportError as e:
        print(f"TestClient could not be imported (missing httpx/dependencies): {e}")
        print("Falling back to testing API endpoints externally using urllib...")
        import urllib.request
        
        # Health check
        try:
            with urllib.request.urlopen("http://localhost:8000/health") as r:
                res = json.loads(r.read().decode())
                if res.get("status") == "healthy":
                    print("[PASS] urllib GET /health returned healthy.")
                else:
                    print(f"[FAIL] urllib GET /health returned unexpected json: {res}")
                    sys.exit(1)
        except Exception as ex:
            print(f"[FAIL] Health check request failed: {ex}")
            sys.exit(1)
            
        # Verify endpoint (valid pin)
        try:
            req = urllib.request.Request(
                "http://localhost:8000/api/verify",
                data=json.dumps({"name": parent_name, "pin": parent_pin}).encode(),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req) as r:
                res = json.loads(r.read().decode())
                print(f"[PASS] urllib POST /api/verify succeeded for {parent_name} (ID: {res.get('id')}).")
        except Exception as ex:
            print(f"[FAIL] Verify PIN request failed: {ex}")
            sys.exit(1)

if __name__ == "__main__":
    test_database_and_pin_hashing()
    test_api_routing_internally()
    print("\nALL VERIFICATIONS PASSED SUCCESSFULLY!")
