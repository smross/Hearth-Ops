import sqlite3
import hashlib
import os
import logging
from database import get_db_connection, init_db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def hash_pin(pin: str) -> str:
    """Hashes a 4-digit PIN using SHA-256."""
    return hashlib.sha256(pin.encode()).hexdigest()

# Family members and their 4-digit PINs
FAMILY_MEMBERS = [
    {"name": "Shawn", "pin": "3157"},
    {"name": "Michelle", "pin": "9019"},
    {"name": "Sydney", "pin": "0129"},
    {"name": "Henry", "pin": "1019"},
    {"name": "Dorothy", "pin": "0404"},
    {"name": "Levi", "pin": "0924"},
]

# Enhanced Chore List
DEFAULT_CHORES = [
    # Kitchen & Meals
    {"title": "Clear Your Meal Place", "desc": "Bring all your dishes to the sink and rinse them.", "cat": "Kitchen", "freq": "daily", "val": 2},
    {"title": "Wipe Dining Table", "desc": "Clear crumbs and wipe the table surface clean.", "cat": "Kitchen", "freq": "daily", "val": 2},
    {"title": "Clean Under Chair", "desc": "Ensure no food or mess is left on the floor after eating.", "cat": "Kitchen", "freq": "daily", "val": 2},
    {"title": "Morning Kitchen Reset", "desc": "Empty the dishwasher and clear the drying rack.", "cat": "Kitchen", "freq": "daily", "val": 5},
    {"title": "Evening Kitchen Reset", "desc": "Empty dishwasher/drying rack to prep for dinner.", "cat": "Kitchen", "freq": "daily", "val": 5},
    {"title": "Clean Kitchen Island", "desc": "Remove clutter and wipe down the island surface.", "cat": "Kitchen", "freq": "daily", "val": 3},
    {"title": "Chef Duty: Dinner", "desc": "Prepare and serve the family meal.", "cat": "Kitchen", "freq": "daily", "val": 10},
    {"title": "Load Dishwasher", "desc": "Load all dirty dishes and start the wash cycle.", "cat": "Kitchen", "freq": "daily", "val": 5},
    {"title": "Hand Wash Dishes", "desc": "Wash items that can't go in the dishwasher.", "cat": "Kitchen", "freq": "daily", "val": 8},
    {"title": "Wipe Main Counters", "desc": "Clear all items and sanitize kitchen countertops.", "cat": "Kitchen", "freq": "daily", "val": 4},
    {"title": "Store Leftovers", "desc": "Pack food into containers and place in the fridge.", "cat": "Kitchen", "freq": "daily", "val": 2},
    
    # Cleaning & Tidy
    {"title": "Break Down Boxes", "desc": "Flatten cardboard boxes for recycling.", "cat": "Cleaning", "freq": "adhoc", "val": 5},
    {"title": "Trash & Recycling", "desc": "Empty bins and take bags to the outside cans.", "cat": "Cleaning", "freq": "daily", "val": 5},
    {"title": "Basement Big Room Tidy", "desc": "Organize toys and clear the main basement area.", "cat": "Cleaning", "freq": "daily", "val": 8},
    {"title": "Tidy Fireplace Area", "desc": "Straighten pillows and clear the hearth.", "cat": "Cleaning", "freq": "daily", "val": 3},
    {"title": "Tidy Great Room", "desc": "Fix couch cushions and clear the floor space.", "cat": "Cleaning", "freq": "daily", "val": 5},
    {"title": "Tidy Office/Studio", "desc": "Organize desk surface and clear the floor.", "cat": "Cleaning", "freq": "daily", "val": 5},
    {"title": "Tidy Entryway/Foyer", "desc": "Organize shoes and clear items off the bench.", "cat": "Cleaning", "freq": "daily", "val": 4},
    {"title": "Vacuum the Stairs", "desc": "Full vacuum of all stairs and landings.", "cat": "Cleaning", "freq": "weekly", "val": 6},
    {"title": "Hall Bath Deep Clean", "desc": "Sanitize mirror, toilet, and sink area.", "cat": "Cleaning", "freq": "weekly", "val": 7},
    {"title": "Basement Bath Deep Clean", "desc": "Sanitize mirror, toilet, sink, and floor.", "cat": "Cleaning", "freq": "weekly", "val": 10},
    {"title": "Master Bath Deep Clean", "desc": "Sanitize mirror, toilet, and sink area.", "cat": "Cleaning", "freq": "weekly", "val": 7},
    {"title": "Scrub Master Shower", "desc": "Deep clean of shower walls and floor.", "cat": "Cleaning", "freq": "weekly", "val": 10},
    {"title": "Scrub Hall Shower", "desc": "Deep clean of shower walls and floor.", "cat": "Cleaning", "freq": "weekly", "val": 10},

    # Laundry & Organization
    {"title": "Distribute Laundry", "desc": "Sort clean clothes and place on the correct beds.", "cat": "Organization", "freq": "daily", "val": 5},
    {"title": "Start Laundry Cycle", "desc": "Move a load through the washer and dryer.", "cat": "Organization", "freq": "daily", "val": 3},
    {"title": "Unpack Backpack", "desc": "Sort papers, put lunch items away, and hang it up.", "cat": "Organization", "freq": "daily", "val": 3},
    {"title": "Mail Management", "desc": "Sort, open, and scan relevant documents.", "cat": "Organization", "freq": "daily", "val": 5},
    
    # Yardwork
    {"title": "Yard Cleanup", "desc": "Pull weeds and cleanup debris outside.", "cat": "Yard", "freq": "adhoc", "val": 10},
    {"title": "Lawn Maintenance", "desc": "Full mow and trim of the yard.", "cat": "Yard", "freq": "weekly", "val": 15},

    # Personal Care (Often Assigned)
    {"title": "Make Your Bed", "desc": "Tidy sheets, fluff pillows, and straighten the comforter.", "cat": "Personal", "freq": "daily", "val": 2},
    {"title": "Tidy Your Bedroom", "desc": "Pickup toys/clothes and clear the floor surfaces.", "cat": "Personal", "freq": "daily", "val": 5},
    {"title": "Personal Care: Shower", "desc": "Complete your daily shower.", "cat": "Personal", "freq": "daily", "val": 2},
]

def seed_database():
    """Seeds the database with users and the expanded chore list."""
    # Force schema update by deleting old db if needed, or just relying on init_db
    # Since we added columns, it's safer to re-initialize for this transition
    from database import DB_PATH
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        logger.info(f"Removed old database at {DB_PATH} for schema update.")
    
    init_db()

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Seed Users
            for member in FAMILY_MEMBERS:
                cursor.execute(
                    "INSERT INTO users (name, pin_hash) VALUES (?, ?)",
                    (member["name"], hash_pin(member["pin"]))
                )
                logger.info(f"Seeded user: {member['name']}")
            
            # Seed Chores
            for chore in DEFAULT_CHORES:
                cursor.execute(
                    """
                    INSERT INTO chores (title, description, category, frequency, value_credits) 
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (chore["title"], chore["desc"], chore["cat"], chore["freq"], chore["val"])
                )
                logger.info(f"Seeded chore: {chore['title']}")

            conn.commit()
            logger.info("Database seeding completed successfully with 30+ chores.")
            
    except Exception as e:
        logger.error(f"Error seeding database: {e}")
        raise

if __name__ == "__main__":
    seed_database()
