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
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

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
    return templates.TemplateResponse("index.html", {"request": request, "users": users})

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """Serves the read-only administrative dashboard."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, token_balance FROM users ORDER BY token_balance DESC")
        users = cursor.fetchall()
    return templates.TemplateResponse("admin.html", {"request": request, "users": users})

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
            return HTMLResponse(
                content='<div class="alert alert-error">Invalid PIN. Try again.</div>',
                status_code=200
            )
        
        cursor.execute("SELECT id, title, description, value_credits FROM chores WHERE is_active = 1")
        chores = cursor.fetchall()
        
        return templates.TemplateResponse("dashboard_snippet.html", {
            "request": request, 
            "user": user, 
            "chores": chores
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
