-- HearthOps Core SQLite Schema Definition

PRAGMA foreign_keys = ON;

-- 1. Users Table (Family Profiles)
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    pin_hash TEXT NOT NULL,
    token_balance REAL DEFAULT 0.0,
    is_parent INTEGER DEFAULT 0, -- 1=Parent, 0=Child
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Chores Table (Definitions & Assignments)
CREATE TABLE IF NOT EXISTS chores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    category TEXT DEFAULT 'General', -- e.g., 'Kitchen', 'Bedroom', 'Yard', 'Personal'
    frequency TEXT DEFAULT 'daily', -- 'daily', 'weekly', 'adhoc'
    assigned_user_id INTEGER,
    value_credits REAL NOT NULL DEFAULT 0.0,
    max_daily_completions INTEGER DEFAULT 1, -- 1 = default daily limit, adhoc/unlimited = large/999
    is_active INTEGER DEFAULT 1, -- 1=True, 0=False
    is_required INTEGER DEFAULT 0, -- 1=Required, 0=Optional
    is_shared INTEGER DEFAULT 0, -- 1=Shared/Public, 0=Assigned
    after_four_pm INTEGER DEFAULT 0, -- 1=Only available after 4:00 PM local time, 0=No time restriction
    FOREIGN KEY (assigned_user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- 3. Chore Logs Table (Immutable Audit Ledger)
CREATE TABLE IF NOT EXISTS chore_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chore_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    action_type TEXT DEFAULT 'earn', -- 'earn', 'undo'
    credits_delta REAL NOT NULL DEFAULT 0.0,
    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    admin_note TEXT,
    FOREIGN KEY (chore_id) REFERENCES chores(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 4. Multi-User Assignments Table
CREATE TABLE IF NOT EXISTS chore_assignments (
    chore_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    PRIMARY KEY (chore_id, user_id),
    FOREIGN KEY (chore_id) REFERENCES chores(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 5. Token Transactions (Rewards / Manual Adjustment Ledger)
CREATE TABLE IF NOT EXISTS token_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    amount REAL NOT NULL, -- negative for spend, positive for adjustment
    category TEXT NOT NULL, -- 'spend', 'adjust'
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 6. Encouragements (Kudo / Boost Message System)
CREATE TABLE IF NOT EXISTS encouragements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_id INTEGER NOT NULL,
    recipient_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    is_read INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    read_at TIMESTAMP,
    FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (recipient_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 7. Google Calendars Table (Secret iCal Feeds)
CREATE TABLE IF NOT EXISTS google_calendars (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    ical_url TEXT NOT NULL,
    color TEXT NOT NULL, -- Hex or css-compatible color
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 8. Announcements Table
CREATE TABLE IF NOT EXISTS announcements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active INTEGER DEFAULT 1 -- 1=Active, 0=Inactive
);

-- 9. Announcement Acknowledgments Table
CREATE TABLE IF NOT EXISTS announcement_acknowledgments (
    announcement_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    acknowledged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (announcement_id, user_id),
    FOREIGN KEY (announcement_id) REFERENCES announcements(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 10. Admin Audit Logs (Audit Trail)
CREATE TABLE IF NOT EXISTS admin_audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id INTEGER NOT NULL,
    action_type TEXT NOT NULL, -- 'undo', 'reassign', 'comment'
    details TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (admin_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 11. Rewards Store Menu Table
CREATE TABLE IF NOT EXISTS rewards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    cost_points REAL NOT NULL,
    tier INTEGER NOT NULL, -- 1, 2, or 3
    is_active INTEGER DEFAULT 1
);

-- Indexes for performance tuning and fast UI loads
CREATE INDEX IF NOT EXISTS idx_admin_audit_logs_admin ON admin_audit_logs(admin_id);
CREATE INDEX IF NOT EXISTS idx_users_name ON users(name);
CREATE INDEX IF NOT EXISTS idx_chores_assigned ON chores(assigned_user_id);
CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON chore_logs(completed_at);
CREATE INDEX IF NOT EXISTS idx_assignments_user ON chore_assignments(user_id);
CREATE INDEX IF NOT EXISTS idx_transactions_user ON token_transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_encouragements_recipient ON encouragements(recipient_id);
CREATE INDEX IF NOT EXISTS idx_announcements_active ON announcements(is_active);
CREATE INDEX IF NOT EXISTS idx_acknowledgments_user ON announcement_acknowledgments(user_id);
CREATE INDEX IF NOT EXISTS idx_rewards_tier ON rewards(tier);


