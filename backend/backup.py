import sqlite3
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def run_backup(db_path: str, backup_dir: str, max_backups: int = 30) -> bool:
    """
    Safely backs up the SQLite database at db_path to the backup_dir using SQLite's backup API.
    Retains up to max_backups files, deleting the oldest.
    """
    if not os.path.exists(db_path):
        logger.error(f"Database file not found at '{db_path}'. Cannot perform backup.")
        return False

    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"hearth_backup_{timestamp}.db"
    backup_path = os.path.join(backup_dir, backup_file)
    
    logger.info(f"Initiating SQLite backup: '{db_path}' -> '{backup_path}'")
    try:
        # SQLite's backup API executes safely even while the database is being written to.
        src = sqlite3.connect(db_path)
        dst = sqlite3.connect(backup_path)
        with dst:
            src.backup(dst)
        dst.close()
        src.close()
        logger.info(f"Database backup successfully created: '{backup_file}'")
        
        # Prune old backups
        files = sorted(
            [os.path.join(backup_dir, f) for f in os.listdir(backup_dir) if f.startswith("hearth_backup_") and f.endswith(".db")],
            key=os.path.getmtime
        )
        while len(files) > max_backups:
            oldest = files.pop(0)
            try:
                os.remove(oldest)
                logger.info(f"Pruned oldest backup file: '{oldest}'")
            except Exception as e:
                logger.error(f"Failed to delete old backup file '{oldest}': {e}")
                
        return True
    except Exception as e:
        logger.error(f"SQLite backup failed: {e}")
        return False
