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

templates = Jinja2Templates(directory=os.path.join(FRONTEND_DIR, "templates"))
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
    """Serves the main PIN entry page."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM users ORDER BY name")
        users = cursor.fetchall()
    return templates.TemplateResponse(request, "index.html", {"users": users})

@app.post("/api/admin-verify", response_class=HTMLResponse)
async def admin_verify(request: Request):
    """Verifies Admin PIN (Parent 1 or Parent 2) and returns the admin dashboard."""
    pin = request.headers.get("HX-Prompt")
    if not pin:
        return HTMLResponse(content='<div class="alert alert-error">Admin PIN required.</div>')
    
    hashed_input = hash_pin(pin)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Only Parent 1 and Parent 2 can access admin
        cursor.execute(
            "SELECT name FROM users WHERE pin_hash = ? AND (name = 'Parent 1' OR name = 'Parent 2')",
            (hashed_input,)
        )
        admin = cursor.fetchone()
        
        if not admin:
            return HTMLResponse(content='<div class="alert alert-error">Access Denied.</div>')
        
        # Fetch data for admin dashboard
        cursor.execute("SELECT id, name, token_balance FROM users ORDER BY token_balance DESC")
        users = cursor.fetchall()
        
        cursor.execute("SELECT id, title, description, category, frequency, value_credits, is_active FROM chores ORDER BY category, title")
        chores = cursor.fetchall()
        
        # Fetch assignments for each chore
        chore_list = []
        for chore in chores:
            cursor.execute("SELECT user_id FROM chore_assignments WHERE chore_id = ?", (chore["id"],))
            assigned_ids = [row["user_id"] for row in cursor.fetchall()]
            chore_dict = dict(chore)
            chore_dict["assigned_user_ids"] = assigned_ids
            chore_list.append(chore_dict)
        
        return templates.TemplateResponse(request, "admin_snippet.html", {
            "users": users,
            "chores": chore_list
        })

@app.post("/api/admin/chores/toggle/{chore_id}", response_class=HTMLResponse)
async def admin_toggle_chore(request: Request, chore_id: int):
    """Toggles a chore's active status from the admin panel."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE chores SET is_active = 1 - is_active WHERE id = ?", (chore_id,))
        conn.commit()
        
        # Return full admin refresh (simplified for now)
        cursor.execute("SELECT id, name, token_balance FROM users ORDER BY token_balance DESC")
        users = cursor.fetchall()
        cursor.execute("SELECT id, title, description, category, frequency, value_credits, is_active FROM chores ORDER BY category, title")
        chores = cursor.fetchall()
        
        chore_list = []
        for chore in chores:
            cursor.execute("SELECT user_id FROM chore_assignments WHERE chore_id = ?", (chore["id"],))
            assigned_ids = [row["user_id"] for row in cursor.fetchall()]
            chore_dict = dict(chore)
            chore_dict["assigned_user_ids"] = assigned_ids
            chore_list.append(chore_dict)
            
        return templates.TemplateResponse(request, "admin_snippet.html", {
            "users": users,
            "chores": chore_list,
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
                SET title = ?, description = ?, category = ?, frequency = ?, value_credits = ? 
                WHERE id = ?
                """, 
                (title, description, category, frequency, value_credits, chore_id)
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
        
        # Refresh Admin View
        cursor.execute("SELECT id, name, token_balance FROM users ORDER BY token_balance DESC")
        users = cursor.fetchall()
        cursor.execute("SELECT id, title, description, category, frequency, value_credits, is_active FROM chores ORDER BY category, title")
        chores = cursor.fetchall()
        
        chore_list = []
        for chore in chores:
            cursor.execute("SELECT user_id FROM chore_assignments WHERE chore_id = ?", (chore["id"],))
            assigned_ids = [row["user_id"] for row in cursor.fetchall()]
            chore_dict = dict(chore)
            chore_dict["assigned_user_ids"] = assigned_ids
            chore_list.append(chore_dict)
        
        return templates.TemplateResponse(request, "admin_snippet.html", {
            "users": users,
            "chores": chore_list,
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
        
        # Fetch chores and filter by assignments AND frequency/cooldown
        # Logic: Show if (Unassigned OR Assigned to me) 
        # AND (Frequency is 'adhoc' OR not done today for 'daily' OR not done 3x today for 'meal' OR not done this week for 'weekly')
        cursor.execute(
            """
            SELECT c.id, c.title, c.description, c.category, c.frequency, c.value_credits 
            FROM chores c
            WHERE c.is_active = 1 
            AND (
                NOT EXISTS (SELECT 1 FROM chore_assignments WHERE chore_id = c.id)
                OR EXISTS (SELECT 1 FROM chore_assignments WHERE chore_id = c.id AND user_id = ?)
            )
            AND (
                c.frequency = 'adhoc'
                OR (c.frequency = 'daily' AND NOT EXISTS (
                    SELECT 1 FROM chore_logs 
                    WHERE chore_id = c.id AND user_id = ? 
                    AND date(completed_at) = date('now', 'localtime')
                ))
                OR (c.frequency = 'meal' AND (
                    SELECT COUNT(*) FROM chore_logs 
                    WHERE chore_id = c.id AND user_id = ? 
                    AND date(completed_at) = date('now', 'localtime')
                ) < 3)
                OR (c.frequency = 'weekly' AND NOT EXISTS (
                    SELECT 1 FROM chore_logs 
                    WHERE chore_id = c.id AND user_id = ? 
                    AND date(completed_at, 'weekday 0', '-7 days') = date('now', 'localtime', 'weekday 0', '-7 days')
                ))
            )
            ORDER BY c.category, c.title
            """,
            (user["id"], user["id"], user["id"], user["id"])
        )
        chores = cursor.fetchall()
        
        return templates.TemplateResponse(request, "dashboard_snippet.html", {
            "user": user, 
            "chores": chores
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
        
        cursor.execute(
            """
            SELECT c.id, c.title, c.description, c.category, c.frequency, c.value_credits 
            FROM chores c
            WHERE c.is_active = 1 
            AND (
                NOT EXISTS (SELECT 1 FROM chore_assignments WHERE chore_id = c.id)
                OR EXISTS (SELECT 1 FROM chore_assignments WHERE chore_id = c.id AND user_id = ?)
            )
            ORDER BY c.category, c.title
            """,
            (user_id,)
        )
        chores = cursor.fetchall()

        if not pin or hash_pin(pin) != user["pin_hash"]:
            return templates.TemplateResponse(request, "dashboard_snippet.html", {
                "user": user,
                "chores": chores,
                "error": "Invalid PIN. Completion failed."
            })
            
        cursor.execute("SELECT value_credits, title FROM chores WHERE id = ? AND is_active = 1", (chore_id,))
        chore = cursor.fetchone()
        if not chore:
            return templates.TemplateResponse(request, "dashboard_snippet.html", {
                "user": user,
                "chores": chores,
                "error": "Chore not found."
            })
            
        try:
            cursor.execute("BEGIN TRANSACTION;")
            cursor.execute("INSERT INTO chore_logs (chore_id, user_id) VALUES (?, ?)", (chore_id, user_id))
            cursor.execute("UPDATE users SET token_balance = token_balance + ? WHERE id = ?", (chore["value_credits"], user_id))
            conn.commit()
            
            # Refresh user data
            cursor.execute("SELECT id, name, token_balance FROM users WHERE id = ?", (user_id,))
            user = cursor.fetchone()
            
            return templates.TemplateResponse(request, "dashboard_snippet.html", {
                "user": user, 
                "chores": chores,
                "message": f"Success! Earned {chore['value_credits']} credits."
            })
        except Exception as e:
            conn.rollback()
            return templates.TemplateResponse(request, "dashboard_snippet.html", {
                "user": user,
                "chores": chores,
                "error": f"Error: {str(e)}"
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
