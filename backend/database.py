import sqlite3
import os
import logging
from contextlib import contextmanager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////app/data/hearth.db")
# Extract the file path from the sqlite://// format
DB_PATH = DATABASE_URL.replace("sqlite:///", "")

def init_db():
    """
    Initializes the database if it doesn't exist by running the schema.sql script.
    """
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
        logger.info(f"Created database directory: {db_dir}")

    if not os.path.exists(DB_PATH):
        logger.info(f"Database not found at {DB_PATH}. Initializing with schema.sql...")
        schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
        
        try:
            with sqlite3.connect(DB_PATH) as conn:
                with open(schema_path, "r") as f:
                    conn.executescript(f.read())
            logger.info("Database successfully initialized with schema.sql.")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    else:
        logger.info(f"Database found at {DB_PATH}. Skipping initialization.")

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
