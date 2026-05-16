# HearthOps Guidepost: Project Intent & Current State

## 📍 Where We Are
We have completed the **Backend Foundations (Phases 1-3)**. 
- **Database:** SQLite with a robust schema (`schema.sql`), connection management (`database.py`), and a family seeding script (`seed.py`).
- **API:** FastAPI engine (`main.py`) with user verification and atomic ledger update transactions.
- **Orchestration:** `docker-compose.yml` is ready for Backend and Pi-hole services.

## 🛠 Architectural Decisions
1. **Security:** PINs are stored as SHA-256 hashes. Every transaction (`/api/chores/complete`) requires the PIN to be re-verified, ensuring the kiosk cannot be "left logged in" to a high-privilege state without validation.
2. **UI Strategy:** We are using **HTMX** with **FastAPI/Jinja2** to keep the frontend ultra-lightweight. This avoids the need for a complex JS build step (like React/Vue) and fits the "low-power tablet kiosk" requirement perfectly.
3. **Database Transactions:** We use explicit `BEGIN TRANSACTION` and `COMMIT/ROLLBACK` for ledger updates to ensure that points are never awarded without a log entry, and vice-versa.

## 🚀 Where We Are Going
1. **Frontend Scaffolding (Phase 4):** Building a mobile-first, "chunky" UI suitable for touchscreens.
2. **Integration:** Serving the frontend directly from FastAPI for simplicity in this initial prototype.
3. **Validation:** Pushing to a `feature/prototype-alpha` branch to ensure the user can pull and test in their local Docker environment.

## 📝 Future Self Note
If you are resuming on a new device:
1. Copy `.env.example` to `.env`.
2. Run `docker-compose up --build`.
3. Run `python backend/seed.py` (inside the container or locally) to populate the family members.
