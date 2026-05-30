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
    {"name": "Parent 1", "pin": "1234", "is_parent": 1},
    {"name": "Parent 2", "pin": "5678", "is_parent": 1},
    {"name": "Child 1", "pin": "1111", "is_parent": 0},
    {"name": "Child 2", "pin": "2222", "is_parent": 0},
    {"name": "Child 3", "pin": "3333", "is_parent": 0},
]

# Enhanced Chore List
DEFAULT_CHORES = [
    # Kitchen & Meals
    {"title": "Clear Your Meal Place", "desc": "Bring all your dishes to the sink and rinse them.", "cat": "Kitchen", "freq": "daily", "val": 2, "max_comp": 1},
    {"title": "Wipe Dining Table", "desc": "Clear crumbs and wipe the table surface clean.", "cat": "Kitchen", "freq": "daily", "val": 2, "max_comp": 1},
    {"title": "Clean Under Chair", "desc": "Ensure no food or mess is left on the floor after eating.", "cat": "Kitchen", "freq": "daily", "val": 2, "max_comp": 1},
    {"title": "Unload dishwasher+clear drying rack", "desc": "Empty the dishwasher and clear the drying rack.", "cat": "Kitchen", "freq": "daily", "val": 5, "max_comp": 1},
    {"title": "Evening Kitchen Reset", "desc": "Empty dishwasher/drying rack to prep for dinner.", "cat": "Kitchen", "freq": "daily", "val": 5, "max_comp": 1},
    {"title": "Clean Kitchen Island", "desc": "Remove clutter and wipe down the island surface.", "cat": "Kitchen", "freq": "daily", "val": 3, "max_comp": 1},
    {"title": "Chef Duty: Dinner", "desc": "Prepare and serve the family meal.", "cat": "Kitchen", "freq": "daily", "val": 10, "max_comp": 1},
    {"title": "Load Dishwasher", "desc": "Load all dirty dishes and start the wash cycle.", "cat": "Kitchen", "freq": "daily", "val": 5, "max_comp": 1},
    {"title": "Hand Wash Dishes", "desc": "Wash items that can't go in the dishwasher.", "cat": "Kitchen", "freq": "daily", "val": 8, "max_comp": 1},
    {"title": "Wipe Main Counters", "desc": "Clear all items and sanitize kitchen countertops.", "cat": "Kitchen", "freq": "daily", "val": 4, "max_comp": 1},
    {"title": "Store Leftovers", "desc": "Pack food into containers and place in the fridge.", "cat": "Kitchen", "freq": "daily", "val": 2, "max_comp": 1},
    
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
    {"title": "Mow Lawn", "desc": "Mow the yard to the specified height.", "cat": "Yard", "freq": "weekly", "val": 8},
    {"title": "Trim Edges", "desc": "Trim along fences, beds, and walks.", "cat": "Yard", "freq": "weekly", "val": 7},

    # Personal Care (Often Assigned)
    {"title": "Make Your Bed", "desc": "Tidy sheets, fluff pillows, and straighten the comforter.", "cat": "Personal", "freq": "daily", "val": 2, "is_required": 1, "is_shared": 1},
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

    # Load family members list (supports local anonymized config override)
    import json
    family_members = FAMILY_MEMBERS
    config_paths = [
        "family_members.json",
        os.path.join(os.path.dirname(__file__), "family_members.json"),
        "/app/family_members.json",
        "/app/backend/family_members.json"
    ]
    for path in config_paths:
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    family_members = json.load(f)
                logger.info(f"Loaded custom family members configuration from {path}")
                break
            except Exception as e:
                logger.error(f"Error loading custom configuration {path}: {e}")

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Seed Users
            for member in family_members:
                cursor.execute(
                    "INSERT INTO users (name, pin_hash, is_parent) VALUES (?, ?, ?)",
                    (member["name"], hash_pin(member["pin"]), member["is_parent"])
                )
                logger.info(f"Seeded user: {member['name']}")
            
            # Seed Chores
            for chore in DEFAULT_CHORES:
                # Default max_daily_completions to 999 for adhoc, or 1 for daily/weekly, or 3 for meal (if any exist)
                max_comp = chore.get("max_comp")
                if max_comp is None:
                    if chore["freq"] == "adhoc":
                        max_comp = 999
                    elif chore["freq"] == "meal":
                        max_comp = 3
                    else:
                        max_comp = 1
                
                is_req = chore.get("is_required", 0)
                is_sh = chore.get("is_shared", 0)
                        
                cursor.execute(
                    """
                    INSERT INTO chores (title, description, category, frequency, value_credits, max_daily_completions, is_required, is_shared) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (chore["title"], chore["desc"], chore["cat"], chore["freq"], chore["val"], max_comp, is_req, is_sh)
                )
                logger.info(f"Seeded chore: {chore['title']}")

            conn.commit()
            logger.info("Database seeding completed successfully with 30+ chores.")
            
    except Exception as e:
        logger.error(f"Error seeding database: {e}")
        raise

if __name__ == "__main__":
    seed_database()
