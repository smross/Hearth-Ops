-- HearthOps Core SQLite Schema Definition

PRAGMA foreign_keys = ON;

-- 1. Users Table (Family Profiles)
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    pin_hash TEXT NOT NULL,
    token_balance REAL DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Chores Table (Definitions & Assignments)
CREATE TABLE IF NOT EXISTS chores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    assigned_user_id INTEGER,
    value_credits REAL NOT NULL DEFAULT 0.0,
    is_active INTEGER DEFAULT 1, -- 1=True, 0=False
    FOREIGN KEY (assigned_user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- 3. Chore Logs Table (Immutable Audit Ledger)
CREATE TABLE IF NOT EXISTS chore_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chore_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chore_id) REFERENCES chores(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Indexes for performance tuning and fast UI loads
CREATE INDEX IF NOT EXISTS idx_users_name ON users(name);
CREATE INDEX IF NOT EXISTS idx_chores_assigned ON chores(assigned_user_id);
CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON chore_logs(completed_at);
