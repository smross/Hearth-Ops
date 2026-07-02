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

### 11. `rewards` (Rewards Store Menu)
- `id`: INTEGER, Primary Key, Auto-increment.
- `title`: TEXT, NOT NULL.
- `description`: TEXT.
- `cost_points`: REAL, NOT NULL.
- `tier`: INTEGER, NOT NULL.
- `is_active`: INTEGER, default `1` (1 = active, 0 = disabled).

## 🏆 Reward Tiers & Ratio Mechanics

The HearthOps economy uses a **100 points baseline** ratio system.

### 1. Ratio Baseline
- **Standard Daily Chore**: 25 - 50 points (e.g., clear place, unload dishwasher, tidy great room).
- **Deep Weekly Chore**: 200 - 500 points (e.g., deep clean bathrooms, scrub showers, lawn maintenance).

### 2. Tier 1 (Screen Time & Network)
- **30 Mins Xbox/PC**: 50 pts
- **60 Mins Unrestricted Phone**: 100 pts
- **Plume Network 'Lag-Free' Priority Boost (1 Hour)**: 150 pts

### 3. Tier 2 (Privileges & Passes)
- **Pick Family Movie Night**: 150 pts
- **Pick Family Dessert**: 100 pts
- **Pick Family Dinner Menu**: 300 pts
- **'Get Out of Jail Free' Chore Pass**: 500 pts
  - *Allows skipping a task and routing it to a sibling or a bounty pool.*

### 4. Tier 3 (Quality Time & Outings)
- **'QT Cone' Ice Cream Run with Mom/Dad**: 400 pts
- **Late-Night Passenger (Stay up 1 hour late on weekend)**: 250 pts
- **Chesterfield Valley Excursion (2-hour weekend outing)**: 800 pts

### 5. ADHD System Modifiers
- **'Early Bird' Modifier**: +10% points for chores completed before 9:00 AM.
- **Streak Boosts**: Additional points for daily completion streaks.
- **Sibling Bounty Board**: Siblings can complete expired chores for 1.5x points (points are deducted from the target child's potential balance).