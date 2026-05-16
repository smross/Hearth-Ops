# Network Filtering & Restriction Protocols

Accountability logic relies on a phased structural approach, utilizing existing device enforcement constraints before scaling to router-level infrastructure hardware.

## 🛡️ Active Device Safeguards
To prevent common DNS avoidance tactics, client devices maintain locked configurations:
* **Mobile Devices:** Enforced by system-level **Boomerang Parental Controls**.
* **Workstations/PCs:** Restricted to the Microsoft Edge environment tied to **Microsoft Family Safety**.
* **Result:** Underlying changes to local DNS pointers, third-party VPN configurations, or DNS-over-HTTPS (DoH) parameters are completely restricted.

---

## 🛑 Network Blocking & Filtering Implementations

### Phase 1: Manual Eero Profile Interruption (Immediate)
* **Mechanics:** Children's devices are organized into native user profiles within the Eero network app.
* **Enforcement:** If daily threshold timelines are missed, a parent manually taps **Pause** on the specific child's network profile.
* **Content Filtering:** Existing Eero+ subscriptions manage upstream content controls profile-by-profile.

### Phase 2: Pi-hole Docker Stopgap (Intermediate Drop)
* **Engine:** Pi-hole deployed inside the local Docker context on the ThinkPad server.
* **Total Internet Block:** Targeted client devices are grouped into a dedicated restriction profile. Activating this group executes a wildcard regex rule: `.` 
* **The HTTPS Caveat:** Because modern web protocols use secure handshakes, this blocking mechanism causes client browsers to throw a secure connection validation failure (`NET::ERR_CERT_COMMON_NAME_INVALID`) instead of rendering a custom "Do Your Chores" landing page.

### Phase 3: Ubiquiti UniFi Transition (Future Scale)
* **Goal:** Completely eliminate manual parental interaction for internet restrictions.
* **Execution:** Migrate network nodes to a UniFi routing setup. The FastAPI backend container can execute automated scripts leveraging `python-unifi-client`.
* **Automation Loop:** If chores are not verified by the system's deadline time, the backend fires an asynchronous local API command to the UniFi controller to block the child's MAC addresses automatically.