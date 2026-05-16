# HearthOps

HearthOps is a self-hosted Docker monorepo that automates family routines, manages an ADHD-friendly token economy, and enforces network accountability. Built with FastAPI and SQLite for a local server and tablet kiosk, it replaces parental nagging with immediate dopamine feedback loops and secure remote overrides.

## 🖥️ System Architecture

* **Core Server (ThinkPad T440s):** Runs a headless Linux environment hosting the core Docker containers. Its internal battery acts as an automatic hardware UPS to maintain database integrity during unexpected power fluctuations.
* **Command Center (13-Inch iPad):** Positioned on the kitchen island as a high-utility family hub. Hardened via Apple **Guided Access** to a single local browser window and entirely isolated from WAN access at the router level for enhanced platform security.
* **Validation Terminals:** Personal smartphones (including a SIM-less Wi-Fi device for the youngest child) running a mobile-responsive interface for secure task clearance using unique 4-digit PINs.
* **Remote Administration:** Managed exclusively from parental mobile devices over a secure **Tailscale** mesh network, completely bypassing the need to install orchestration software on corporate workstations.

---

## 📁 Repository Directory Structure

```text
hearth-ops/
├── .env.example             # Template for secure environment variables
├── .gitignore               # Multi-stack environment exclusion mapping
├── docker-compose.yml       # Local multi-container deployment configuration
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

* **Zero-Cloud PII:** Family identities, performance histories, and ledger transaction accounts are strictly maintained inside the internal containerized SQLite instance over the local area network.
* **Credential Isolation:** All developer access parameters and system tokens must reside exclusively inside a root-protected `.env` runtime context. Standard application logging is configured to explicitly suppress environment configurations from flat-text outputs.
