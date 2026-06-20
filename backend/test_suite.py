import os
import sqlite3
import pytest
from fastapi.testclient import TestClient
from bs4 import BeautifulSoup
from freezegun import freeze_time

# Override database path globally for testing to enforce database isolation sandboxing
import database
TEST_DB_PATH = os.path.join(os.path.dirname(__file__), "test_sandbox_hearth.db")
database.set_db_path(TEST_DB_PATH)

from main import app, hash_pin
from database import get_db_connection, init_db

@pytest.fixture(autouse=True)
def run_around_tests():
    """Fixture that initializes a sandboxed SQLite database before every test case and tears it down afterwards."""
    # Tear down if old sandbox exists
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
        
    # Re-initialize sandboxed database tables using core schema
    init_db()
    
    # Seed minimal baseline users and chores for predictable testing
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Insert test users (Parents and Children)
        cursor.execute("INSERT INTO users (id, name, pin_hash, token_balance, is_parent) VALUES (1, 'Parent test', ?, 10.0, 1)", (hash_pin("1234"),))
        cursor.execute("INSERT INTO users (id, name, pin_hash, token_balance, is_parent) VALUES (2, 'Kid test', ?, 5.0, 0)", (hash_pin("1111"),))
        
        # Insert test chores of various frequencies, constraints, and requirements
        # 1. Normal daily optional chore
        cursor.execute(
            "INSERT INTO chores (id, title, description, category, frequency, value_credits, max_daily_completions, is_active, is_required, is_shared, after_four_pm) VALUES (1, 'Feed Pets', 'Daily optional chore', 'General', 'daily', 2.0, 1, 1, 0, 1, 0)"
        )
        # 2. Daily required chore
        cursor.execute(
            "INSERT INTO chores (id, title, description, category, frequency, value_credits, max_daily_completions, is_active, is_required, is_shared, after_four_pm) VALUES (2, 'Make Bed', 'Daily required chore', 'Personal', 'daily', 1.0, 1, 1, 1, 0, 0)"
        )
        # 3. Weekly required chore
        cursor.execute(
            "INSERT INTO chores (id, title, description, category, frequency, value_credits, max_daily_completions, is_active, is_required, is_shared, after_four_pm) VALUES (3, 'Clean Room', 'Weekly required chore', 'Personal', 'weekly', 5.0, 1, 1, 1, 0, 0)"
        )
        # 4. Evening-only chore (Available after 4:00 PM)
        cursor.execute(
            "INSERT INTO chores (id, title, description, category, frequency, value_credits, max_daily_completions, is_active, is_required, is_shared, after_four_pm) VALUES (4, 'Evening Dishwasher', 'Only after 4 PM', 'Kitchen', 'daily', 3.0, 1, 1, 0, 1, 1)"
        )
        
        # Seed an unread encouragement to verify regression layout wrapping
        cursor.execute(
            "INSERT INTO encouragements (id, sender_id, recipient_id, content, is_read) VALUES (1, 1, 2, 'awesome_work_very_long_unbroken_string_test_wrapping', 0)"
        )
        
        # Assign chore 2 specifically to Kid test (User 2)
        cursor.execute("INSERT INTO chore_assignments (chore_id, user_id) VALUES (2, 2)")
        # Assign chore 3 specifically to Kid test (User 2)
        cursor.execute("INSERT INTO chore_assignments (chore_id, user_id) VALUES (3, 2)")
        
        conn.commit()

    yield # Execute actual test logic

    # Tear down database file to leave no trace in active filesystem directories
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass

@pytest.fixture
def client():
    """Returns a FastAPI TestClient configured for request mocking."""
    return TestClient(app)

# ----------------- REGRESSION TESTS -----------------

def test_regression_query_empty_strings(client):
    """
    Ensures that sending empty filter strings to the audit query endpoint 
    does NOT crash the backend with a 422 validation error.
    """
    response = client.get("/api/admin/audit/query?days=&user_id=&chore_id=")
    assert response.status_code == 200
    assert "Loading audit logs" not in response.text # Assumes it returns actual templates

def test_regression_long_kudos_wrapping(client):
    """
    Verifies that formatting styles (word-break) are present in templates
    to prevent long text from breaking layout boundaries.
    """
    # Fetch base template to ensure it parses successfully
    response = client.post("/api/verify-ui", data={"name": "Kid test", "pin": "1111"})
    assert response.status_code == 200
    # Verify word-break styling is active in HTML response
    assert "word-break: break-word" in response.text

# ----------------- SECURITY & AUTHENTICATION TESTS -----------------

def test_pin_verification(client):
    """Validates login with correct and incorrect PIN hashes."""
    # Correct PIN
    response = client.post("/api/verify", json={"name": "Kid test", "pin": "1111"})
    assert response.status_code == 200
    assert response.json()["name"] == "Kid test"

    # Incorrect PIN
    response = client.post("/api/verify", json={"name": "Kid test", "pin": "9999"})
    assert response.status_code == 401

# ----------------- CONSTRAINT VALIDATION & TIME TRAVEL TESTS -----------------

@freeze_time("2026-06-25 10:00:00") # Thursday morning (10:00 AM Central/UTC mapping depending on TZ setting)
def test_after_four_pm_chores_hidden_before_four(client):
    """
    Time Travel Check: Chores marked as 'after_four_pm' must be completely hidden 
    from the dashboard if logged in before 4:00 PM.
    """
    response = client.post("/api/verify-ui", data={"name": "Kid test", "pin": "1111"})
    assert response.status_code == 200
    assert "Evening Dishwasher" not in response.text

@freeze_time("2026-06-25 23:00:00") # Thursday evening (6:00 PM Central Time)
def test_after_four_pm_chores_visible_after_four(client):
    """
    Time Travel Check: Chores marked as 'after_four_pm' must become visible 
    on the dashboard after 4:00 PM.
    """
    # Daily and weekly required chores must be completed first or we won't load the normal dashboard/optional list.
    # In run_around_tests fixture, User 2 has chore 2 (Make Bed) and chore 3 (Clean Room) as required chores.
    # On a weekday (2026-06-25 is Thursday), weekly required chores do not block, but daily required chores (Chore 2) DO block!
    # Let's complete the daily required chore (Chore 2) first.
    res_daily = client.post(
        "/api/chores/complete-ui",
        data={"chore_id": 2, "user_id": 2},
        headers={"HX-Prompt": "1111"}
    )
    assert res_daily.status_code == 200

    response = client.post("/api/verify-ui", data={"name": "Kid test", "pin": "1111"})
    assert response.status_code == 200
    # Search for title or chore ID matching Evening Dishwasher
    assert "Evening Dishwasher" in response.text

@freeze_time("2026-06-25 10:00:00") # Thursday (Weekday)
def test_weekly_required_chores_do_not_block_on_weekdays(client):
    """
    Time Travel Check: Required weekly chores must NOT lock the user's dashboard 
    on weekdays. They should be allowed to complete optional daily chores (after completing daily required ones).
    """
    # 1. Kid test completes the daily required chore (Make Bed = Chore 2) first
    res_daily = client.post(
        "/api/chores/complete-ui",
        data={"chore_id": 2, "user_id": 2},
        headers={"HX-Prompt": "1111"}
    )
    assert res_daily.status_code == 200
    
    # 2. Try to complete optional daily chore (Feed Pets = Chore 1). This should work because weekly chore (Clean Room) doesn't block on weekdays.
    response = client.post(
        "/api/chores/complete-ui",
        data={"chore_id": 1, "user_id": 2},
        headers={"HX-Prompt": "1111"}
    )
    assert response.status_code == 200
    # Check that it did NOT trigger the validation blocker (which returns a dashboard snippet with "Complete required chores first")
    assert "Complete required chores first" not in response.text

@freeze_time("2026-06-28 10:00:00") # Sunday (Weekend)
def test_weekly_required_chores_block_on_weekends(client):
    """
    Time Travel Check: Required weekly chores MUST block daily/optional chores 
    on weekends if not completed (even after daily required ones are completed).
    """
    # 1. Kid test completes the daily required chore (Make Bed = Chore 2)
    res_daily = client.post(
        "/api/chores/complete-ui",
        data={"chore_id": 2, "user_id": 2},
        headers={"HX-Prompt": "1111"}
    )
    assert res_daily.status_code == 200
    
    # 2. Kid test tries to complete daily optional chore (Feed Pets = Chore 1) on a Sunday. 
    # Because required weekly chore (Clean Room) is still uncompleted, it should fail and return error.
    response = client.post(
        "/api/chores/complete-ui",
        data={"chore_id": 1, "user_id": 2},
        headers={"HX-Prompt": "1111"}
    )
    assert response.status_code == 200
    assert "Complete required chores first: Clean Room (Weekly)!" in response.text

# ----------------- ADMIN PORTAL TESTS -----------------

def test_admin_inline_rename_user(client):
    """Verifies that parent profiles can rename other profile names from the admin console."""
    # Inline rename Kid test (User 2) to 'Sydney'
    response = client.post(
        "/api/admin/users/rename/2",
        data={"name": "Sydney"}
    )
    assert response.status_code == 200
    assert "Renamed profile" in response.text
    assert "Sydney" in response.text
    
    # Confirm name changed in database
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM users WHERE id = 2")
        assert cursor.fetchone()["name"] == "Sydney"
