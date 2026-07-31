# HearthOps: Implementation Roadmap & Task State

This file tracks the active deployment state of the HearthOps monorepo. Use this checklist to guide AI development agents through atomic, step-by-step feature implementation.

## 🟩 Phase 1: Project Scaffolding & Environment Initialization
- [x] **Task 1.1:** Initialize the base repository directory structures (`backend/`, `frontend/`, `infrastructure/pihole/`).
- [x] **Task 1.2:** Create the configuration template file `.env.example` defining database locations, security tokens, and localized ports.
- [x] **Task 1.3:** Construct the baseline `docker-compose.yml` file to orchestrate the core app placeholder and a Pi-hole container mapping the required persistent internal volume locations.

## 🟩 Phase 2: Core Database Architecture (SQLite Engine)
- [x] **Task 2.1:** Code `backend/database.py` using Python's native `sqlite3` or an async wrapper to initialize connection pooling and directory mapping.
- [x] **Task 2.2:** Author database initialization scripts to establish the core schemas (`users`, `chores`, `chore_logs`) alongside unique indexing arrays.
- [x] **Task 2.3:** Write a seeding script to populate the database with initial family user profiles and secure, default 4-digit PIN definitions.

## 🟩 Phase 3: Headless API Engine Foundations (FastAPI)
- [x] **Task 3.1:** Scaffold `backend/main.py` with standard FastAPI routing mechanics, health check tools, and CORS allocations.
- [x] **Task 3.2:** Develop the verification endpoint API (`POST /api/verify`) that processes user context and evaluates PIN inputs against the database records.
- [x] **Task 3.3:** Construct the ledger updates controller (`POST /api/chores/complete`) to increment point pools and record transaction histories upon clean verification events.

## 🟩 Phase 4: UI Engine & Template Scaffolding (HTMX & CSS)
- [x] **Task 4.1:** Build the core base HTML shell utilizing an ultra-lightweight, mobile-first CSS architecture.
- [x] **Task 4.2:** Construct the client validation form using HTMX endpoints to handle dynamic PIN entries, error responses, and live ledger balances without full-page reloads.
- [x] **Task 4.3:** Formulate the read-only, split-screen administrative dashboard layout structured specifically for tablet kiosks.

## 🟩 Phase 5: Docker Integration & Local Validation
- [x] **Task 5.1:** Update `backend/main.py` to handle dynamic template/static paths for both local and container environments.
- [x] **Task 5.2:** Refine `docker-compose.yml` volume mounts to preserve project directory structure.
- [x] **Task 5.3:** Enhance `backend/seed.py` to include default chores and load environment variables from `.env`.
- [x] **Task 5.4:** Verify the full "Identify" -> "Dashboard" -> "Complete Chore" loop locally.
- [x] **Task 5.5:** Run `docker-compose up --build` to confirm the containerized environment is fully functional.

## 🟩 Phase 6: Production Hardening & Feature Expansion (Next)
- [x] **Task 6.1:** Implement "Token Redemptions" (Rewards store) for kids to spend their earned credits.
- [ ] Task 6.2 (Deferred): Configure Pi-hole API hooks to toggle internet access based on chore completion status.
- [x] **Task 6.3:** Add "Transaction History" view for kids to see their past earned/spent tokens.

## 🟩 Phase 7: Family Announcements Feature
- [x] **Task 7.1:** Design database schemas for `announcements` and individual user `announcement_acknowledgments`.
- [x] **Task 7.2:** Construct the Admin Console interface for adding, active-toggling, and deleting announcements.
- [x] **Task 7.3:** Implement landing page alert banner showing active notice cards dynamically.
- [x] **Task 7.4:** Establish logged-in user interceptor modal requiring explicit "Got It" clicks to persist acknowledgments.
- [x] **Task 7.5:** Standardize screensaver viewport constraints and unified America/Chicago CT/CDT AM/PM time formatting.

## 🟩 Phase 8: Three-Jar Point Allocation (Spend/Save/Give) & Parent Approval Queue
- [x] **Task 8.1:** Add `save_balance`, `give_balance`, and `target_jar` fields to database schemas and update default seed configurations.
- [x] **Task 8.2:** Implement integer-based auto-split mathematical allocation (50% Spend / 30% Save / 20% Give) on chore completion and undo.
- [x] **Task 8.3:** Build a parent-approval queue for high-value Save (cash payout) and Give (charity match) store redemptions.
- [x] **Task 8.4:** Redesign the Admin Console ledger table to split balances, unified positive/negative manual adjustments, and pending payout controls.
- [x] **Task 8.5:** Integrate HTMX `hx-confirm` modal safety checks for parent balance resets.
- [x] **Task 8.6:** Migrate all transaction history and active balances on staging to a clean 10x integer scale.