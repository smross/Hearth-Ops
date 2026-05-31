import os
import logging
import hashlib
import requests
import datetime
import random
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

from zoneinfo import ZoneInfo
from datetime import datetime as dt_class, timezone as tz_class

def format_to_central_time(utc_datetime_str: str) -> str:
    """Converts UTC datetime string from SQLite to America/Chicago and formats as I:M AM/PM CT/CDT/CST."""
    try:
        # Handle cases with or without timezone info
        if " " in utc_datetime_str:
            clean_str = utc_datetime_str.replace(" ", "T")
        else:
            clean_str = utc_datetime_str
        
        if "+" not in clean_str and "Z" not in clean_str:
            clean_str += "+00:00"
            
        dt = dt_class.fromisoformat(clean_str.replace("Z", "+00:00"))
        central_tz = ZoneInfo("America/Chicago")
        central_dt = dt.astimezone(central_tz)
        time_str = central_dt.strftime("%I:%M %p").lstrip('0')
        tz_str = central_dt.strftime("%Z")
        return f"{time_str} {tz_str}"
    except Exception as e:
        logger.error(f"Error converting timezone: {e}")
        return utc_datetime_str

FAMILY_QUOTES = [
    "Why did the chore go to school? To clean up its act!",
    "Carpe Diem! A clean room is a clear mind. Which chore is next?",
    "What did the broom say to the vacuum? I'm so swept away by your work ethic!",
    "Every chore completed is a step closer to legendary status.",
    "Why did the dust bunny cross the road? To escape your cleaning skills!",
    "Cleanliness is next to... earning more tokens!",
    "Choose your chore, build your routine, earn your reward!",
    "What kind of head has no brain? A head of lettuce! Eat your veggies after chores!",
    "Why did the computer squeak? Because someone used a mouse! Clean your desk!",
    "Did you hear about the math teacher who was afraid of negative numbers? He'll stop at nothing to avoid them!",
    "The secret of getting ahead is getting started. Tackle a routine now!",
    "A little progress each day adds up to big results.",
    "Keep going! You're doing amazing helper work today.",
    "Teamwork makes the dream work. Help your family out today!",
    "What did one plate say to the other? Dinner is on me! Let's wipe the dining table!",
    "Your bed is a canvas, and you are the artist. Make it beautiful!",
    "Why did the sponge cross the sink? To get to the clean side!",
    "Work hard in silence, let your token balance make the noise!",
    "You can do it! Small habits lead to giant successes.",
    "Clean space, happy pace! Let's make it shine today!"
]

def get_mixed_ticker_items(cursor) -> List[str]:
    """Fetches completed chores today and mixes them with random motivational quotes/jokes."""
    # 1. Fetch completed chores
    cursor.execute(
        """
        SELECT u.name, c.title, l.completed_at
        FROM chore_logs l
        JOIN users u ON l.user_id = u.id
        JOIN chores c ON l.chore_id = c.id
        WHERE date(l.completed_at, 'localtime') = date('now', 'localtime')
        AND l.action_type = 'earn'
        ORDER BY l.completed_at DESC
        LIMIT 5
        """
    )
    chores = cursor.fetchall()
    
    ticker_items = []
    for row in chores:
        time_str = format_to_central_time(row["completed_at"])
        ticker_items.append(f"🎉 <strong>{row['name']}</strong> did <em>{row['title']}</em> at {time_str}")
        
    # 2. Select random quotes
    selected_quotes = random.sample(FAMILY_QUOTES, 5)
    for q in selected_quotes:
        ticker_items.append(f"✨ <strong>{q}</strong>")
        
    # 3. Shuffle them so they are nicely mixed
    random.shuffle(ticker_items)
    return ticker_items


# Cache to avoid calling Google servers on every page refresh
CALENDAR_CACHE = {
    "events": [],
    "last_fetched": None
}
CACHE_DURATION = datetime.timedelta(minutes=10)

def fetch_and_parse_calendars():
    global CALENDAR_CACHE
    now = datetime.datetime.now()
    central_tz = ZoneInfo("America/Chicago")
    now_central = datetime.datetime.now(central_tz)
    today = now_central.date()
    tomorrow = today + datetime.timedelta(days=1)
    
    # If cache is empty or stale, refetch and parse raw events
    if not CALENDAR_CACHE["last_fetched"] or (now - CALENDAR_CACHE["last_fetched"]) >= CACHE_DURATION:
        events_list = []
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, ical_url, color FROM google_calendars")
            calendars = cursor.fetchall()
            
        start_date = today
        end_date = today + datetime.timedelta(days=3)
        
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
                        
                        if not end:
                            end = start
                            
                        # start and end can be date or datetime
                        all_day = not isinstance(start, datetime.datetime)
                        
                        if all_day:
                            start_date_obj = start
                            start_dt = start
                            end_dt = end
                            start_str = start.strftime("%Y-%m-%d")
                        else:
                            if start.tzinfo is not None:
                                start_dt = start.astimezone(central_tz)
                            else:
                                start_dt = start.replace(tzinfo=central_tz)
                                
                            if end.tzinfo is not None:
                                end_dt = end.astimezone(central_tz)
                            else:
                                end_dt = end.replace(tzinfo=central_tz)
                                
                            time_str = start_dt.strftime("%I:%M %p").lstrip('0')
                            tz_str = start_dt.strftime("%Z")
                            start_str = f"{time_str} {tz_str}"
                            start_date_obj = start_dt.date()
                            
                        events_list.append({
                            "summary": summary,
                            "start": start_str,
                            "all_day": all_day,
                            "calendar_name": cal["name"],
                            "color": cal["color"],
                            "date_obj": start_date_obj,
                            "start_dt": start_dt,
                            "end_dt": end_dt
                        })
            except Exception as e:
                logger.error(f"Error fetching calendar {cal['name']}: {e}")
                
        CALENDAR_CACHE["events"] = events_list
        CALENDAR_CACHE["last_fetched"] = now

    # Filter raw events dynamically
    raw_events = CALENDAR_CACHE["events"]
    filtered_events = []
    
    for ev in raw_events:
        # 1. Today and tomorrow only
        if ev["date_obj"] != today and ev["date_obj"] != tomorrow:
            continue
            
        # 2. Skip passed events (fall off when end time reached)
        if not ev["all_day"]:
            if now_central >= ev["end_dt"]:
                continue
                
        filtered_events.append(ev)
        
    # Sort events: all-day events first on their respective date, then timed events
    def get_sort_key(ev):
        d = ev["date_obj"]
        if ev["all_day"]:
            dt = datetime.datetime.combine(d, datetime.time.min).replace(tzinfo=central_tz)
            return (d, dt, 0)
        else:
            return (d, ev["start_dt"], 1)
            
    filtered_events.sort(key=get_sort_key)
    
    # 3. Compression flag if non-all-day events > 4
    non_all_day_count = sum(1 for ev in filtered_events if not ev["all_day"])
    compress_all_day = non_all_day_count > 4
    
    for ev in filtered_events:
        if ev["all_day"]:
            ev["compressed"] = compress_all_day
        else:
            ev["compressed"] = False
            
    # 4. Truncate events (LIMIT = 5)
    # Today's events are sorted first, so they naturally have priority.
    truncated_events = filtered_events[:5]
    
    # Group by day
    days_dict = {}
    for ev in truncated_events:
        d = ev["date_obj"]
        date_str = d.strftime("%Y-%m-%d")
        if date_str not in days_dict:
            if d == today:
                label = "Today"
            else:
                label = "Tomorrow"
            days_dict[date_str] = {
                "date": date_str,
                "label": label,
                "events": []
            }
        days_dict[date_str]["events"].append(ev)
        
    grouped_events = list(days_dict.values())
    grouped_events.sort(key=lambda x: x["date"])
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
templates.env.globals["app_env"] = os.getenv("APP_ENV", "production")
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
        cursor.execute(
            """
            SELECT u.id, u.name, u.is_parent, u.token_balance,
                   COALESCE((SELECT SUM(c.value_credits) FROM chore_logs l JOIN chores c ON l.chore_id = c.id WHERE l.user_id = u.id AND l.action_type = 'earn' AND date(l.completed_at, 'localtime') = date('now', 'localtime')), 0.0) as earned_today
            FROM users u
            ORDER BY u.name
            """
        )
        users = cursor.fetchall()
        
        # Ticker: Mixed chores and dad jokes/quotes
        ticker_items = get_mixed_ticker_items(cursor)

        # Fetch active announcements (visible on landing page if not acknowledged by all kids yet)
        cursor.execute(
            """
            SELECT a.id, a.title, a.content FROM announcements a
            WHERE a.is_active = 1
            AND EXISTS (
                SELECT 1 FROM users u
                WHERE u.is_parent = 0
                AND NOT EXISTS (
                    SELECT 1 FROM announcement_acknowledgments ack
                    WHERE ack.announcement_id = a.id AND ack.user_id = u.id
                )
            )
            ORDER BY a.created_at DESC
            """
        )
        active_announcements = cursor.fetchall()

        # Leaderboard (Top earners in last 7 days)
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
        
    # Fetch calendar events for the landing page
    try:
        calendar_days = fetch_and_parse_calendars()
    except Exception as e:
        logger.error(f"Error loading calendars: {e}")
        calendar_days = []
        
    return templates.TemplateResponse(request, "index.html", {
        "users": users,
        "ticker": ticker_items,
        "calendar_days": calendar_days,
        "active_announcements": active_announcements,
        "leaderboard": leaderboard
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
    transactions_list = []
    for tx in transactions:
        tx_dict = dict(tx)
        tx_dict["created_at"] = format_to_central_time(tx["created_at"])
        transactions_list.append(tx_dict)
    
    # Fetch google calendars
    cursor.execute("SELECT id, name, ical_url, color FROM google_calendars ORDER BY name")
    google_calendars = cursor.fetchall()
    
    # Fetch announcements
    cursor.execute("SELECT id, title, content, is_active, created_at FROM announcements ORDER BY created_at DESC")
    announcements = cursor.fetchall()
    announcements_list = []
    for ann in announcements:
        ann_dict = dict(ann)
        ann_dict["created_at"] = format_to_central_time(ann["created_at"])
        announcements_list.append(ann_dict)
    
    return users, chore_list, transactions_list, google_calendars, announcements_list

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
        
        users, chores, transactions, google_calendars, announcements = get_admin_data(cursor)
        
        return templates.TemplateResponse(request, "admin_snippet.html", {
            "users": users,
            "chores": chores,
            "transactions": transactions,
            "google_calendars": google_calendars,
            "announcements": announcements
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
            
        users, chores, transactions, google_calendars, announcements = get_admin_data(cursor)
        return templates.TemplateResponse(request, "admin_snippet.html", {
            "users": users,
            "chores": chores,
            "transactions": transactions,
            "google_calendars": google_calendars,
            "announcements": announcements,
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
            
        users, chores, transactions, google_calendars, announcements = get_admin_data(cursor)
        return templates.TemplateResponse(request, "admin_snippet.html", {
            "users": users,
            "chores": chores,
            "transactions": transactions,
            "google_calendars": google_calendars,
            "announcements": announcements,
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
            
        users, chores, transactions, google_calendars, announcements = get_admin_data(cursor)
        return templates.TemplateResponse(request, "admin_snippet.html", {
            "users": users,
            "chores": chores,
            "transactions": transactions,
            "google_calendars": google_calendars,
            "announcements": announcements,
            "message": msg
        })

@app.post("/api/admin/chores/toggle/{chore_id}", response_class=HTMLResponse)
async def admin_toggle_chore(request: Request, chore_id: int):
    """Toggles a chore's active status from the admin panel."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE chores SET is_active = 1 - is_active WHERE id = ?", (chore_id,))
        conn.commit()
        
        users, chores, transactions, google_calendars, announcements = get_admin_data(cursor)
            
        return templates.TemplateResponse(request, "admin_snippet.html", {
            "users": users,
            "chores": chores,
            "transactions": transactions,
            "google_calendars": google_calendars,
            "announcements": announcements,
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
        
        users, chores, transactions, google_calendars, announcements = get_admin_data(cursor)
        
        return templates.TemplateResponse(request, "admin_snippet.html", {
            "users": users,
            "chores": chores,
            "transactions": transactions,
            "google_calendars": google_calendars,
            "announcements": announcements,
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
    # 7. Ticker (mixed chores and quotes)
    ticker_items = get_mixed_ticker_items(cursor)

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
    encouragements_list = []
    for enc in encouragements:
        enc_dict = dict(enc)
        enc_dict["created_at"] = format_to_central_time(enc["created_at"])
        encouragements_list.append(enc_dict)
        
    has_new_encouragement = any(not enc["is_read"] for enc in encouragements)

    # 9. Pending announcements for acknowledgment modal
    cursor.execute(
        """
        SELECT a.id, a.title, a.content
        FROM announcements a
        WHERE a.is_active = 1
        AND NOT EXISTS (
            SELECT 1 FROM announcement_acknowledgments ack
            WHERE ack.announcement_id = a.id
            AND ack.user_id = ?
        )
        ORDER BY a.created_at ASC
        """,
        (user_id,)
    )
    pending_announcements = cursor.fetchall()

    return templates.TemplateResponse(request, "dashboard_snippet.html", {
        "user": user, 
        "chores": available_list,
        "completed_chores": completed_chores,
        "recent_completes": recent_completes,
        "ticker": ticker_items,
        "leaderboard": leaderboard,
        "completed_today": completed_today,
        "encouragements": encouragements_list,
        "has_new_encouragement": has_new_encouragement,
        "pending_announcements": pending_announcements,
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
            cursor.execute(
                """
                SELECT u.id, u.name, u.is_parent, u.token_balance,
                       COALESCE((SELECT SUM(c.value_credits) FROM chore_logs l JOIN chores c ON l.chore_id = c.id WHERE l.user_id = u.id AND l.action_type = 'earn' AND date(l.completed_at, 'localtime') = date('now', 'localtime')), 0.0) as earned_today
                FROM users u
                ORDER BY u.name
                """
            )
            users = cursor.fetchall()
            return templates.TemplateResponse(request, "login_snippet.html", {
                "users": users,
                "selected_name": name,
                "error": "Invalid PIN. Try again.",
                "standalone": True
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
            return HTMLResponse(content="""
                <div class="alert alert-success">Kudo Boost sent successfully! ✨</div>
                <script>
                    new Audio('https://assets.mixkit.co/active_storage/sfx/2568/2568-preview.mp3').play();
                    setTimeout(function() {
                        hideKudoModal();
                    }, 1200);
                </script>
            """)
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
            users, chores, transactions, google_calendars, announcements = get_admin_data(cursor)
            return templates.TemplateResponse(request, "admin_snippet.html", {
                "users": users,
                "chores": chores,
                "transactions": transactions,
                "google_calendars": google_calendars,
                "announcements": announcements,
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
            
        users, chores, transactions, google_calendars, announcements = get_admin_data(cursor)
        return templates.TemplateResponse(request, "admin_snippet.html", {
            "users": users,
            "chores": chores,
            "transactions": transactions,
            "google_calendars": google_calendars,
            "announcements": announcements,
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
            
        users, chores, transactions, google_calendars, announcements = get_admin_data(cursor)
        return templates.TemplateResponse(request, "admin_snippet.html", {
            "users": users,
            "chores": chores,
            "transactions": transactions,
            "google_calendars": google_calendars,
            "announcements": announcements,
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
            
        users, chores, transactions, google_calendars, announcements = get_admin_data(cursor)
        return templates.TemplateResponse(request, "admin_snippet.html", {
            "users": users,
            "chores": chores,
            "transactions": transactions,
            "google_calendars": google_calendars,
            "announcements": announcements,
            "message": msg,
            "error": err
        })

@app.post("/api/admin/calendars/update-color/{calendar_id}", response_class=HTMLResponse)
async def admin_update_calendar_color(
    request: Request,
    calendar_id: int,
    color: str = Form(...)
):
    """Updates the display color of a Google Calendar connection."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE google_calendars SET color = ? WHERE id = ?",
                (color, calendar_id)
            )
            conn.commit()
            # Invalidate calendar cache
            global CALENDAR_CACHE
            CALENDAR_CACHE["last_fetched"] = None
            msg = "Updated calendar display color."
            err = None
        except Exception as e:
            msg = None
            err = f"Database error: {str(e)}"
            
        users, chores, transactions, google_calendars, announcements = get_admin_data(cursor)
        return templates.TemplateResponse(request, "admin_snippet.html", {
            "users": users,
            "chores": chores,
            "transactions": transactions,
            "google_calendars": google_calendars,
            "announcements": announcements,
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


@app.post("/api/admin/announcements/add", response_class=HTMLResponse)
async def admin_add_announcement(
    request: Request,
    title: str = Form(...),
    content: str = Form(...)
):
    """Adds a new family announcement."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO announcements (title, content, is_active) VALUES (?, ?, 1)",
                (title, content)
            )
            conn.commit()
            msg = f"Posted announcement: {title}"
            err = None
        except Exception as e:
            msg = None
            err = f"Database error: {str(e)}"
            
        users, chores, transactions, google_calendars, announcements = get_admin_data(cursor)
        return templates.TemplateResponse(request, "admin_snippet.html", {
            "users": users,
            "chores": chores,
            "transactions": transactions,
            "google_calendars": google_calendars,
            "announcements": announcements,
            "message": msg,
            "error": err
        })

@app.post("/api/admin/announcements/toggle/{ann_id}", response_class=HTMLResponse)
async def admin_toggle_announcement(request: Request, ann_id: int):
    """Toggles an announcement's active status."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE announcements SET is_active = 1 - is_active WHERE id = ?", (ann_id,))
            conn.commit()
            msg = "Announcement status toggled."
            err = None
        except Exception as e:
            msg = None
            err = f"Database error: {str(e)}"
            
        users, chores, transactions, google_calendars, announcements = get_admin_data(cursor)
        return templates.TemplateResponse(request, "admin_snippet.html", {
            "users": users,
            "chores": chores,
            "transactions": transactions,
            "google_calendars": google_calendars,
            "announcements": announcements,
            "message": msg,
            "error": err
        })

@app.post("/api/admin/announcements/delete/{ann_id}", response_class=HTMLResponse)
async def admin_delete_announcement(request: Request, ann_id: int):
    """Deletes an announcement."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM announcements WHERE id = ?", (ann_id,))
            conn.commit()
            msg = "Deleted announcement."
            err = None
        except Exception as e:
            msg = None
            err = f"Database error: {str(e)}"
            
        users, chores, transactions, google_calendars, announcements = get_admin_data(cursor)
        return templates.TemplateResponse(request, "admin_snippet.html", {
            "users": users,
            "chores": chores,
            "transactions": transactions,
            "google_calendars": google_calendars,
            "announcements": announcements,
            "message": msg,
            "error": err
        })

@app.post("/api/announcements/acknowledge", response_class=HTMLResponse)
async def acknowledge_announcements(
    request: Request,
    user_id: int = Form(...),
    announcement_ids: List[int] = Form([])
):
    """Records user acknowledgments for announcements, then returns the dashboard."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("BEGIN TRANSACTION;")
            for ann_id in announcement_ids:
                cursor.execute(
                    "INSERT OR IGNORE INTO announcement_acknowledgments (announcement_id, user_id) VALUES (?, ?)",
                    (ann_id, user_id)
                )
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Error acknowledging announcements: {e}")
            
        return render_dashboard(request, user_id, cursor)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("APP_PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
