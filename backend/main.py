import os
import logging
import hashlib
import requests
import datetime
from typing import Optional, List
from pydantic import BaseModel
from fastapi import FastAPI, Depends, HTTPException, status, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from icalendar import Calendar
import recurring_ical_events
from database import init_db, get_db_connection

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cache to avoid calling Google servers on every page refresh
CALENDAR_CACHE = {
    "events": [],
    "last_fetched": None
}
CACHE_DURATION = datetime.timedelta(minutes=10)

def fetch_and_parse_calendars():
    global CALENDAR_CACHE
    now = datetime.datetime.now()
    if CALENDAR_CACHE["last_fetched"] and (now - CALENDAR_CACHE["last_fetched"]) < CACHE_DURATION:
        return CALENDAR_CACHE["events"]
        
    events_list = []
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, ical_url, color FROM google_calendars")
        calendars = cursor.fetchall()
        
    start_date = datetime.date.today()
    end_date = datetime.date.today() + datetime.timedelta(days=7) # show next 7 days of events
    
    for cal in calendars:
        try:
            # Add a timeout of 4 seconds to avoid hanging the UI
            response = requests.get(cal["ical_url"], timeout=4)
            if response.status_code == 200:
                ical_data = response.text
                ical_calendar = Calendar.from_ical(ical_data)
                
                # Expand recurring events in range
                ical_events = recurring_ical_events.of(ical_calendar).between(start_date, end_date)
                
                for event in ical_events:
                    summary = str(event.get("SUMMARY", "No Title"))
                    start = event.get("DTSTART").dt
                    end = event.get("DTEND").dt
                    
                    # start and end can be date or datetime
                    all_day = not isinstance(start, datetime.datetime)
                    
                    # Convert everything to string/standard format
                    if all_day:
                        start_str = start.strftime("%Y-%m-%d")
                        start_date_obj = start
                    else:
                        start_str = start.strftime("%I:%M %p")
                        start_date_obj = start.date()
                        
                    if start_date_obj >= datetime.date.today():
                        events_list.append({
                            "summary": summary,
                            "start": start_str,
                            "all_day": all_day,
                            "calendar_name": cal["name"],
                            "color": cal["color"],
                            "date_obj": start_date_obj
                        })
        except Exception as e:
            logger.error(f"Error fetching calendar {cal['name']}: {e}")
            
    # Sort events by date and time
    def get_sort_key(ev):
        d = ev["date_obj"]
        # extract datetime/time or use min time for sorting
        return d
        
    events_list.sort(key=get_sort_key)
    
    # Format events list by grouping them by day
    # e.g. [{"date": "2026-05-30", "label": "Today", "events": [...]}]
    days_dict = {}
    today = datetime.date.today()
    for ev in events_list:
        d = ev["date_obj"]
        date_str = d.strftime("%Y-%m-%d")
        if date_str not in days_dict:
            # format date label nicely
            if d == today:
                label = "Today"
            elif d == today + datetime.timedelta(days=1):
                label = "Tomorrow"
            else:
                label = d.strftime("%A, %b %d")
            days_dict[date_str] = {
                "date": date_str,
                "label": label,
                "events": []
            }
        days_dict[date_str]["events"].append(ev)
        
    grouped_events = list(days_dict.values())
    grouped_events.sort(key=lambda x: x["date"])
    
    CALENDAR_CACHE["events"] = grouped_events
    CALENDAR_CACHE["last_fetched"] = now
    return grouped_events


# Initialize FastAPI App
app = FastAPI(
    title="HearthOps API",
    description="Backend engine for family routine automation and token economy.",
    version="0.1.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static Files & Templates
# In Docker, main.py is in /app, and frontend is in /app/frontend
# Locally, main.py is in backend/, and frontend is a sibling of backend/
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.exists(os.path.join(CURRENT_DIR, "..", "frontend")):
    # Local dev structure
    FRONTEND_DIR = os.path.join(CURRENT_DIR, "..", "frontend")
else:
    # Docker or alternative structure where frontend might be a sibling in the same dir
    FRONTEND_DIR = os.path.join(CURRENT_DIR, "frontend")

import random

templates = Jinja2Templates(directory=os.path.join(FRONTEND_DIR, "templates"))

def jinja_shuffle(l):
    try:
        aux = list(l)
        random.shuffle(aux)
        return aux
    except Exception:
        return l

templates.env.filters["shuffle"] = jinja_shuffle
app.mount("/static", StaticFiles(directory=os.path.join(FRONTEND_DIR, "static")), name="static")

# --- Models ---

class VerifyRequest(BaseModel):
    name: str
    pin: str

class UserResponse(BaseModel):
    id: int
    name: str
    token_balance: float

class ChoreCompleteRequest(BaseModel):
    chore_id: int
    user_id: int
    pin: str

# --- Utilities ---

def hash_pin(pin: str) -> str:
    """Hashes a 4-digit PIN using SHA-256."""
    return hashlib.sha256(pin.encode()).hexdigest()

# --- UI Endpoints (HTMX) ---

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serves the main PIN entry page with ticker and calendar support."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, is_parent FROM users ORDER BY name")
        users = cursor.fetchall()
        
        # Ticker: Last 5 chores completed by ANYONE today
        cursor.execute(
            """
            SELECT u.name, c.title, strftime('%H:%M', l.completed_at, 'localtime') as time_str
            FROM chore_logs l
            JOIN users u ON l.user_id = u.id
            JOIN chores c ON l.chore_id = c.id
            WHERE date(l.completed_at, 'localtime') = date('now', 'localtime')
            AND l.action_type = 'earn'
            ORDER BY l.completed_at DESC
            LIMIT 5
            """
        )
        ticker_items = cursor.fetchall()
        
    # Fetch calendar events for the landing page
    try:
        calendar_days = fetch_and_parse_calendars()
    except Exception as e:
        logger.error(f"Error loading calendars: {e}")
        calendar_days = []
        
    return templates.TemplateResponse(request, "index.html", {
        "users": users,
        "ticker": ticker_items,
        "calendar_days": calendar_days
    })

def get_admin_data(cursor):
    """Helper to fetch all details for admin snippet updates."""
    cursor.execute("SELECT id, name, token_balance FROM users ORDER BY name")
    users = cursor.fetchall()
    
    cursor.execute("SELECT id, title, description, category, frequency, value_credits, max_daily_completions, is_active FROM chores ORDER BY category, title")
    chores = cursor.fetchall()
    
    chore_list = []
    for chore in chores:
        cursor.execute("SELECT user_id FROM chore_assignments WHERE chore_id = ?", (chore["id"],))
        assigned_ids = [row["user_id"] for row in cursor.fetchall()]
        chore_dict = dict(chore)
        chore_dict["assigned_user_ids"] = assigned_ids
        chore_list.append(chore_dict)
    
    # Fetch recent transactions to display as an audit log
    cursor.execute(
        """
        SELECT t.id, u.name, t.amount, t.category, t.description, t.created_at 
        FROM token_transactions t
        JOIN users u ON t.user_id = u.id
        ORDER BY t.created_at DESC LIMIT 15
        """
    )
    transactions = cursor.fetchall()
    
    # Fetch google calendars
    cursor.execute("SELECT id, name, ical_url, color FROM google_calendars ORDER BY name")
    google_calendars = cursor.fetchall()
    
    return users, chore_list, transactions, google_calendars

@app.post("/api/admin-verify", response_class=HTMLResponse)
async def admin_verify(request: Request):
    """Verifies Admin PIN (any user with is_parent = 1) and returns the admin dashboard."""
    pin = request.headers.get("HX-Prompt")
    if not pin:
        return HTMLResponse(content='<div class="alert alert-error">Admin PIN required.</div>')
    
    hashed_input = hash_pin(pin)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Allow any user marked as a parent to access admin
        cursor.execute(
            "SELECT name FROM users WHERE pin_hash = ? AND is_parent = 1",
            (hashed_input,)
        )
        admin = cursor.fetchone()
        
        if not admin:
            return HTMLResponse(content='<div class="alert alert-error">Access Denied.</div>')
        
        users, chores, transactions, google_calendars = get_admin_data(cursor)
        
        return templates.TemplateResponse(request, "admin_snippet.html", {
            "users": users,
            "chores": chores,
            "transactions": transactions,
            "google_calendars": google_calendars
        })

@app.post("/api/admin/ledger/reset", response_class=HTMLResponse)
async def admin_reset_ledger(request: Request, user_id: int = Form(...)):
    """Resets a user's token balance to 0 and records the transaction."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("BEGIN TRANSACTION;")
            cursor.execute("SELECT name, token_balance FROM users WHERE id = ?", (user_id,))
            user = cursor.fetchone()
            
            if user:
                # Log adjustment transaction
                cursor.execute(
                    "INSERT INTO token_transactions (user_id, amount, category, description) VALUES (?, ?, 'adjust', ?)",
                    (user_id, -user["token_balance"], f"Manual reset of token balance by admin.")
                )
                cursor.execute("UPDATE users SET token_balance = 0.0 WHERE id = ?", (user_id,))
                conn.commit()
                msg = f"Reset balance for {user['name']} to 0."
            else:
                conn.rollback()
                msg = "User not found."
        except Exception as e:
            conn.rollback()
            msg = f"Error: {str(e)}"
            
        users, chores, transactions, google_calendars = get_admin_data(cursor)
        return templates.TemplateResponse(request, "admin_snippet.html", {
            "users": users,
            "chores": chores,
            "transactions": transactions,
            "google_calendars": google_calendars,
            "message": msg
        })

@app.post("/api/admin/ledger/adjust", response_class=HTMLResponse)
async def admin_adjust_ledger(request: Request, user_id: int = Form(...), amount: float = Form(...), description: str = Form("")):
    """Adjusts (positive or negative) a user's token balance."""
    category = "spend" if amount < 0 else "adjust"
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("BEGIN TRANSACTION;")
            cursor.execute("SELECT name FROM users WHERE id = ?", (user_id,))
            user = cursor.fetchone()
            
            if user:
                cursor.execute(
                    "INSERT INTO token_transactions (user_id, amount, category, description) VALUES (?, ?, ?, ?)",
                    (user_id, amount, category, description or f"Admin adjustment ({amount:+})")
                )
                cursor.execute("UPDATE users SET token_balance = token_balance + ? WHERE id = ?", (amount, user_id))
                conn.commit()
                msg = f"Adjusted {user['name']} balance by {amount:+} credits."
            else:
                conn.rollback()
                msg = "User not found."
        except Exception as e:
            conn.rollback()
            msg = f"Error: {str(e)}"
            
        users, chores, transactions, google_calendars = get_admin_data(cursor)
        return templates.TemplateResponse(request, "admin_snippet.html", {
            "users": users,
            "chores": chores,
            "transactions": transactions,
            "google_calendars": google_calendars,
            "message": msg
        })

@app.post("/api/admin/users/reset-pin", response_class=HTMLResponse)
async def admin_reset_user_pin(request: Request, user_id: int = Form(...), new_pin: str = Form(...)):
    """Resets a family member's PIN from the admin dashboard."""
    if not new_pin.isdigit() or len(new_pin) != 4:
        return HTMLResponse(content='<div class="alert alert-error">PIN must be exactly 4 digits.</div>')
    
    hashed_pin = hash_pin(new_pin)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE users SET pin_hash = ? WHERE id = ?", (hashed_pin, user_id))
            conn.commit()
            cursor.execute("SELECT name FROM users WHERE id = ?", (user_id,))
            user = cursor.fetchone()
            msg = f"Reset PIN for {user['name']} successfully."
        except Exception as e:
            msg = f"Error: {str(e)}"
            
        users, chores, transactions, google_calendars = get_admin_data(cursor)
        return templates.TemplateResponse(request, "admin_snippet.html", {
            "users": users,
            "chores": chores,
            "transactions": transactions,
            "google_calendars": google_calendars,
            "message": msg
        })

@app.post("/api/admin/chores/toggle/{chore_id}", response_class=HTMLResponse)
async def admin_toggle_chore(request: Request, chore_id: int):
    """Toggles a chore's active status from the admin panel."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE chores SET is_active = 1 - is_active WHERE id = ?", (chore_id,))
        conn.commit()
        
        users, chores, transactions, google_calendars = get_admin_data(cursor)
            
        return templates.TemplateResponse(request, "admin_snippet.html", {
            "users": users,
            "chores": chores,
            "transactions": transactions,
            "google_calendars": google_calendars,
            "message": "Chore status updated."
        })

@app.post("/api/admin/chores/update", response_class=HTMLResponse)
async def admin_update_chore(
    request: Request, 
    chore_id: int = Form(...), 
    title: str = Form(...),
    description: str = Form(...),
    category: str = Form(...),
    frequency: str = Form(...),
    value_credits: float = Form(...),
    max_daily_completions: int = Form(1),
    assigned_user_ids: List[int] = Form([])
):
    """Updates all fields for a specific chore, including multi-user assignments."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("BEGIN TRANSACTION;")
            cursor.execute(
                """
                UPDATE chores 
                SET title = ?, description = ?, category = ?, frequency = ?, value_credits = ?, max_daily_completions = ? 
                WHERE id = ?
                """, 
                (title, description, category, frequency, value_credits, max_daily_completions, chore_id)
            )
            
            # Update Assignments: Clear old and insert new
            cursor.execute("DELETE FROM chore_assignments WHERE chore_id = ?", (chore_id,))
            for user_id in assigned_user_ids:
                cursor.execute("INSERT INTO chore_assignments (chore_id, user_id) VALUES (?, ?)", (chore_id, user_id))
            
            conn.commit()
            msg = f"Updated: {title}"
        except Exception as e:
            conn.rollback()
            msg = f"Error: {str(e)}"
        
        users, chores, transactions, google_calendars = get_admin_data(cursor)
        
        return templates.TemplateResponse(request, "admin_snippet.html", {
            "users": users,
            "chores": chores,
            "transactions": transactions,
            "google_calendars": google_calendars,
            "message": msg
        })

def render_dashboard(request: Request, user_id: int, cursor, message: Optional[str] = None, error: Optional[str] = None):
    """Gathers all dashboard state and returns the dashboard snippet."""
    # 1. Fetch user
    cursor.execute("SELECT id, name, token_balance, pin_hash FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # 2. Leaderboard (Top earners in last 7 days)
    cursor.execute(
        """
        SELECT u.name, SUM(c.value_credits) as total_earned
        FROM users u
        JOIN chore_logs l ON u.id = l.user_id
        JOIN chores c ON l.chore_id = c.id
        WHERE l.action_type = 'earn'
        AND date(l.completed_at, 'localtime') >= date('now', '-7 days', 'localtime')
        GROUP BY u.id
        ORDER BY total_earned DESC
        """
    )
    leaderboard = cursor.fetchall()

    # 3. Daily progress
    cursor.execute(
        """
        SELECT COUNT(*) as completed_today
        FROM chore_logs
        WHERE user_id = ? 
        AND action_type = 'earn'
        AND date(completed_at, 'localtime') = date('now', 'localtime')
        """,
        (user_id,)
    )
    progress = cursor.fetchone()
    completed_today = progress["completed_today"] if progress else 0

    # 4. Available chores (Personal + Shared chores)
    cursor.execute(
        """
        SELECT c.id, c.title, c.description, c.category, c.frequency, c.value_credits, c.max_daily_completions, c.is_required, c.is_shared,
               (SELECT COUNT(*) FROM chore_assignments WHERE chore_id = c.id) as is_assigned
        FROM chores c
        WHERE c.is_active = 1 
        AND (
            c.is_shared = 1
            OR NOT EXISTS (SELECT 1 FROM chore_assignments WHERE chore_id = c.id)
            OR EXISTS (SELECT 1 FROM chore_assignments WHERE chore_id = c.id AND user_id = ?)
        )
        AND (
            c.frequency = 'adhoc'
            OR (
                (c.is_shared = 1 AND (SELECT COUNT(*) FROM chore_logs WHERE chore_id = c.id AND user_id = ? AND action_type = 'earn' AND date(completed_at, 'localtime') = date('now', 'localtime')) < c.max_daily_completions)
                OR (c.is_shared = 0 AND (SELECT COUNT(*) FROM chore_logs WHERE chore_id = c.id AND action_type = 'earn' AND date(completed_at, 'localtime') = date('now', 'localtime')) < c.max_daily_completions)
            )
            OR (c.frequency = 'weekly' AND (
                (c.is_shared = 1 AND NOT EXISTS (
                    SELECT 1 FROM chore_logs 
                    WHERE chore_id = c.id AND user_id = ?
                    AND action_type = 'earn'
                    AND date(completed_at, 'localtime', 'weekday 0', '-7 days') = date('now', 'localtime', 'weekday 0', '-7 days')
                ))
                OR (c.is_shared = 0 AND NOT EXISTS (
                    SELECT 1 FROM chore_logs 
                    WHERE chore_id = c.id 
                    AND action_type = 'earn'
                    AND date(completed_at, 'localtime', 'weekday 0', '-7 days') = date('now', 'localtime', 'weekday 0', '-7 days')
                ))
            ))
        )
        ORDER BY c.category, c.title
        """,
        (user_id, user_id, user_id)
    )
    available_chores = cursor.fetchall()

    # Populate other assignees for personal chores
    available_list = []
    for chore in available_chores:
        chore_dict = dict(chore)
        if chore["is_assigned"] > 0:
            cursor.execute(
                "SELECT u.name FROM chore_assignments a JOIN users u ON a.user_id = u.id WHERE a.chore_id = ? AND a.user_id != ?",
                (chore["id"], user_id)
            )
            others = [row["name"] for row in cursor.fetchall()]
            chore_dict["other_assignees"] = others
        else:
            chore_dict["other_assignees"] = []
        available_list.append(chore_dict)

    # 5. Completed Chores (Grayed out) today
    cursor.execute(
        """
        SELECT DISTINCT c.id, c.title, c.description, c.category, c.value_credits, u.name as done_by
        FROM chores c
        JOIN chore_logs l ON c.id = l.chore_id
        JOIN users u ON l.user_id = u.id
        WHERE date(l.completed_at, 'localtime') = date('now', 'localtime')
        AND l.action_type = 'earn'
        AND c.frequency != 'adhoc'
        AND (
            (c.is_shared = 1 AND l.user_id = ?)
            OR (c.is_shared = 0 AND (
                (SELECT COUNT(*) FROM chore_logs WHERE chore_id = c.id AND action_type = 'earn' AND date(completed_at, 'localtime') = date('now', 'localtime')) >= c.max_daily_completions
                OR c.frequency = 'weekly'
            ))
        )
        """,
        (user_id,)
    )
    completed_chores = cursor.fetchall()

    # 6. Recent logs for undo logic
    cursor.execute(
        """
        SELECT l.id as log_id, c.title, c.value_credits, l.completed_at
        FROM chore_logs l
        JOIN chores c ON l.chore_id = c.id
        WHERE l.user_id = ?
        AND l.action_type = 'earn'
        AND datetime(l.completed_at) >= datetime('now', '-15 minutes')
        ORDER BY l.completed_at DESC
        """,
        (user_id,)
    )
    recent_completes = cursor.fetchall()

    # 7. Ticker (last 5 completions today)
    cursor.execute(
        """
        SELECT u.name, c.title, strftime('%H:%M', l.completed_at, 'localtime') as time_str
        FROM chore_logs l
        JOIN users u ON l.user_id = u.id
        JOIN chores c ON l.chore_id = c.id
        WHERE date(l.completed_at, 'localtime') = date('now', 'localtime')
        AND l.action_type = 'earn'
        ORDER BY l.completed_at DESC
        LIMIT 5
        """
    )
    ticker_items = cursor.fetchall()

    # 8. Encouragements (Kudos)
    cursor.execute(
        """
        SELECT e.id, u.name as sender_name, e.content, e.is_read, e.created_at
        FROM encouragements e
        JOIN users u ON e.sender_id = u.id
        WHERE e.recipient_id = ?
        ORDER BY e.created_at DESC
        """,
        (user_id,)
    )
    encouragements = cursor.fetchall()
    has_new_encouragement = any(not enc["is_read"] for enc in encouragements)

    return templates.TemplateResponse(request, "dashboard_snippet.html", {
        "user": user, 
        "chores": available_list,
        "completed_chores": completed_chores,
        "recent_completes": recent_completes,
        "ticker": ticker_items,
        "leaderboard": leaderboard,
        "completed_today": completed_today,
        "encouragements": encouragements,
        "has_new_encouragement": has_new_encouragement,
        "message": message,
        "error": error
    })

@app.post("/api/verify-ui", response_class=HTMLResponse)
async def verify_ui(request: Request, name: str = Form(...), pin: str = Form(...)):
    """Handles PIN verification from the UI and returns the chore list or error."""
    hashed_input = hash_pin(pin)
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, token_balance, pin_hash FROM users WHERE name = ?",
            (name,)
        )
        user = cursor.fetchone()
        
        if not user or user["pin_hash"] != hashed_input:
            cursor.execute("SELECT id, name, is_parent FROM users ORDER BY name")
            users = cursor.fetchall()
            return templates.TemplateResponse(request, "login_snippet.html", {
                "users": users,
                "selected_name": name,
                "error": "Invalid PIN. Try again."
            })
        
        return render_dashboard(request, user["id"], cursor)


@app.post("/api/chores/complete-ui", response_class=HTMLResponse)
async def complete_chore_ui(
    request: Request, 
    chore_id: int = Form(...), 
    user_id: int = Form(...)
):
    """Handles chore completion from the UI via HTMX prompt."""
    pin = request.headers.get("HX-Prompt")
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, pin_hash, token_balance FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        
        if not pin or hash_pin(pin) != user["pin_hash"]:
             return HTMLResponse(content='<div class="alert alert-error">Invalid PIN.</div>', status_code=401)
            
        try:
            cursor.execute("SELECT value_credits, title, is_required FROM chores WHERE id = ?", (chore_id,))
            chore = cursor.fetchone()
            if not chore:
                return HTMLResponse(content='<div class="alert alert-error">Chore not found.</div>', status_code=404)

            # Constraint: Block non-required chores if there are uncompleted required chores today
            if chore["is_required"] == 0:
                cursor.execute(
                    """
                    SELECT c.id, c.title, c.is_shared
                    FROM chores c
                    WHERE c.is_active = 1
                    AND c.is_required = 1
                    AND (
                        c.is_shared = 1
                        OR NOT EXISTS (SELECT 1 FROM chore_assignments WHERE chore_id = c.id)
                        OR EXISTS (SELECT 1 FROM chore_assignments WHERE chore_id = c.id AND user_id = ?)
                    )
                    """,
                    (user_id,)
                )
                required_chores = cursor.fetchall()
                
                uncompleted_required = []
                for req in required_chores:
                    if req["is_shared"] == 1:
                        cursor.execute(
                            """
                            SELECT 1 FROM chore_logs
                            WHERE chore_id = ? AND user_id = ?
                            AND action_type = 'earn'
                            AND date(completed_at, 'localtime') = date('now', 'localtime')
                            """,
                            (req["id"], user_id)
                        )
                    else:
                        cursor.execute(
                            """
                            SELECT 1 FROM chore_logs
                            WHERE chore_id = ?
                            AND action_type = 'earn'
                            AND date(completed_at, 'localtime') = date('now', 'localtime')
                            """,
                            (req["id"],)
                        )
                    if not cursor.fetchone():
                        uncompleted_required.append(req["title"])
                
                if uncompleted_required:
                    return render_dashboard(
                        request, 
                        user_id, 
                        cursor, 
                        error=f"Complete required chores first: {', '.join(uncompleted_required)}!"
                    )

            cursor.execute("BEGIN TRANSACTION;")
            # Record log with delta
            cursor.execute(
                "INSERT INTO chore_logs (chore_id, user_id, action_type, credits_delta) VALUES (?, ?, 'earn', ?)", 
                (chore_id, user_id, chore["value_credits"])
            )
            cursor.execute("UPDATE users SET token_balance = token_balance + ? WHERE id = ?", (chore["value_credits"], user_id))
            conn.commit()
            
            return render_dashboard(request, user_id, cursor, message=f"Success! Earned {chore['value_credits']} credits.")
        except Exception as e:
            if conn: conn.rollback()
            return HTMLResponse(content=f"Error: {str(e)}", status_code=500)

@app.post("/api/chores/undo-ui", response_class=HTMLResponse)
async def undo_chore_ui(
    request: Request,
    log_id: int = Form(...),
    user_id: int = Form(...)
):
    """Handles undoing a completed chore within the last 15 minutes."""
    pin = request.headers.get("HX-Prompt")
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, pin_hash, name FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        
        if not pin or hash_pin(pin) != user["pin_hash"]:
             return HTMLResponse(content='<div class="alert alert-error">Invalid PIN.</div>', status_code=401)
             
        try:
            cursor.execute("BEGIN TRANSACTION;")
            cursor.execute("SELECT chore_id, credits_delta FROM chore_logs WHERE id = ? AND user_id = ?", (log_id, user_id))
            log_item = cursor.fetchone()
            
            if log_item:
                # Deduct credits
                cursor.execute("UPDATE users SET token_balance = token_balance - ? WHERE id = ?", (log_item["credits_delta"], user_id))
                # Mark as undo
                cursor.execute("UPDATE chore_logs SET action_type = 'undo' WHERE id = ?", (log_id,))
                conn.commit()
                msg = "Chore completion reversed."
                err = None
            else:
                conn.rollback()
                msg = None
                err = "Log entry not found."
                
            return render_dashboard(request, user_id, cursor, message=msg, error=err)
        except Exception as e:
            if conn: conn.rollback()
            return HTMLResponse(content=f"Error: {str(e)}", status_code=500)

@app.post("/api/user/change-pin", response_class=HTMLResponse)
async def user_change_pin_ui(
    request: Request,
    user_id: int = Form(...),
    old_pin: str = Form(...),
    new_pin: str = Form(...)
):
    """Allows kids/family members to change their own 4-digit PIN."""
    if len(new_pin) != 4 or not new_pin.isdigit():
        return HTMLResponse(content='<div class="alert alert-error">New PIN must be exactly 4 digits.</div>', status_code=400)
        
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, pin_hash FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        
        if not user or hash_pin(old_pin) != user["pin_hash"]:
            return HTMLResponse(content='<div class="alert alert-error">Incorrect current PIN.</div>', status_code=401)
            
        try:
            cursor.execute("UPDATE users SET pin_hash = ? WHERE id = ?", (hash_pin(new_pin), user_id))
            conn.commit()
            return render_dashboard(request, user_id, cursor, message="PIN updated successfully!")
        except Exception as e:
            return HTMLResponse(content=f"Error changing PIN: {str(e)}", status_code=500)

@app.post("/api/encouragements", response_class=HTMLResponse)
async def create_encouragement_ui(
    request: Request,
    sender_id: int = Form(...),
    recipient_id: int = Form(...),
    pin: str = Form(...),
    content: str = Form(...)
):
    """Saves an encouragement note (Kudo) from one family member to another."""
    if len(content.strip()) == 0 or len(content) > 140:
        return HTMLResponse(content='<div class="alert alert-error">Message must be between 1 and 140 characters.</div>', status_code=400)
        
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT pin_hash FROM users WHERE id = ?", (sender_id,))
        sender = cursor.fetchone()
        
        if not sender or hash_pin(pin) != sender["pin_hash"]:
            return HTMLResponse(content='<div class="alert alert-error">Invalid sender PIN.</div>', status_code=401)
            
        if int(sender_id) == int(recipient_id):
            return HTMLResponse(content='<div class="alert alert-error">You cannot leave a Kudo for yourself.</div>', status_code=400)
            
        try:
            cursor.execute(
                "INSERT INTO encouragements (sender_id, recipient_id, content) VALUES (?, ?, ?)",
                (sender_id, recipient_id, content.strip())
            )
            conn.commit()
            return HTMLResponse(content='<div class="alert alert-success">Kudo Boost sent successfully! ✨</div>')
        except Exception as e:
            return HTMLResponse(content=f'<div class="alert alert-error">Error: {str(e)}</div>', status_code=500)

@app.post("/api/encouragements/read", response_class=HTMLResponse)
async def read_encouragement_ui(
    request: Request,
    encouragement_id: int = Form(...),
    user_id: int = Form(...)
):
    """Marks an encouragement note as read/dismissed."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE encouragements SET is_read = 1, read_at = CURRENT_TIMESTAMP WHERE id = ? AND recipient_id = ?",
                (encouragement_id, user_id)
            )
            conn.commit()
            return render_dashboard(request, user_id, cursor, message="Kudo marked as read.")
        except Exception as e:
            return HTMLResponse(content=f"Error: {str(e)}", status_code=500)

@app.post("/api/admin/bonus", response_class=HTMLResponse)
async def admin_award_bonus_ui(
    request: Request,
    target_user_id: int = Form(...),
    amount: float = Form(...),
    description: str = Form(...),
    admin_pin: str = Form(...)
):
    """Awards a custom bonus (credits adjustment) to a user from the Admin console."""
    hashed_pin = hash_pin(admin_pin)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, pin_hash FROM users WHERE is_parent = 1")
        admins = cursor.fetchall()
        valid_admin = any(hashed_pin == admin["pin_hash"] for admin in admins)
        
        if not valid_admin:
            users, chores, transactions, google_calendars = get_admin_data(cursor)
            return templates.TemplateResponse(request, "admin_snippet.html", {
                "users": users,
                "chores": chores,
                "transactions": transactions,
                "google_calendars": google_calendars,
                "error": "Invalid Admin PIN. Action aborted."
            })
            
        try:
            cursor.execute("BEGIN TRANSACTION;")
            cursor.execute(
                "INSERT INTO token_transactions (user_id, amount, category, description) VALUES (?, ?, 'adjust', ?)",
                (target_user_id, amount, description)
            )
            cursor.execute(
                "UPDATE users SET token_balance = token_balance + ? WHERE id = ?",
                (amount, target_user_id)
            )
            conn.commit()
            msg = f"Successfully awarded 🪙 {amount} to user."
            err = None
        except Exception as e:
            conn.rollback()
            msg = None
            err = f"Database error: {str(e)}"
            
        users, chores, transactions, google_calendars = get_admin_data(cursor)
        return templates.TemplateResponse(request, "admin_snippet.html", {
            "users": users,
            "chores": chores,
            "transactions": transactions,
            "google_calendars": google_calendars,
            "message": msg,
            "error": err
        })

@app.post("/api/admin/calendars/test", response_class=HTMLResponse)
async def admin_test_calendar(ical_url: str = Form(...)):
    """Fetches and parses the given URL to verify it's a valid iCal feed."""
    try:
        response = requests.get(ical_url, timeout=5)
        if response.status_code != 200:
            return HTMLResponse(
                content=f'<span style="color: var(--error);">❌ Failed: Server returned HTTP status {response.status_code}</span>'
            )
            
        ical_data = response.text
        if "BEGIN:VCALENDAR" not in ical_data:
            return HTMLResponse(
                content='<span style="color: var(--error);">❌ Failed: Response is not a valid iCal feed (missing BEGIN:VCALENDAR)</span>'
            )
            
        ical_calendar = Calendar.from_ical(ical_data)
        start_date = datetime.date.today()
        end_date = datetime.date.today() + datetime.timedelta(days=7)
        ical_events = recurring_ical_events.of(ical_calendar).between(start_date, end_date)
        
        events_count = len(ical_events)
        summaries = [str(e.get("SUMMARY", "No Title")) for e in ical_events[:3]]
        
        summary_str = ", ".join([f"'{s}'" for s in summaries])
        if events_count > 3:
            summary_str += "..."
            
        if events_count > 0:
            msg = f"✅ Success! Connected and found {events_count} events in the next 7 days: {summary_str}"
        else:
            msg = "✅ Success! Connected successfully, but found 0 events in the next 7 days."
            
        return HTMLResponse(content=f'<span style="color: var(--success);">{msg}</span>')
    except Exception as e:
        return HTMLResponse(content=f'<span style="color: var(--error);">❌ Error: {str(e)}</span>')

@app.post("/api/admin/calendars/add", response_class=HTMLResponse)
async def admin_add_calendar(
    request: Request,
    name: str = Form(...),
    color: str = Form(...),
    ical_url: str = Form(...)
):
    """Links a new Google Calendar secret iCal URL."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO google_calendars (name, ical_url, color) VALUES (?, ?, ?)",
                (name, ical_url, color)
            )
            conn.commit()
            # Invalidate calendar cache
            global CALENDAR_CACHE
            CALENDAR_CACHE["last_fetched"] = None
            msg = f"Successfully linked calendar: {name}"
            err = None
        except Exception as e:
            msg = None
            err = f"Database error: {str(e)}"
            
        users, chores, transactions, google_calendars = get_admin_data(cursor)
        return templates.TemplateResponse(request, "admin_snippet.html", {
            "users": users,
            "chores": chores,
            "transactions": transactions,
            "google_calendars": google_calendars,
            "message": msg,
            "error": err
        })

@app.post("/api/admin/calendars/delete/{calendar_id}", response_class=HTMLResponse)
async def admin_delete_calendar(request: Request, calendar_id: int):
    """Deletes a linked Google Calendar."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM google_calendars WHERE id = ?", (calendar_id,))
            conn.commit()
            # Invalidate calendar cache
            global CALENDAR_CACHE
            CALENDAR_CACHE["last_fetched"] = None
            msg = "Deleted calendar connection."
            err = None
        except Exception as e:
            msg = None
            err = f"Database error: {str(e)}"
            
        users, chores, transactions, google_calendars = get_admin_data(cursor)
        return templates.TemplateResponse(request, "admin_snippet.html", {
            "users": users,
            "chores": chores,
            "transactions": transactions,
            "google_calendars": google_calendars,
            "message": msg,
            "error": err
        })

# --- JSON API Endpoints ---

@app.on_event("startup")
def startup_event():
    """Actions to run on server startup."""
    logger.info("Starting up HearthOps API...")
    init_db()

@app.get("/health")
def health_check():
    """Standard health check endpoint."""
    return {"status": "healthy", "service": "hearth-ops-backend"}

@app.post("/api/verify", response_model=UserResponse)
def verify_user(request: VerifyRequest):
    """Verifies a user's identity via their 4-digit PIN."""
    hashed_input = hash_pin(request.pin)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, token_balance, pin_hash FROM users WHERE name = ?", (request.name,))
        user = cursor.fetchone()
        if not user or user["pin_hash"] != hashed_input:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return {"id": user["id"], "name": user["name"], "token_balance": user["token_balance"]}

@app.post("/api/chores/complete")
def complete_chore(request: ChoreCompleteRequest):
    """Records a completed chore and updates balance."""
    hashed_input = hash_pin(request.pin)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT pin_hash, name FROM users WHERE id = ?", (request.user_id,))
        user = cursor.fetchone()
        if not user or user["pin_hash"] != hashed_input:
            raise HTTPException(status_code=401, detail="Invalid PIN")
        cursor.execute("SELECT value_credits, title FROM chores WHERE id = ? AND is_active = 1", (request.chore_id,))
        chore = cursor.fetchone()
        if not chore:
            raise HTTPException(status_code=404, detail="Chore not found")
        try:
            cursor.execute("BEGIN TRANSACTION;")
            cursor.execute("INSERT INTO chore_logs (chore_id, user_id) VALUES (?, ?)", (request.chore_id, request.user_id))
            cursor.execute("UPDATE users SET token_balance = token_balance + ? WHERE id = ?", (chore["value_credits"], request.user_id))
            conn.commit()
            cursor.execute("SELECT token_balance FROM users WHERE id = ?", (request.user_id,))
            return {"status": "success", "new_balance": cursor.fetchone()["token_balance"]}
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("APP_PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
