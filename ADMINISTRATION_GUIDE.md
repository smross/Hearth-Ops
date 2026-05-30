# HearthOps Administration & Customization Guide

This guide describes how to configure and administer your HearthOps installation, including customizing family members, managing the chore definitions, and linking Google Calendars.

---

## 👥 Managing Family Members (Profiles)
HearthOps distinguishes between parents (administrators) and kids (general users) based on the `is_parent` flag in the database. 

*   **Parents (`is_parent = 1`):** Appears below the PIN pad on the login page. Can log into the Admin Console by entering their PIN.
*   **Kids (`is_parent = 0`):** Appears at the top of the login page. Can complete chores and earn tokens, but cannot access admin features.

### Customizing Names and PINs (Local Server)
The default generic names are populated by the database seeding script. To use your actual family names on your local server without tracking them in your public git repository:

1. Create a file named `family_members.json` in the `backend/` directory (this filename is ignored in `.gitignore`).
2. Populate the file with your family profile names, PINs, and parent roles in JSON format:
   ```json
   [
       {"name": "Parent 1", "pin": "3157", "is_parent": 1},
       {"name": "Parent 2", "pin": "9019", "is_parent": 1},
       {"name": "Child 3", "pin": "0129", "is_parent": 0},
       {"name": "Child 1", "pin": "1019", "is_parent": 0},
       {"name": "Child 2", "pin": "0404", "is_parent": 0},
       {"name": "Child 4", "pin": "0924", "is_parent": 0}
   ]
   ```
3. Run the database seed script to apply:
   *   **Docker Container:** `docker compose exec backend python seed.py`
   *   **Local Python environment:** `python backend/seed.py`

*Note: Running `seed.py` will reset existing chore logs and token balances. If you wish to make live modifications without resetting data, connect directly to the SQLite database `data/hearth.db` using a SQLite GUI client (like DB Browser for SQLite) and modify the `users` table directly.*

---

## 📋 Managing Chores
Chore definitions, categories, and payouts are defined in the database.

### Modifying Chore Definitions
To change default chores before building:
1. Open `backend/seed.py` and modify the `DEFAULT_CHORES` list.
2. Re-run the seed script.

### Live Management via Admin Console
To edit chores live without resetting database data:
1. Tap any Parent profile card on the login screen and enter your Parent PIN.
2. In the Admin Console, scroll down to the **Chore Management** section.
3. Open any category accordion (e.g. Kitchen, Cleaning).
4. Update the fields (Title, Description, Category, Frequency, Max Daily Completions, and Value Credits).
5. **Assigning Chores:** Check the boxes next to family members under *Allowed Assignees*. Leaving all check boxes blank marks the chore as "Public" (anyone can complete it).
6. Click **Save Changes**.

---

## 📅 Linking Google Calendars
HearthOps parses private Google Calendar iCal feeds and displays color-coded events in a 3-column responsive layout.

### Finding Your Secret iCal URL
1. Open [Google Calendar](https://calendar.google.com) on a desktop browser.
2. Find the calendar in the left sidebar under *My Calendars*.
3. Click the **Three Dots (Options)** -> **Settings and sharing**.
4. Scroll to the very bottom to the **Integrate calendar** section.
5. Copy the URL from the **Secret address in iCal format** field (do NOT use the Public address).

### Adding it to HearthOps
1. Open the Admin Console.
2. Scroll to the **Google Calendar Connections** section.
3. Input a **Calendar Name** (e.g., "Family Events").
4. Select a **Display Theme Color** (e.g., Red, Blue, Green) to color-code the events on the main screen.
5. Paste the copied secret URL into the **Secret iCal Feed URL** input box.
6. Click **Link Calendar**. The dashboard will automatically fetch and display upcoming events!
