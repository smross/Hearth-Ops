# HearthOps Project Instructions

This file provides foundational context for Gemini CLI when working on the HearthOps project.

## 📍 Project State
- **Current Phase:** Phase 4 (UI Scaffolding) completed. 
- **Next Phase:** Phase 5 (Docker Integration & Local Validation).
- **Active Branch:** `feature/alpha-scaffold`
- **Roadmap:** Refer to `TASKS.md` for the granular checklist.
- **Guideposts:** Refer to `GUIDEPOST.md` for architectural rationale and deep-dives.

## 🏗 Architecture & Conventions
- **Stack:** FastAPI (Backend), HTMX + Vanilla CSS (Frontend), SQLite (Database).
- **Directory Structure:**
  - `backend/`: Core logic, API, and database management.
  - `frontend/`: Templates (Jinja2) and static assets (CSS).
  - `infrastructure/`: Config for external services like Pi-hole.
- **Security:**
  - PINs are SHA-256 hashed.
  - Every ledger transaction requires PIN re-verification.
  - Credentials must live in `.env` (refer to `.env.example`).
- **Coding Style:** Keep it minimal, functional, and "chunky" (for tablet usage). Prefer HTMX over heavy JavaScript.

## 🛠 Onboarding for New Sessions
When resuming this project on a new device:
1. **Repository:** Ensure you are on the `feature/alpha-scaffold` branch.
2. **Environment:**
   - Copy `.env.example` to `.env`.
   - Run `docker-compose up --build` to verify the containerized environment.
3. **Database:**
   - Run `python backend/seed.py` (either inside the container or locally) to initialize the family profiles.
4. **Primary Goal:** Verify the "Identify Yourself" -> "Dashboard" -> "Complete Chore" loop.
