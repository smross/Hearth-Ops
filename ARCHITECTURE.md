# Infrastructure Blueprint & Security Safeguards

## 🖥️ Hardware Layer Allocations

### 1. The Core Server (ThinkPad T440s)
* **OS:** Headless Linux distribution (Ubuntu Server or Debian).
* **Role:** Hosts the core Docker environment, FastAPI server, SQLite database, and individual local utility tasks.
* **Resiliency Benefit:** Built-in battery acts as an automatic internal UPS against power interruptions.

### 2. The Kitchen Command Center (13-Inch iPad)
* **Role:** Dedicated family status hub positioned on the kitchen island.
* **Hardening Protocol:** Enforced via iOS **Guided Access** locked permanently to the local browser window. Home-button and external gesture inputs are entirely password-restricted.
* **Network Isolation:** Paused or isolated from WAN access via local network definitions. The device can access the local ThinkPad IP address but is explicitly banned from reaching the public internet to neutralize security lifecycle risks.

### 3. Client Validation Devices
* **Old / SIM-less Smartphones:** Repurposed over local Wi-Fi for younger children.
* **Primary Smartphones:** Utilized by older children.

---

## 🔒 Remote Management & Security Boundaries

### Secure Remote Access
* **Engine:** **Tailscale** installed directly to the ThinkPad T440s host environment and parental mobile devices.
* **Constraint:** Excluded entirely from corporate workstations. Remote administration (toggling access rules or manually overriding point ledgers) is executed exclusively from parental smartphones over the private secure mesh network.

### Data Privacy & Isolation
* **Zero-Cloud PII:** All tracking metrics, child identification records, and logging metrics stay contained inside the local SQLite file.
* **Key Scrape Protection:** API parameters for any external integrations (e.g., Google Ecosystem) are isolated inside root-protected `.env` contexts. Terminal output logging (`stdout`) is programmatically stripped of variables.