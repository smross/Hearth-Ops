import sqlite3
import os
import logging
from contextlib import contextmanager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////app/data/hearth.db")
# Extract the file path from the sqlite://// format
DB_PATH = DATABASE_URL.replace("sqlite:///", "")

def set_db_path(new_path: str):
    """Overrides the active DB path, useful for sandboxed database testing."""
    global DB_PATH
    DB_PATH = new_path

def init_db():
    """
    Initializes the database if it doesn't exist by running the schema.sql script.
    Always runs CREATE TABLE IF NOT EXISTS statements to ensure new schema tables are created.
    """
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
        logger.info(f"Created database directory: {db_dir}")

    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    if os.path.exists(schema_path):
        logger.info(f"Ensuring schema tables are up to date using schema.sql on {DB_PATH}...")
        try:
            with sqlite3.connect(DB_PATH) as conn:
                with open(schema_path, "r") as f:
                    conn.executescript(f.read())
                
                # Check and dynamically add admin_note if missing from existing databases
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(chore_logs)")
                columns = [row[1] for row in cursor.fetchall()]
                if 'admin_note' not in columns:
                    cursor.execute("ALTER TABLE chore_logs ADD COLUMN admin_note TEXT;")
                    conn.commit()
                    logger.info("Migrated chore_logs: Added admin_note column successfully.")

                # Check and dynamically add after_four_pm if missing from chores table
                cursor.execute("PRAGMA table_info(chores)")
                chore_columns = [row[1] for row in cursor.fetchall()]
                if 'after_four_pm' not in chore_columns:
                    cursor.execute("ALTER TABLE chores ADD COLUMN after_four_pm INTEGER DEFAULT 0;")
                    conn.commit()
                    logger.info("Migrated chores: Added after_four_pm column successfully.")
            logger.info("Database schema check/initialization and migrations completed successfully.")
        except Exception as e:
            logger.error(f"Failed to check/initialize database schema: {e}")
            raise
    else:
        logger.error(f"Schema file not found at {schema_path}")

@contextmanager
def get_db_connection():
    """
    Context manager for safely handling SQLite database connections.
    Ensures foreign keys are enabled for every connection.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Enable name-based access to columns
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        yield conn
    finally:
        conn.close()

if __name__ == "__main__":
    # Allow running the script directly to initialize the DB
    init_db()
