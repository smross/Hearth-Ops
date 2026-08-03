# HearthOps Session Summary & Migration Notes (August 2, 2026)

This file details the recent project progress, database migration tools created, and instructions for future AI assistants or developers resuming work on HearthOps.

---

## 📍 Session Accomplishments & Progress

During this session, we completed the prep work to migrate HearthOps from the development host to a new Proxmox LXC instance running Docker:

1. **Code Alignment & Remote Push:**
   - Verified that the `feature/alpha-scaffold` dev branch contains the completed **Phase 8 (Three-Jar Spend/Save/Give Point Allocation & Parent Approval Queue)** and **Phase 7 (Announcements)** features.
   - Checked that the local test client runs successfully inside the Docker environment (`pytest` succeeded with 8/8 test cases passing).
   - Merged `feature/alpha-scaffold` into the `main` production branch.
   - Pushed all commits (both `main` and `feature/alpha-scaffold`) to the remote GitHub repository at `https://github.com/smross/Hearth-Ops`.

2. **Economy Migration Script Created:**
   - Discovered that the existing live production database (`hearth.db`) was still on the legacy **1x float scale** and lacked the new three-jar columns.
   - Created **[migrate_economy_10x.py](file:///C:/Users/sgtse/SourceCode/Hearth-Ops/backend/migrate_economy_10x.py)**.
   - This script updates the database schema, scales all point quantities (balances, chore payouts, reward costs, log increments, manual transactions) by **10**, and automatically splits the kids' historical balances into **Spend (50%), Save (30%), and Give (20%)** jars.
   - Validated the script inside the staging container on a direct copy of the live production database. All balances and logs migrated successfully without issues.

3. **Pi-hole Deferral:**
   - Marked **Task 6.2 (Configure Pi-hole API hooks)** as **Deferred/Paused** in **[TASKS.md](file:///C:/Users/sgtse/SourceCode/Hearth-Ops/TASKS.md)**. The architecture remains modular to support adding DNS/network locks later, but it is ignored for this deployment phase.

4. **Local Services Deactivation:**
   - Stopped and removed the local backend docker services (`hearth-ops-staging-backend` and `hearth-ops-production-backend`) to prevent any local user interactions.
   - Left the local directory intact as a safe backup copy on this machine.

---

## 🏗 Current Project State

- **Deployment Host:** Moving to Proxmox VE (in a nesting-enabled LXC container running Docker).
- **Branch:** `main` (Fully up to date with dev features up to Phase 8).
- **Core Stack:** FastAPI, SQLite, HTMX, Tailwind-free Vanilla CSS.

---

## 🚀 Instructions for Future Assistants & Developers

If you are picking up HearthOps on the new Proxmox VM/LXC, follow these steps to resume:

### 1. Verification
Run the test suite to ensure the environment is correctly configured:
```bash
docker compose exec backend pytest
```

### 2. Upgrading/Migrating an Old Production Database
If you are moving a copy of the old `hearth.db` (1x scale) to the new host, run the migration script to upgrade the schema and scale the economy:
```bash
# Option A: Run directly on host database file before container startup
python backend/migrate_economy_10x.py path/to/hearth.db

# Option B: Run inside container once active
docker compose exec backend python migrate_economy_10x.py
```

### 3. Environment Checklist
Ensure the host has a `.env` file containing:
```ini
APP_ENV=production
APP_PORT=8000
TZ=America/Chicago
SECRET_KEY=<secure_hex_key>
```
Ensure that the local `./data` folder has proper read/write permissions for the non-root container user (`chown -R 10001:10001 ./data` on the host).
