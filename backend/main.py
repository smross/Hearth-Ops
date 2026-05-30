import os
import logging
import hashlib
from typing import Optional, List
from pydantic import BaseModel
from fastapi import FastAPI, Depends, HTTPException, status, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from database import init_db, get_db_connection

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    """Serves the main PIN entry page with ticker support."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM users ORDER BY name")
        users = cursor.fetchall()
        
        # Ticker: Last 5 chores completed by ANYONE today
        cursor.execute(
            """
            SELECT u.name, c.title, strftime('%H:%M', l.completed_at) as time_str
            FROM chore_logs l
            JOIN users u ON l.user_id = u.id
            JOIN chores c ON l.chore_id = c.id
            WHERE date(l.completed_at) = date('now', 'localtime')
            AND l.action_type = 'earn'
            ORDER BY l.completed_at DESC
            LIMIT 5
            """
        )
        ticker_items = cursor.fetchall()
        
    return templates.TemplateResponse(request, "index.html", {
        "users": users,
        "ticker": ticker_items
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
    
    return users, chore_list, transactions

@app.post("/api/admin-verify", response_class=HTMLResponse)
async def admin_verify(request: Request):
    """Verifies Admin PIN (Shawn or Michelle) and returns the admin dashboard."""
    pin = request.headers.get("HX-Prompt")
    if not pin:
        return HTMLResponse(content='<div class="alert alert-error">Admin PIN required.</div>')
    
    hashed_input = hash_pin(pin)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Only Shawn and Michelle can access admin
        cursor.execute(
            "SELECT name FROM users WHERE pin_hash = ? AND (name = 'Shawn' OR name = 'Michelle')",
            (hashed_input,)
        )
        admin = cursor.fetchone()
        
        if not admin:
            return HTMLResponse(content='<div class="alert alert-error">Access Denied.</div>')
        
        users, chores, transactions = get_admin_data(cursor)
        
        return templates.TemplateResponse(request, "admin_snippet.html", {
            "users": users,
            "chores": chores,
            "transactions": transactions
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
            
        users, chores, transactions = get_admin_data(cursor)
        return templates.TemplateResponse(request, "admin_snippet.html", {
            "users": users,
            "chores": chores,
            "transactions": transactions,
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
            
        users, chores, transactions = get_admin_data(cursor)
        return templates.TemplateResponse(request, "admin_snippet.html", {
            "users": users,
            "chores": chores,
            "transactions": transactions,
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
            
        users, chores, transactions = get_admin_data(cursor)
        return templates.TemplateResponse(request, "admin_snippet.html", {
            "users": users,
            "chores": chores,
            "transactions": transactions,
            "message": msg
        })

@app.post("/api/admin/chores/toggle/{chore_id}", response_class=HTMLResponse)
async def admin_toggle_chore(request: Request, chore_id: int):
    """Toggles a chore's active status from the admin panel."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE chores SET is_active = 1 - is_active WHERE id = ?", (chore_id,))
        conn.commit()
        
        users, chores, transactions = get_admin_data(cursor)
            
        return templates.TemplateResponse(request, "admin_snippet.html", {
            "users": users,
            "chores": chores,
            "transactions": transactions,
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
        
        users, chores, transactions = get_admin_data(cursor)
        
        return templates.TemplateResponse(request, "admin_snippet.html", {
            "users": users,
            "chores": chores,
            "transactions": transactions,
            "message": msg
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
            cursor.execute("SELECT name FROM users ORDER BY name")
            users = cursor.fetchall()
            return templates.TemplateResponse(request, "login_snippet.html", {
                "users": users,
                "selected_name": name,
                "error": "Invalid PIN. Try again."
            })
        
        # Leaderboard Data (Top earners this week)
        cursor.execute(
            """
            SELECT u.name, SUM(c.value_credits) as total_earned
            FROM users u
            JOIN chore_logs l ON u.id = l.user_id
            JOIN chores c ON l.chore_id = c.id
            WHERE l.action_type = 'earn'
            AND date(l.completed_at) >= date('now', '-7 days')
            GROUP BY u.id
            ORDER BY total_earned DESC
            """
        )
        leaderboard = cursor.fetchall()

        # Daily Progress
        cursor.execute(
            """
            SELECT COUNT(*) as completed_today
            FROM chore_logs
            WHERE user_id = ? 
            AND action_type = 'earn'
            AND date(completed_at) = date('now', 'localtime')
            """,
            (user["id"],)
        )
        progress = cursor.fetchone()

        # Fetch chores
        # Chores that are actually available to THIS user right now
        cursor.execute(
            """
            SELECT c.id, c.title, c.description, c.category, c.frequency, c.value_credits, c.max_daily_completions,
                   (SELECT COUNT(*) FROM chore_assignments WHERE chore_id = c.id) as is_assigned
            FROM chores c
            WHERE c.is_active = 1 
            AND (
                NOT EXISTS (SELECT 1 FROM chore_assignments WHERE chore_id = c.id)
                OR EXISTS (SELECT 1 FROM chore_assignments WHERE chore_id = c.id AND user_id = ?)
            )
            AND (
                c.frequency = 'adhoc'
                OR (
                    (SELECT COUNT(*) FROM chore_logs 
                     WHERE chore_id = c.id 
                     AND action_type = 'earn'
                     AND date(completed_at) = date('now', 'localtime')) < c.max_daily_completions
                )
                OR (c.frequency = 'weekly' AND NOT EXISTS (
                    SELECT 1 FROM chore_logs 
                    WHERE chore_id = c.id 
                    AND action_type = 'earn'
                    AND date(completed_at, 'weekday 0', '-7 days') = date('now', 'localtime', 'weekday 0', '-7 days')
                ))
            )
            ORDER BY c.category, c.title
            """,
            (user["id"],)
        )
        available_chores = cursor.fetchall()

        # Chores that were done today by ANYONE (to show as grayed out)
        cursor.execute(
            """
            SELECT DISTINCT c.id, c.title, c.description, c.category, c.value_credits, u.name as done_by
            FROM chores c
            JOIN chore_logs l ON c.id = l.chore_id
            JOIN users u ON l.user_id = u.id
            WHERE date(l.completed_at) = date('now', 'localtime')
            AND l.action_type = 'earn'
            AND c.frequency != 'adhoc'
            AND (
                (SELECT COUNT(*) FROM chore_logs WHERE chore_id = c.id AND action_type = 'earn' AND date(completed_at) = date('now', 'localtime')) >= c.max_daily_completions
                OR c.frequency = 'weekly'
            )
            """
        )
        completed_chores = cursor.fetchall()
        
        # Recent logs for undo logic (last 15 minutes completed by this user)
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
            (user["id"],)
        )
        recent_completes = cursor.fetchall()

        # Ticker: Last 5 chores completed by ANYONE today
        cursor.execute(
            """
            SELECT u.name, c.title, strftime('%H:%M', l.completed_at) as time_str
            FROM chore_logs l
            JOIN users u ON l.user_id = u.id
            JOIN chores c ON l.chore_id = c.id
            WHERE date(l.completed_at) = date('now', 'localtime')
            AND l.action_type = 'earn'
            ORDER BY l.completed_at DESC
            LIMIT 5
            """
        )
        ticker_items = cursor.fetchall()
        
        # Add stealth list of other assignees for the chores
        available_list = []
        for chore in available_chores:
            chore_dict = dict(chore)
            if chore["is_assigned"] > 0:
                cursor.execute(
                    "SELECT u.name FROM chore_assignments a JOIN users u ON a.user_id = u.id WHERE a.chore_id = ? AND a.user_id != ?",
                    (chore["id"], user["id"])
                )
                others = [row["name"] for row in cursor.fetchall()]
                chore_dict["other_assignees"] = others
            else:
                chore_dict["other_assignees"] = []
            available_list.append(chore_dict)
        
        return templates.TemplateResponse(request, "dashboard_snippet.html", {
            "user": user, 
            "chores": available_list,
            "completed_chores": completed_chores,
            "recent_completes": recent_completes,
            "ticker": ticker_items,
            "leaderboard": leaderboard,
            "completed_today": progress["completed_today"]
        })

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
            cursor.execute("BEGIN TRANSACTION;")
            cursor.execute("SELECT value_credits, title FROM chores WHERE id = ?", (chore_id,))
            chore = cursor.fetchone()
            
            # Record log with delta
            cursor.execute(
                "INSERT INTO chore_logs (chore_id, user_id, action_type, credits_delta) VALUES (?, ?, 'earn', ?)", 
                (chore_id, user_id, chore["value_credits"])
            )
            cursor.execute("UPDATE users SET token_balance = token_balance + ? WHERE id = ?", (chore["value_credits"], user_id))
            conn.commit()
            
            # Re-fetch page elements
            cursor.execute("SELECT id, name, token_balance, pin_hash FROM users WHERE id = ?", (user_id,))
            user = cursor.fetchone()
            
            cursor.execute(
                """
                SELECT u.name, SUM(c.value_credits) as total_earned
                FROM users u
                JOIN chore_logs l ON u.id = l.user_id
                JOIN chores c ON l.chore_id = c.id
                WHERE l.action_type = 'earn'
                AND date(l.completed_at) >= date('now', '-7 days')
                GROUP BY u.id
                ORDER BY total_earned DESC
                """
            )
            leaderboard = cursor.fetchall()

            cursor.execute("SELECT COUNT(*) as completed_today FROM chore_logs WHERE user_id = ? AND action_type = 'earn' AND date(completed_at) = date('now', 'localtime')", (user_id,))
            progress = cursor.fetchone()

            # Re-fetch available chores
            cursor.execute(
                """
                SELECT c.id, c.title, c.description, c.category, c.frequency, c.value_credits, c.max_daily_completions,
                       (SELECT COUNT(*) FROM chore_assignments WHERE chore_id = c.id) as is_assigned
                FROM chores c
                WHERE c.is_active = 1 
                AND (
                    NOT EXISTS (SELECT 1 FROM chore_assignments WHERE chore_id = c.id)
                    OR EXISTS (SELECT 1 FROM chore_assignments WHERE chore_id = c.id AND user_id = ?)
                )
                AND (
                    c.frequency = 'adhoc'
                    OR (
                        (SELECT COUNT(*) FROM chore_logs 
                         WHERE chore_id = c.id 
                         AND action_type = 'earn'
                         AND date(completed_at) = date('now', 'localtime')) < c.max_daily_completions
                    )
                    OR (c.frequency = 'weekly' AND NOT EXISTS (
                        SELECT 1 FROM chore_logs 
                        WHERE chore_id = c.id 
                        AND action_type = 'earn'
                        AND date(completed_at, 'weekday 0', '-7 days') = date('now', 'localtime', 'weekday 0', '-7 days')
                    ))
                )
                ORDER BY c.category, c.title
                """,
                (user_id,)
            )
            available_chores = cursor.fetchall()

            # Re-fetch completed chores
            cursor.execute(
                """
                SELECT DISTINCT c.id, c.title, u.name as done_by
                FROM chores c
                JOIN chore_logs l ON c.id = l.chore_id
                JOIN users u ON l.user_id = u.id
                WHERE date(l.completed_at) = date('now', 'localtime')
                AND l.action_type = 'earn'
                AND c.frequency != 'adhoc'
                AND (
                    (SELECT COUNT(*) FROM chore_logs WHERE chore_id = c.id AND action_type = 'earn' AND date(completed_at) = date('now', 'localtime')) >= c.max_daily_completions
                    OR c.frequency = 'weekly'
                )
                """
            )
            completed_chores = cursor.fetchall()
            
            # Fetch recent logs for undo logic (last 15 mins)
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

            # Ticker: Last 5 chores completed by ANYONE today
            cursor.execute(
                """
                SELECT u.name, c.title, strftime('%H:%M', l.completed_at) as time_str
                FROM chore_logs l
                JOIN users u ON l.user_id = u.id
                JOIN chores c ON l.chore_id = c.id
                WHERE date(l.completed_at) = date('now', 'localtime')
                AND l.action_type = 'earn'
                ORDER BY l.completed_at DESC
                LIMIT 5
                """
            )
            ticker_items = cursor.fetchall()
            
            available_list = []
            for chore_item in available_chores:
                chore_dict = dict(chore_item)
                if chore_item["is_assigned"] > 0:
                    cursor.execute(
                        "SELECT u.name FROM chore_assignments a JOIN users u ON a.user_id = u.id WHERE a.chore_id = ? AND a.user_id != ?",
                        (chore_item["id"], user_id)
                    )
                    others = [row["name"] for row in cursor.fetchall()]
                    chore_dict["other_assignees"] = others
                else:
                    chore_dict["other_assignees"] = []
                available_list.append(chore_dict)

            return templates.TemplateResponse(request, "dashboard_snippet.html", {
                "user": user, 
                "chores": available_list,
                "completed_chores": completed_chores,
                "recent_completes": recent_completes,
                "ticker": ticker_items,
                "leaderboard": leaderboard,
                "completed_today": progress["completed_today"],
                "message": f"Success! Earned {chore['value_credits']} credits."
            })
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
            else:
                conn.rollback()
                msg = "Log entry not found."
                
            # Re-fetch page elements
            cursor.execute("SELECT id, name, token_balance, pin_hash FROM users WHERE id = ?", (user_id,))
            user = cursor.fetchone()
            
            cursor.execute(
                """
                SELECT u.name, SUM(c.value_credits) as total_earned
                FROM users u
                JOIN chore_logs l ON u.id = l.user_id
                JOIN chores c ON l.chore_id = c.id
                WHERE l.action_type = 'earn'
                AND date(l.completed_at) >= date('now', '-7 days')
                GROUP BY u.id
                ORDER BY total_earned DESC
                """
            )
            leaderboard = cursor.fetchall()

            cursor.execute("SELECT COUNT(*) as completed_today FROM chore_logs WHERE user_id = ? AND action_type = 'earn' AND date(completed_at) = date('now', 'localtime')", (user_id,))
            progress = cursor.fetchone()

            # Re-fetch available chores
            cursor.execute(
                """
                SELECT c.id, c.title, c.description, c.category, c.frequency, c.value_credits, c.max_daily_completions,
                       (SELECT COUNT(*) FROM chore_assignments WHERE chore_id = c.id) as is_assigned
                FROM chores c
                WHERE c.is_active = 1 
                AND (
                    NOT EXISTS (SELECT 1 FROM chore_assignments WHERE chore_id = c.id)
                    OR EXISTS (SELECT 1 FROM chore_assignments WHERE chore_id = c.id AND user_id = ?)
                )
                AND (
                    c.frequency = 'adhoc'
                    OR (
                        (SELECT COUNT(*) FROM chore_logs 
                         WHERE chore_id = c.id 
                         AND action_type = 'earn'
                         AND date(completed_at) = date('now', 'localtime')) < c.max_daily_completions
                    )
                    OR (c.frequency = 'weekly' AND NOT EXISTS (
                        SELECT 1 FROM chore_logs 
                        WHERE chore_id = c.id 
                        AND action_type = 'earn'
                        AND date(completed_at, 'weekday 0', '-7 days') = date('now', 'localtime', 'weekday 0', '-7 days')
                    ))
                )
                ORDER BY c.category, c.title
                """,
                (user_id,)
            )
            available_chores = cursor.fetchall()

            # Re-fetch completed chores
            cursor.execute(
                """
                SELECT DISTINCT c.id, c.title, u.name as done_by
                FROM chores c
                JOIN chore_logs l ON c.id = l.chore_id
                JOIN users u ON l.user_id = u.id
                WHERE date(l.completed_at) = date('now', 'localtime')
                AND l.action_type = 'earn'
                AND c.frequency != 'adhoc'
                AND (
                    (SELECT COUNT(*) FROM chore_logs WHERE chore_id = c.id AND action_type = 'earn' AND date(completed_at) = date('now', 'localtime')) >= c.max_daily_completions
                    OR c.frequency = 'weekly'
                )
                """
            )
            completed_chores = cursor.fetchall()
            
            # Fetch recent logs for undo logic (last 15 mins)
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

            # Ticker: Last 5 chores completed by ANYONE today
            cursor.execute(
                """
                SELECT u.name, c.title, strftime('%H:%M', l.completed_at) as time_str
                FROM chore_logs l
                JOIN users u ON l.user_id = u.id
                JOIN chores c ON l.chore_id = c.id
                WHERE date(l.completed_at) = date('now', 'localtime')
                AND l.action_type = 'earn'
                ORDER BY l.completed_at DESC
                LIMIT 5
                """
            )
            ticker_items = cursor.fetchall()
            
            available_list = []
            for chore_item in available_chores:
                chore_dict = dict(chore_item)
                if chore_item["is_assigned"] > 0:
                    cursor.execute(
                        "SELECT u.name FROM chore_assignments a JOIN users u ON a.user_id = u.id WHERE a.chore_id = ? AND a.user_id != ?",
                        (chore_item["id"], user_id)
                    )
                    others = [row["name"] for row in cursor.fetchall()]
                    chore_dict["other_assignees"] = others
                else:
                    chore_dict["other_assignees"] = []
                available_list.append(chore_dict)

            return templates.TemplateResponse(request, "dashboard_snippet.html", {
                "user": user, 
                "chores": available_list,
                "completed_chores": completed_chores,
                "recent_completes": recent_completes,
                "ticker": ticker_items,
                "leaderboard": leaderboard,
                "completed_today": progress["completed_today"],
                "message": msg
            })
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
            
            # Re-fetch page elements
            cursor.execute("SELECT id, name, token_balance, pin_hash FROM users WHERE id = ?", (user_id,))
            user = cursor.fetchone()
            
            cursor.execute(
                """
                SELECT u.name, SUM(c.value_credits) as total_earned
                FROM users u
                JOIN chore_logs l ON u.id = l.user_id
                JOIN chores c ON l.chore_id = c.id
                WHERE l.action_type = 'earn'
                AND date(l.completed_at) >= date('now', '-7 days')
                GROUP BY u.id
                ORDER BY total_earned DESC
                """
            )
            leaderboard = cursor.fetchall()

            cursor.execute("SELECT COUNT(*) as completed_today FROM chore_logs WHERE user_id = ? AND action_type = 'earn' AND date(completed_at) = date('now', 'localtime')", (user_id,))
            progress = cursor.fetchone()

            # Re-fetch available chores
            cursor.execute(
                """
                SELECT c.id, c.title, c.description, c.category, c.frequency, c.value_credits, c.max_daily_completions,
                       (SELECT COUNT(*) FROM chore_assignments WHERE chore_id = c.id) as is_assigned
                FROM chores c
                WHERE c.is_active = 1 
                AND (
                    NOT EXISTS (SELECT 1 FROM chore_assignments WHERE chore_id = c.id)
                    OR EXISTS (SELECT 1 FROM chore_assignments WHERE chore_id = c.id AND user_id = ?)
                )
                AND (
                    c.frequency = 'adhoc'
                    OR (
                        (SELECT COUNT(*) FROM chore_logs 
                         WHERE chore_id = c.id 
                         AND action_type = 'earn'
                         AND date(completed_at) = date('now', 'localtime')) < c.max_daily_completions
                    )
                    OR (c.frequency = 'weekly' AND NOT EXISTS (
                        SELECT 1 FROM chore_logs 
                        WHERE chore_id = c.id 
                        AND action_type = 'earn'
                        AND date(completed_at, 'weekday 0', '-7 days') = date('now', 'localtime', 'weekday 0', '-7 days')
                    ))
                )
                ORDER BY c.category, c.title
                """,
                (user_id,)
            )
            available_chores = cursor.fetchall()

            # Re-fetch completed chores
            cursor.execute(
                """
                SELECT DISTINCT c.id, c.title, u.name as done_by
                FROM chores c
                JOIN chore_logs l ON c.id = l.chore_id
                JOIN users u ON l.user_id = u.id
                WHERE date(l.completed_at) = date('now', 'localtime')
                AND l.action_type = 'earn'
                AND c.frequency != 'adhoc'
                AND (
                    (SELECT COUNT(*) FROM chore_logs WHERE chore_id = c.id AND action_type = 'earn' AND date(completed_at) = date('now', 'localtime')) >= c.max_daily_completions
                    OR c.frequency = 'weekly'
                )
                """
            )
            completed_chores = cursor.fetchall()
            
            # Fetch recent logs for undo logic (last 15 mins)
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

            # Ticker: Last 5 chores completed by ANYONE today
            cursor.execute(
                """
                SELECT u.name, c.title, strftime('%H:%M', l.completed_at) as time_str
                FROM chore_logs l
                JOIN users u ON l.user_id = u.id
                JOIN chores c ON l.chore_id = c.id
                WHERE date(l.completed_at) = date('now', 'localtime')
                AND l.action_type = 'earn'
                ORDER BY l.completed_at DESC
                LIMIT 5
                """
            )
            ticker_items = cursor.fetchall()
            
            available_list = []
            for chore_item in available_chores:
                chore_dict = dict(chore_item)
                if chore_item["is_assigned"] > 0:
                    cursor.execute(
                        "SELECT u.name FROM chore_assignments a JOIN users u ON a.user_id = u.id WHERE a.chore_id = ? AND a.user_id != ?",
                        (chore_item["id"], user_id)
                    )
                    others = [row["name"] for row in cursor.fetchall()]
                    chore_dict["other_assignees"] = others
                else:
                    chore_dict["other_assignees"] = []
                available_list.append(chore_dict)

            return templates.TemplateResponse(request, "dashboard_snippet.html", {
                "user": user, 
                "chores": available_list,
                "completed_chores": completed_chores,
                "recent_completes": recent_completes,
                "ticker": ticker_items,
                "leaderboard": leaderboard,
                "completed_today": progress["completed_today"],
                "message": "PIN updated successfully!"
            })
        except Exception as e:
            return HTMLResponse(content=f"Error changing PIN: {str(e)}", status_code=500)

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
