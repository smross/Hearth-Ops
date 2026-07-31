import sqlite3
import os
import sys
import logging

# Ensure backend folder is in path if run from elsewhere
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import DB_PATH, init_db, get_db_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_database(db_path: str = None):
    """
    Safely migrates a HearthOps database from the old 1x float scale
    to the new 10x integer scale, implementing the 50/30/20 three-jar split.
    """
    active_db = db_path if db_path else DB_PATH
    logger.info(f"Starting economy migration on database: {active_db}")

    if not os.path.exists(active_db):
        logger.error(f"Database file not found at {active_db}. Cannot migrate.")
        return False

    # 1. Initialize schema updates (adds save_balance, give_balance, target_jar, etc.)
    # We temporarily set the global database path to active_db for initialization
    import database
    original_db_path = database.DB_PATH
    database.set_db_path(active_db)
    try:
        init_db()
    finally:
        database.set_db_path(original_db_path)

    # 2. Check if already migrated
    conn = sqlite3.connect(active_db)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Create metadata table if not exists
        cursor.execute("CREATE TABLE IF NOT EXISTS sys_metadata (key TEXT PRIMARY KEY, value TEXT);")
        conn.commit()

        cursor.execute("SELECT value FROM sys_metadata WHERE key = 'economy_scaled_10x'")
        row = cursor.fetchone()
        if row and row['value'] == 'true':
            logger.info("Database is already migrated to 10x integer scale. Skipping.")
            conn.close()
            return True

        # Perform backup within SQLite
        backup_path = active_db + ".pre-migration-backup"
        logger.info(f"Creating a safety backup of the database at: {backup_path}")
        backup_conn = sqlite3.connect(backup_path)
        with backup_conn:
            conn.backup(backup_conn)
        backup_conn.close()

        logger.info("Beginning transaction for 10x economy scaling...")
        
        # A. Scale users table and apply 50/30/20 split to kids' balances
        cursor.execute("SELECT id, name, token_balance, is_parent FROM users")
        users = cursor.fetchall()
        for user in users:
            user_id = user['id']
            old_balance = user['token_balance'] or 0.0
            new_total = int(round(old_balance * 10))

            if user['is_parent'] == 0:
                # Apply 50/30/20 split for kids
                give_val = int(round(new_total * 0.20))
                save_val = int(round(new_total * 0.30))
                spend_val = new_total - give_val - save_val
                
                cursor.execute(
                    "UPDATE users SET token_balance = ?, save_balance = ?, give_balance = ? WHERE id = ?",
                    (float(spend_val), float(save_val), float(give_val), user_id)
                )
                logger.info(f"Migrated kid {user['name']}: {old_balance} -> Spend: {spend_val}, Save: {save_val}, Give: {give_val} (Total: {new_total})")
            else:
                # Parents keep all points in spend/token balance scaled by 10
                cursor.execute(
                    "UPDATE users SET token_balance = ?, save_balance = 0.0, give_balance = 0.0 WHERE id = ?",
                    (float(new_total), user_id)
                )
                logger.info(f"Migrated parent {user['name']}: {old_balance} -> {new_total}")

        # B. Scale chores table (value_credits)
        cursor.execute("SELECT id, title, value_credits FROM chores")
        chores = cursor.fetchall()
        for chore in chores:
            old_val = chore['value_credits'] or 0.0
            new_val = int(round(old_val * 10))
            cursor.execute("UPDATE chores SET value_credits = ? WHERE id = ?", (float(new_val), chore['id']))
            logger.info(f"Scaled chore '{chore['title']}': {old_val} -> {new_val}")

        # C. Scale chore_logs table (credits_delta)
        cursor.execute("SELECT id, credits_delta FROM chore_logs")
        logs = cursor.fetchall()
        for log in logs:
            old_delta = log['credits_delta'] or 0.0
            new_delta = int(round(old_delta * 10))
            cursor.execute("UPDATE chore_logs SET credits_delta = ? WHERE id = ?", (float(new_delta), log['id']))
        logger.info(f"Scaled {len(logs)} chore logs.")

        # D. Scale token_transactions table (amount)
        cursor.execute("SELECT id, amount FROM token_transactions")
        txs = cursor.fetchall()
        for tx in txs:
            old_amount = tx['amount'] or 0.0
            new_amount = int(round(old_amount * 10))
            cursor.execute("UPDATE token_transactions SET amount = ? WHERE id = ?", (float(new_amount), tx['id']))
        logger.info(f"Scaled {len(txs)} token transactions.")

        # E. Scale rewards table (cost_points)
        cursor.execute("SELECT id, title, cost_points FROM rewards")
        rewards = cursor.fetchall()
        for reward in rewards:
            old_cost = reward['cost_points'] or 0.0
            new_cost = int(round(old_cost * 10))
            cursor.execute("UPDATE rewards SET cost_points = ? WHERE id = ?", (float(new_cost), reward['id']))
            logger.info(f"Scaled reward '{reward['title']}': {old_cost} -> {new_cost}")

        # F. Scale payout_requests (if any exist)
        try:
            cursor.execute("SELECT id, amount_tokens FROM payout_requests")
            payouts = cursor.fetchall()
            for payout in payouts:
                old_p = payout['amount_tokens'] or 0.0
                new_p = int(round(old_p * 10))
                cursor.execute("UPDATE payout_requests SET amount_tokens = ? WHERE id = ?", (float(new_p), payout['id']))
            logger.info(f"Scaled {len(payouts)} payout requests.")
        except Exception:
            # Table might not contain rows or table checks are clean
            pass

        # Write migration completion marker
        cursor.execute("INSERT OR REPLACE INTO sys_metadata (key, value) VALUES ('economy_scaled_10x', 'true')")
        
        conn.commit()
        logger.info("Economy migration completed and committed successfully!")
        return True

    except Exception as e:
        conn.rollback()
        logger.error(f"Error during database economy migration: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else None
    success = migrate_database(db)
    sys.exit(0 if success else 1)
