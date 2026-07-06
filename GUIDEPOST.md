# HearthOps Guidepost: Project Intent & Current State

## 📍 Where We Are
We have completed the **Backend Foundations (Phases 1-3)**, **UI Scaffolding (Phases 4-5)**, **Announcements (Phase 7)**, and **Three-Jar Point Allocation & Payout Queue (Phase 8)**.
- **Database:** SQLite with updated tables supporting `save_balance` and `give_balance` for users, `target_jar` for rewards, and `payout_requests` for the confirmation queue.
- **System Scale:** Successfully migrated all database point quantities to a **10x integer scale** to guarantee clean split allocations without float/decimal clutter.
- **Active Branch:** `feature/alpha-scaffold`

## 🛠 Architectural Decisions
1. **Security:** PINs are stored as SHA-256 hashes. Every transaction (`/api/chores/complete`) requires the PIN to be re-verified, ensuring the kiosk cannot be "left logged in" to a high-privilege state without validation.
2. **UI Strategy:** We are using **HTMX** with **FastAPI/Jinja2** to keep the frontend ultra-lightweight. This avoids the need for a complex JS build step (like React/Vue) and fits the "low-power tablet kiosk" requirement perfectly.
3. **Database Transactions:** We use explicit `BEGIN TRANSACTION` and `COMMIT/ROLLBACK` for ledger updates to ensure that points are never awarded without a log entry, and vice-versa.
4. **Three-Jar Auto-Split (50/30/20):** Points from completed chores split strictly into whole integers to prevent fractional leaks:
   * $\text{Give Jar} = \text{round}(\text{Original} \times 0.20)$
   * $\text{Save Jar} = \text{round}(\text{Original} \times 0.30)$
   * $\text{Spend Jar} = \text{Original} - \text{Give Jar} - \text{Save Jar}$
5. **10x Scale Resolution:** Points are multiplied by 10 (e.g. 2 points becomes 20 points). This ensures that every chore completed contributes at least 1 point to all three jars, avoiding the psychological issue of minor chores contributing "0 points" to the Give Jar due to rounding.
6. **Parent-Approved Payout Queue:** Save (cash out) and Give (charity matches) redemptions deduct points immediately and enter a pending confirmation queue. Parents approve/decline requests using their PIN via the Admin Console. Decline events refund points back to the correct source jar.

## 🚀 Where We Are Going
1. **Pi-hole Integration (Phase 6.2):** Configure network priority toggles and access limits hooked into the local Pi-hole instance.
2. **Production Deployment:** Release features to production under Docker.

## 📝 Future Self Note
If you are resuming on a new device:
1. Copy `.env.example` to `.env`.
2. Run `docker-compose up --build`.
3. Run `python backend/seed.py` (inside the container or locally) to populate the family members.
4. Primary Goal: Verify the "Identify Yourself" -> "Dashboard" -> "Complete Chore" -> "Split Validation" loop.
