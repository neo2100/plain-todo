from dotenv import load_dotenv
from pathlib import Path
import os

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import logging
from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
import uuid
import re
import bcrypt
import jwt
import requests
from datetime import datetime, timezone, timedelta

# ---------------------------------------------------------------------------
# Config / DB
# ---------------------------------------------------------------------------
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

JWT_ALGORITHM = "HS256"
EMERGENT_SESSION_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"

app = FastAPI()
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_jwt_secret() -> str:
    return os.environ["JWT_SECRET"]


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: str, email: str) -> str:
    payload = {"sub": user_id, "email": email,
               "exp": datetime.now(timezone.utc) + timedelta(days=7), "type": "access"}
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def set_auth_cookie(response: Response, name: str, value: str, max_age: int):
    response.set_cookie(key=name, value=value, httponly=True, secure=True,
                        samesite="none", max_age=max_age, path="/")


async def resolve_user(request: Request) -> Optional[dict]:
    # 1. Emergent Google session token
    session_token = request.cookies.get("session_token")
    if not session_token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            session_token = auth_header[7:]
    if session_token:
        sess = await db.user_sessions.find_one({"session_token": session_token}, {"_id": 0})
        if sess:
            expires_at = sess["expires_at"]
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at >= datetime.now(timezone.utc):
                user = await db.users.find_one({"user_id": sess["user_id"]}, {"_id": 0, "password_hash": 0})
                if user:
                    return user

    # 2. JWT access token (email/password)
    token = request.cookies.get("access_token")
    if token:
        try:
            payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
            if payload.get("type") == "access":
                user = await db.users.find_one({"user_id": payload["sub"]}, {"_id": 0, "password_hash": 0})
                if user:
                    return user
        except jwt.InvalidTokenError:
            pass
    return None


async def get_current_user(request: Request) -> dict:
    user = await resolve_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class RegisterInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: Optional[str] = None


class LoginInput(BaseModel):
    email: EmailStr
    password: str


class DayInput(BaseModel):
    content: str = ""


class BacklogItem(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:10])
    text: str
    done: bool = False


class BacklogInput(BaseModel):
    items: List[BacklogItem] = []


class SettingsInput(BaseModel):
    rollover_mode: str = "everyday"  # everyday | workdays


def public_user(u: dict) -> dict:
    return {"user_id": u["user_id"], "email": u["email"],
            "name": u.get("name"), "picture": u.get("picture")}


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------
@api_router.post("/auth/register")
async def register(body: RegisterInput, response: Response):
    email = body.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="An account with this email already exists.")
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    await db.users.insert_one({
        "user_id": user_id, "email": email, "name": body.name or email.split("@")[0],
        "password_hash": hash_password(body.password), "picture": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    token = create_access_token(user_id, email)
    set_auth_cookie(response, "access_token", token, 604800)
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
    return public_user(user)


@api_router.post("/auth/login")
async def login(body: LoginInput, response: Response):
    email = body.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user or not user.get("password_hash") or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    token = create_access_token(user["user_id"], email)
    set_auth_cookie(response, "access_token", token, 604800)
    return public_user(user)


@api_router.post("/auth/session")
async def google_session(request: Request, response: Response):
    session_id = request.headers.get("X-Session-ID")
    if not session_id:
        body = {}
        try:
            body = await request.json()
        except Exception:
            pass
        session_id = body.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="Missing session id")
    try:
        r = requests.get(EMERGENT_SESSION_URL, headers={"X-Session-ID": session_id}, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.error(f"Emergent session-data error: {e}")
        raise HTTPException(status_code=401, detail="Failed to verify session")

    email = data["email"].lower().strip()
    existing = await db.users.find_one({"email": email})
    if existing:
        user_id = existing["user_id"]
        await db.users.update_one({"user_id": user_id},
                                  {"$set": {"name": data.get("name"), "picture": data.get("picture")}})
    else:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({
            "user_id": user_id, "email": email, "name": data.get("name"),
            "picture": data.get("picture"), "password_hash": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    session_token = data["session_token"]
    await db.user_sessions.insert_one({
        "user_id": user_id, "session_token": session_token,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    set_auth_cookie(response, "session_token", session_token, 604800)
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
    return public_user(user)


@api_router.post("/auth/logout")
async def logout(request: Request, response: Response):
    session_token = request.cookies.get("session_token")
    if session_token:
        await db.user_sessions.delete_one({"session_token": session_token})
    response.delete_cookie("access_token", path="/", secure=True, samesite="none")
    response.delete_cookie("session_token", path="/", secure=True, samesite="none")
    return {"ok": True}


@api_router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return public_user(user)


# ---------------------------------------------------------------------------
# Rollover logic
# ---------------------------------------------------------------------------
def _indent_of(line: str) -> int:
    stripped = line.lstrip(" \t")
    raw = line[: len(line) - len(stripped)]
    return raw.replace("\t", "  ").count("  ")


def _is_open_task(line: str) -> bool:
    return line.lstrip(" \t").startswith("[ ]")


def split_open_tasks(content: str):
    """Return (remaining_content, moved_lines) extracting open task groups."""
    lines = content.split("\n") if content else []
    kept, moved = [], []
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        if _is_open_task(line):
            indent = _indent_of(line)
            group = [line]
            j = i + 1
            while j < n:
                nxt = lines[j]
                if nxt.strip() == "":
                    break
                if _indent_of(nxt) > indent and not _is_open_task(nxt):
                    group.append(nxt)
                    j += 1
                else:
                    break
            moved.extend(group)
            i = j
        else:
            kept.append(line)
            i += 1
    return "\n".join(kept), moved


async def run_rollover(user_id: str, today: str, mode: str):
    settings = await db.settings.find_one({"user_id": user_id}, {"_id": 0}) or {}
    last = settings.get("last_rollover_date")
    if last == today:
        return
    # workdays mode: don't roll onto a weekend (Sat=5, Sun=6)
    if mode == "workdays":
        wd = datetime.strptime(today, "%Y-%m-%d").weekday()
        if wd >= 5:
            return

    prev_days = await db.days.find(
        {"user_id": user_id, "date": {"$lt": today}}, {"_id": 0}
    ).sort("date", 1).to_list(1000)

    all_moved = []
    for d in prev_days:
        remaining, moved = split_open_tasks(d.get("content", ""))
        if moved:
            all_moved.extend(moved)
            await db.days.update_one({"user_id": user_id, "date": d["date"]},
                                     {"$set": {"content": remaining}})

    if all_moved:
        today_doc = await db.days.find_one({"user_id": user_id, "date": today}, {"_id": 0})
        existing = today_doc.get("content", "") if today_doc else ""
        base = existing.rstrip("\n")
        merged = ("\n".join([base] + all_moved)).strip("\n") if base else "\n".join(all_moved)
        await db.days.update_one(
            {"user_id": user_id, "date": today},
            {"$set": {"content": merged, "updated_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )

    await db.settings.update_one({"user_id": user_id},
                                 {"$set": {"last_rollover_date": today}}, upsert=True)


# ---------------------------------------------------------------------------
# Board endpoints
# ---------------------------------------------------------------------------
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@api_router.get("/board")
async def get_board(date: str, user: dict = Depends(get_current_user)):
    if not DATE_RE.match(date):
        raise HTTPException(status_code=400, detail="Invalid date")
    uid = user["user_id"]
    settings = await db.settings.find_one({"user_id": uid}, {"_id": 0}) or {}
    mode = settings.get("rollover_mode", "everyday")
    await run_rollover(uid, date, mode)

    days = await db.days.find({"user_id": uid}, {"_id": 0}).sort("date", -1).to_list(1000)
    if not any(d["date"] == date for d in days):
        days = [{"date": date, "content": ""}] + days
    backlog = await db.backlog.find_one({"user_id": uid}, {"_id": 0}) or {"items": []}
    settings = await db.settings.find_one({"user_id": uid}, {"_id": 0}) or {}
    return {
        "today": date,
        "days": [{"date": d["date"], "content": d.get("content", "")} for d in days],
        "backlog": {"items": backlog.get("items", [])},
        "settings": {"rollover_mode": settings.get("rollover_mode", "everyday")},
    }


@api_router.put("/days/{date}")
async def save_day(date: str, body: DayInput, user: dict = Depends(get_current_user)):
    if not DATE_RE.match(date):
        raise HTTPException(status_code=400, detail="Invalid date")
    await db.days.update_one(
        {"user_id": user["user_id"], "date": date},
        {"$set": {"content": body.content, "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    return {"ok": True}


@api_router.put("/backlog")
async def save_backlog(body: BacklogInput, user: dict = Depends(get_current_user)):
    items = [i.model_dump() for i in body.items]
    await db.backlog.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"items": items, "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    return {"items": items}


@api_router.put("/settings")
async def save_settings(body: SettingsInput, user: dict = Depends(get_current_user)):
    if body.rollover_mode not in ("everyday", "workdays"):
        raise HTTPException(status_code=400, detail="Invalid mode")
    await db.settings.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"rollover_mode": body.rollover_mode}}, upsert=True,
    )
    return {"rollover_mode": body.rollover_mode}


@api_router.get("/")
async def root():
    return {"message": "Plain Todo API"}


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("user_id")
    await db.user_sessions.create_index("session_token")
    await db.days.create_index([("user_id", 1), ("date", 1)], unique=True)
    admin_email = os.environ.get("ADMIN_EMAIL")
    admin_password = os.environ.get("ADMIN_PASSWORD")
    if admin_email and admin_password:
        existing = await db.users.find_one({"email": admin_email})
        if existing is None:
            await db.users.insert_one({
                "user_id": f"user_{uuid.uuid4().hex[:12]}", "email": admin_email,
                "name": "Admin", "password_hash": hash_password(admin_password),
                "picture": None, "role": "admin",
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
        elif not verify_password(admin_password, existing.get("password_hash", "")):
            await db.users.update_one({"email": admin_email},
                                      {"$set": {"password_hash": hash_password(admin_password)}})


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
