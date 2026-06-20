# HearthOps

HearthOps is a self-hosted monorepo that automates family routines, manages a token-based chore economy, and supports local calendar synchronization. Built with FastAPI, HTMX, and SQLite, it is designed to run in a containerized Docker environment for local network dashboarding, tablet kiosks, or phone-based chore validation.

For directions on customizing family profiles, managing chores, and linking Google Calendars, see the [Administration Guide](file:///C:/Users/sgtse/SourceCode/Hearth-Ops/ADMINISTRATION_GUIDE.md).

---

## 🖥️ Architecture & Deployment Ideas

HearthOps is highly flexible and can be adapted to various home server setups:

*   **Core Server:** Typically hosted on a local server, single-board computer, or older laptop (which offers a built-in battery backup) running Docker.
*   **Command Center Kiosk:** Often displayed on a kitchen tablet or shared screen. Using tablet kiosk features (like Guided Access on iOS) locks the interface to the local dashboard window.
*   **Validation Terminals:** Family members' mobile phones or local Wi-Fi devices can access the responsive interface to enter their unique 4-digit PIN and check off chores.
*   **Remote Administration:** Access to the admin console can be secured using local access rules or a private VPN mesh network (like Tailscale) for secure parental override.

---

## 📁 Repository Directory Structure

```text
hearth-ops/
├── .env.example             # Template for secure environment variables
├── .gitignore               # Multi-stack environment exclusion mapping
├── docker-compose.yml       # Local multi-container deployment configuration
├── ADMINISTRATION_GUIDE.md  # How to configure family users, chores, and calendars
├── backend/                 # Python/FastAPI Core Application Engine
│   ├── main.py              # API endpoint routing and verification logic
│   ├── database.py          # SQLite connection and migration engine
│   └── requirements.txt     # Python dependencies
├── frontend/                # Lightweight HTMX and responsive CSS templates
└── infrastructure/          # Local network utility provisions
    └── pihole/              # Persistent volume mounts for local blocklists
```

---

## 🔒 Security & Data Integrity

*   **Zero-Cloud PII:** Family identities, performance histories, and ledger transaction accounts are strictly maintained inside the local SQLite database.
*   **Credential Isolation:** System configurations, passwords, and calendar links reside inside a local `.env` runtime context to protect private data.

---

## 🧪 Testing & Validation

The backend includes an automated sandboxed test suite using `pytest`, `freezegun` (for clock-travel tests), and `BeautifulSoup` (for HTML output validation). The tests run in an isolated environment against a temporary SQLite database (`test_sandbox_hearth.db`), leaving the active databases completely untouched.

To run the test suite inside the containerized environment:
```bash
docker compose exec backend pytest test_suite.py
```

