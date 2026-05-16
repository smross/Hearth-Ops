import sqlite3
import hashlib
import os
import logging
from database import get_db_connection, init_db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def hash_pin(pin: str) -> str:
    """
    Hashes a 4-digit PIN using SHA-256. 
    In a production system with PII, use bcrypt/argon2, 
    but for a local PIN economy, SHA-256 is efficient.
    """
    return hashlib.sha256(pin.encode()).hexdigest()

# Family members and their 4-digit PINs
FAMILY_MEMBERS = [
    {"name": "Parent 1", "pin": "3157"},
    {"name": "Parent 2", "pin": "0919"},
    {"name": "Child 3", "pin": "0129"},
    {"name": "Child 1", "pin": "1019"},
    {"name": "Child 2", "pin": "0404"},
    {"name": "Child 4", "pin": "0924"},
]

def seed_database():
    """
    Seeds the database with initial family user profiles.
    """
    # Ensure DB and Schema exist first
    init_db()

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            for member in FAMILY_MEMBERS:
                name = member["name"]
                pin_hash = hash_pin(member["pin"])
                
                # Use INSERT OR IGNORE to avoid duplicates if script is run multiple times
                cursor.execute(
                    "INSERT OR IGNORE INTO users (name, pin_hash) VALUES (?, ?)",
                    (name, pin_hash)
                )
                if cursor.rowcount > 0:
                    logger.info(f"Seeded user: {name}")
                else:
                    logger.info(f"User {name} already exists, skipping.")
            
            conn.commit()
            logger.info("Database seeding completed successfully.")
            
    except Exception as e:
        logger.error(f"Error seeding database: {e}")
        raise

if __name__ == "__main__":
    seed_database()
