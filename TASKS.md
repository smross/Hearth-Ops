# HearthOps: Implementation Roadmap & Task State

This file tracks the active deployment state of the HearthOps monorepo. Use this checklist to guide AI development agents through atomic, step-by-step feature implementation.

## 🟩 Phase 1: Project Scaffolding & Environment Initialization
- [ ] **Task 1.1:** Initialize the base repository directory structures (`backend/`, `frontend/`, `infrastructure/pihole/`).
- [ ] **Task 1.2:** Create the configuration template file `.env.example` defining database locations, security tokens, and localized ports.
- [ ] **Task 1.3:** Construct the baseline `docker-compose.yml` file to orchestrate the core app placeholder and a Pi-hole container mapping the required persistent internal volume locations.

## 🟩 Phase 2: Core Database Architecture (SQLite Engine)
- [ ] **Task 2.1:** Code `backend/database.py` using Python's native `sqlite3` or an async wrapper to initialize connection pooling and directory mapping.
- [ ] **Task 2.2:** Author database initialization scripts to establish the core schemas (`users`, `chores`, `chore_logs`) alongside unique indexing arrays.
- [ ] **Task 2.3:** Write a seeding script to populate the database with initial family user profiles and secure, default 4-digit PIN definitions.

## 🟩 Phase 3: Headless API Engine Foundations (FastAPI)
- [ ] **Task 3.1:** Scaffold `backend/main.py` with standard FastAPI routing mechanics, health check tools, and CORS allocations.
- [ ] **Task 3.2:** Develop the verification endpoint API (`POST /api/verify`) that processes user context and evaluates PIN inputs against the database records.
- [ ] **Task 3.3:** Construct the ledger updates controller (`POST /api/chores/complete`) to increment point pools and record transaction histories upon clean verification events.

## 🟩 Phase 4: UI Engine & Template Scaffolding (HTMX & CSS)
- [ ] **Task 4.1:** Build the core base HTML shell utilizing an ultra-lightweight, mobile-first CSS architecture.
- [ ] **Task 4.2:** Construct the client validation form using HTMX endpoints to handle dynamic PIN entries, error responses, and live ledger balances without full-page reloads.
- [ ] **Task 4.3:** Formulate the read-only, split-screen administrative dashboard layout structured specifically for tablet kiosks.