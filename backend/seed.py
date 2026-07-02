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

# Family members and their 4-digit PINs (Fallback defaults)
FAMILY_MEMBERS = [
    {"name": "Parent 1", "pin": "1234", "is_parent": 1},
    {"name": "Parent 2", "pin": "5678", "is_parent": 1},
    {"name": "Child 1", "pin": "1111", "is_parent": 0},
    {"name": "Child 2", "pin": "2222", "is_parent": 0},
    {"name": "Child 3", "pin": "3333", "is_parent": 0},
]

# Enhanced Chore List with scaled points (100-point baseline)
DEFAULT_CHORES = [
    # Kitchen & Meals
    {"title": "Clear Your Meal Place", "desc": "Bring all your dishes to the sink and rinse them.", "cat": "Kitchen", "freq": "daily", "val": 25, "max_comp": 1},
    {"title": "Wipe Dining Table", "desc": "Clear crumbs and wipe the table surface clean.", "cat": "Kitchen", "freq": "daily", "val": 25, "max_comp": 1},
    {"title": "Clean Under Chair", "desc": "Ensure no food or mess is left on the floor after eating.", "cat": "Kitchen", "freq": "daily", "val": 25, "max_comp": 1},
    {"title": "Unload dishwasher+clear drying rack", "desc": "Empty the dishwasher and clear the drying rack.", "cat": "Kitchen", "freq": "daily", "val": 50, "max_comp": 1},
    {"title": "Evening Kitchen Reset", "desc": "Empty dishwasher/drying rack to prep for dinner.", "cat": "Kitchen", "freq": "daily", "val": 50, "max_comp": 1},
    {"title": "Clean Kitchen Island", "desc": "Remove clutter and wipe down the island surface.", "cat": "Kitchen", "freq": "daily", "val": 30, "max_comp": 1},
    {"title": "Chef Duty: Dinner", "desc": "Prepare and serve the family meal.", "cat": "Kitchen", "freq": "daily", "val": 100, "max_comp": 1},
    {"title": "Load Dishwasher", "desc": "Load all dirty dishes and start the wash cycle.", "cat": "Kitchen", "freq": "daily", "val": 50, "max_comp": 1},
    {"title": "Hand Wash Dishes", "desc": "Wash items that can't go in the dishwasher.", "cat": "Kitchen", "freq": "daily", "val": 80, "max_comp": 1},
    {"title": "Wipe Main Counters", "desc": "Clear all items and sanitize kitchen countertops.", "cat": "Kitchen", "freq": "daily", "val": 40, "max_comp": 1},
    {"title": "Store Leftovers", "desc": "Pack food into containers and place in the fridge.", "cat": "Kitchen", "freq": "daily", "val": 20, "max_comp": 1},
    
    # Cleaning & Tidy
    {"title": "Break Down Boxes", "desc": "Flatten cardboard boxes for recycling.", "cat": "Cleaning", "freq": "adhoc", "val": 50},
    {"title": "Trash & Recycling", "desc": "Empty bins and take bags to the outside cans.", "cat": "Cleaning", "freq": "daily", "val": 50},
    {"title": "Basement Big Room Tidy", "desc": "Organize toys and clear the main basement area.", "cat": "Cleaning", "freq": "daily", "val": 80},
    {"title": "Tidy Fireplace Area", "desc": "Straighten pillows and clear the hearth.", "cat": "Cleaning", "freq": "daily", "val": 30},
    {"title": "Tidy Great Room", "desc": "Fix couch cushions and clear the floor space.", "cat": "Cleaning", "freq": "daily", "val": 50},
    {"title": "Tidy Office/Studio", "desc": "Organize desk surface and clear the floor.", "cat": "Cleaning", "freq": "daily", "val": 50},
    {"title": "Tidy Entryway/Foyer", "desc": "Organize shoes and clear items off the bench.", "cat": "Cleaning", "freq": "daily", "val": 40},
    {"title": "Vacuum the Stairs", "desc": "Full vacuum of all stairs and landings.", "cat": "Cleaning", "freq": "weekly", "val": 200},
    {"title": "Hall Bath Deep Clean", "desc": "Sanitize mirror, toilet, and sink area.", "cat": "Cleaning", "freq": "weekly", "val": 250},
    {"title": "Basement Bath Deep Clean", "desc": "Sanitize mirror, toilet, sink, and floor.", "cat": "Cleaning", "freq": "weekly", "val": 300},
    {"title": "Master Bath Deep Clean", "desc": "Sanitize mirror, toilet, and sink area.", "cat": "Cleaning", "freq": "weekly", "val": 250},
    {"title": "Scrub Master Shower", "desc": "Deep clean of shower walls and floor.", "cat": "Cleaning", "freq": "weekly", "val": 400},
    {"title": "Scrub Hall Shower", "desc": "Deep clean of shower walls and floor.", "cat": "Cleaning", "freq": "weekly", "val": 400},

    # Laundry & Organization
    {"title": "Distribute Laundry", "desc": "Sort clean clothes and place on the correct beds.", "cat": "Organization", "freq": "daily", "val": 50},
    {"title": "Start Laundry Cycle", "desc": "Move a load through the washer and dryer.", "cat": "Organization", "freq": "daily", "val": 30},
    {"title": "Unpack Backpack", "desc": "Sort papers, put lunch items away, and hang it up.", "cat": "Organization", "freq": "daily", "val": 30},
    {"title": "Mail Management", "desc": "Sort, open, and scan relevant documents.", "cat": "Organization", "freq": "daily", "val": 50},
    
    # Yardwork
    {"title": "Yard Cleanup", "desc": "Pull weeds and cleanup debris outside.", "cat": "Yard", "freq": "adhoc", "val": 100},
    {"title": "Mow Lawn", "desc": "Mow the yard to the specified height.", "cat": "Yard", "freq": "weekly", "val": 300},
    {"title": "Trim Edges", "desc": "Trim along fences, beds, and walks.", "cat": "Yard", "freq": "weekly", "val": 200},

    # Personal Care (Often Assigned)
    {"title": "Make Your Bed", "desc": "Tidy sheets, fluff pillows, and straighten the comforter.", "cat": "Personal", "freq": "daily", "val": 20, "is_required": 1, "is_shared": 1},
    {"title": "Tidy Your Bedroom", "desc": "Pickup toys/clothes and clear the floor surfaces.", "cat": "Personal", "freq": "daily", "val": 50},
    {"title": "Personal Care: Shower", "desc": "Complete your daily shower.", "cat": "Personal", "freq": "daily", "val": 20},
]

# Rewards Store Menu
DEFAULT_REWARDS = [
    # Tier 1: Screen Time & Network
    {"title": "30 Mins Xbox/PC", "desc": "30 minutes of gaming time on Xbox or PC.", "cost": 50.0, "tier": 1},
    {"title": "60 Mins Unrestricted Phone", "desc": "60 minutes of unrestricted phone usage.", "cost": 100.0, "tier": 1},
    {"title": "'Lag-Free' Priority Pass", "desc": "Temporary high-priority network allocation.", "cost": 150.0, "tier": 1},
    {"title": "Plume Network Profile Boost (1 Hour)", "desc": "Boost internet priority for 1 hour.", "cost": 150.0, "tier": 1},
    
    # Tier 2: Privileges & Passes
    {"title": "Pick Family Movie Night", "desc": "Choose the movie for the next family movie night.", "cost": 150.0, "tier": 2},
    {"title": "Pick Family Dessert", "desc": "Choose the dessert for a family meal.", "cost": 100.0, "tier": 2},
    {"title": "Pick Family Dinner Menu", "desc": "Select the menu for a family dinner.", "cost": 300.0, "tier": 2},
    {"title": "'Get Out of Jail Free' Chore Pass", "desc": "Allows skipping a task and routing it to a sibling or bounty pool.", "cost": 500.0, "tier": 2},
    
    # Tier 3: Quality Time & Outings
    {"title": "'QT Cone' Ice Cream Run with Mom/Dad", "desc": "One-on-one ice cream run with Mom or Dad.", "cost": 400.0, "tier": 3},
    {"title": "Late-Night Passenger", "desc": "Stay up 1 hour late on weekend.", "cost": 250.0, "tier": 3},
    {"title": "Chesterfield Valley Excursion", "desc": "2-hour weekend outing of your choice.", "cost": 800.0, "tier": 3},
]

def seed_database():
    """Seeds the database with users, chores, and rewards."""
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

            # Seed Rewards
            for reward in DEFAULT_REWARDS:
                cursor.execute(
                    """
                    INSERT INTO rewards (title, description, cost_points, tier)
                    VALUES (?, ?, ?, ?)
                    """,
                    (reward["title"], reward["desc"], reward["cost"], reward["tier"])
                )
                logger.info(f"Seeded reward: {reward['title']}")

            conn.commit()
            logger.info("Database seeding completed successfully with chores and rewards.")
            
    except Exception as e:
        logger.error(f"Error seeding database: {e}")
        raise

if __name__ == "__main__":
    seed_database()
