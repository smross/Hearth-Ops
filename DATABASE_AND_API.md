# Ledger Mechanics & Interface Logic

The core application utilizes a short, high-frequency reinforcement loop. Tasks translate immediately to an internal balance ledger using deterministic user inputs.

## 🗄️ Core Database Schema (SQLite)


HearthOps is backed by a local SQLite database that maintains family ledger integrity using foreign key constraints and indexed queries.

### 1. `users` (Family Profiles)
- `id`: INTEGER, Primary Key, Auto-increment.
- `name`: TEXT, UNIQUE, NOT NULL.
- `pin_hash`: TEXT, NOT NULL (SHA-256 hashed PIN code).
- `token_balance`: REAL, default `0.0` (active ledger currency).
- `is_parent`: INTEGER, default `0` (1 = Parent/Admin, 0 = Child/User).

### 2. `chores` (Chore Definitions)
- `id`: INTEGER, Primary Key, Auto-increment.
- `title`: TEXT, NOT NULL.
- `description`: TEXT.
- `category`: TEXT, default `'General'`.
- `frequency`: TEXT, default `'daily'` (`'daily'`, `'weekly'`, or `'adhoc'`).
- `assigned_user_id`: INTEGER, Foreign Key to `users.id` (deprecated for multi-user assignment).
- `value_credits`: REAL, default `0.0`.
- `max_daily_completions`: INTEGER, default `1`.
- `is_active`: INTEGER, default `1` (1 = active, 0 = disabled).
- `is_required`: INTEGER, default `0` (1 = required/blocks other actions, 0 = optional).
- `is_shared`: INTEGER, default `0` (1 = public chore, 0 = assigned).
- `after_four_pm`: INTEGER, default `0` (1 = only visible after 4:00 PM local time).

### 3. `chore_assignments` (Multi-User Assignment Join Table)
- `chore_id`: INTEGER, Primary Key, Foreign Key to `chores.id` ON DELETE CASCADE.
- `user_id`: INTEGER, Primary Key, Foreign Key to `users.id` ON DELETE CASCADE.

### 4. `chore_logs` (Immutable Chore Completion Audit Log)
- `id`: INTEGER, Primary Key, Auto-increment.
- `chore_id`: INTEGER, Foreign Key to `chores.id`.
- `user_id`: INTEGER, Foreign Key to `users.id`.
- `action_type`: TEXT, default `'earn'` (`'earn'`, `'undo'`).
- `credits_delta`: REAL, default `0.0`.
- `completed_at`: TIMESTAMP, default `CURRENT_TIMESTAMP`.
- `admin_note`: TEXT (Parent modification remarks).

### 5. `token_transactions` (Rewards / Manual Adjustment Ledger)
- `id`: INTEGER, Primary Key, Auto-increment.
- `user_id`: INTEGER, Foreign Key to `users.id` ON DELETE CASCADE.
- `amount`: REAL, NOT NULL (positive for manual awards/adjustments, negative for spends).
- `category`: TEXT, NOT NULL (`'spend'`, `'adjust'`).
- `description`: TEXT (Reasoning).
- `created_at`: TIMESTAMP, default `CURRENT_TIMESTAMP`.

### 6. `encouragements` (Family Message / Kudo Board)
- `id`: INTEGER, Primary Key, Auto-increment.
- `sender_id`: INTEGER, Foreign Key to `users.id` ON DELETE CASCADE.
- `recipient_id`: INTEGER, Foreign Key to `users.id` ON DELETE CASCADE.
- `content`: TEXT, NOT NULL.
- `is_read`: INTEGER, default `0` (1 = read, 0 = unread).
- `created_at`: TIMESTAMP, default `CURRENT_TIMESTAMP`.

### 7. `google_calendars` (Linked Secret iCal Feeds)
- `id`: INTEGER, Primary Key, Auto-increment.
- `name`: TEXT, NOT NULL.
- `ical_url`: TEXT, NOT NULL.
- `color`: TEXT, NOT NULL (hex or CSS-compatible string).

### 8. `announcements` (Family Announcements)
- `id`: INTEGER, Primary Key, Auto-increment.
- `title`: TEXT, NOT NULL.
- `content`: TEXT, NOT NULL.
- `is_active`: INTEGER, default `1` (1 = visible, 0 = hidden).

### 9. `announcement_acknowledgments` (Acknowledge Join Table)
- `announcement_id`: INTEGER, Primary Key, Foreign Key to `announcements.id` ON DELETE CASCADE.
- `user_id`: INTEGER, Primary Key, Foreign Key to `users.id` ON DELETE CASCADE.

### 10. `admin_audit_logs` (Parent Remediation Logs)
- `id`: INTEGER, Primary Key, Auto-increment.
- `admin_id`: INTEGER, Foreign Key to `users.id` ON DELETE CASCADE.
- `action_type`: TEXT, NOT NULL (`'undo'`, `'reassign'`, `'comment'`).
- `details`: TEXT, NOT NULL.