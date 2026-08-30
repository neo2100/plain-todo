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
from pymongo.errors import DuplicateKeyError
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


COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "true").lower() == "true"
COOKIE_SAMESITE = os.environ.get("COOKIE_SAMESITE", "none" if COOKIE_SECURE else "lax")


def set_auth_cookie(response: Response, name: str, value: str, max_age: int):
    response.set_cookie(key=name, value=value, httponly=True, secure=COOKIE_SECURE,
                        samesite=COOKIE_SAMESITE, max_age=max_age, path="/")


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
    notes: str = ""


class BacklogInput(BaseModel):
    items: List[BacklogItem] = []


class SettingsInput(BaseModel):
    rollover_enabled: bool = True
    carry_weekdays: List[int] = [0, 1, 2, 3, 4, 5, 6]
    interval_mode: str = "daily"  # daily | weekly | custom
    interval_days: int = 1


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
    response.delete_cookie("access_token", path="/", secure=COOKIE_SECURE, samesite=COOKIE_SAMESITE)
    response.delete_cookie("session_token", path="/", secure=COOKIE_SECURE, samesite=COOKIE_SAMESITE)
    return {"ok": True}


@api_router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return public_user(user)


# ---------------------------------------------------------------------------
# Rollover logic
# ---------------------------------------------------------------------------
TASK_RE = re.compile(r"^\s*\[( |x|X)\]")


def _is_task(line: str) -> bool:
    return bool(TASK_RE.match(line))


def _is_open_task(line: str) -> bool:
    return bool(re.match(r"^\s*\[\s\]", line))


def _is_heading(line: str) -> bool:
    return line.lstrip(" \t").startswith("#")


def _indent_of(line: str) -> int:
    stripped = line.lstrip(" \t")
    raw = line[: len(line) - len(stripped)]
    return raw.replace("\t", "  ").count("  ")


def extract_open_task_blocks(content: str):
    """
    Extract open task blocks while preserving their original order.

    A block starts with an open task and includes all following lines until:
      - another task at the same or shallower indentation
      - a heading

    Example:

        [ ] Add new feature
          [ ] subtask 1
          - some note

    becomes one block.
    """
    lines = content.splitlines()
    blocks = []

    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]

        if not _is_open_task(line):
            i += 1
            continue

        indent = _indent_of(line)
        block = [line]
        i += 1

        while i < n:
            nxt = lines[i]

            if _is_heading(nxt):
                break

            if _is_task(nxt) and _indent_of(nxt) <= indent:
                break

            block.append(nxt)
            i += 1

        blocks.append(block)

    return blocks


def _section_name(line: str) -> str:
    """
    Return a normalized section name.

    '# Plain ToDo improvements' -> '# Plain ToDo improvements'
    """
    return line.strip()


def _collect_open_tasks_by_section(documents):
    """
    Collect open task blocks from documents.

    Returns:

        [
            {
                "section": "# Section A",
                "blocks": [...]
            },
            ...
        ]

    Section order is the order in which sections/tasks are first encountered
    while walking from oldest -> newest day.

    Tasks within a section retain their original order.
    """

    sections = {}
    section_order = []

    for doc in documents:
        content = doc.get("content", "")
        lines = content.splitlines()

        current_section = None
        i = 0

        while i < len(lines):
            line = lines[i]

            # A heading changes the current section.
            if _is_heading(line):
                current_section = _section_name(line)

                if current_section not in sections:
                    sections[current_section] = []
                    section_order.append(current_section)

                i += 1
                continue

            # Ignore everything that isn't an open task.
            if not _is_open_task(line):
                i += 1
                continue

            indent = _indent_of(line)
            block = [line]
            i += 1

            # Capture the complete task block.
            while i < len(lines):
                nxt = lines[i]

                if _is_heading(nxt):
                    break

                if _is_task(nxt) and _indent_of(nxt) <= indent:
                    break

                block.append(nxt)
                i += 1

            if current_section not in sections:
                sections[current_section] = []
                section_order.append(current_section)

            sections[current_section].append(block)

    return [
        {
            "section": section,
            "blocks": sections[section],
        }
        for section in section_order
    ]


def _task_key(block):
    """
    Return a normalized key used for duplicate detection.

    Currently the complete task block is used.

    This means:

        [ ] Task A

    and:

        [ ] Task A
          note

    are considered different.

    If you want duplicate detection based only on the task title,
    change this function later.
    """
    return "\n".join(line.rstrip() for line in block).strip()


def _build_rollover_content(section_groups):
    """
    Build text for the rollover while preserving section/task order.
    """

    output = []

    for group in section_groups:
        section = group["section"]
        blocks = group["blocks"]

        if not blocks:
            continue

        # Add section heading for named sections.
        if section:
            if output:
                output.append("")

            output.append(section)

        for block in blocks:
            output.extend(block)

    return "\n".join(output).strip()


async def roll_over(user_id: str, today: str, days: int):
    """
    Copy open tasks from the previous `days` calendar days into today.

    IMPORTANT:
      - Previous days are never modified.
      - Tasks are grouped by section.
      - Original order is preserved as much as possible.
      - Existing today content is preserved.
      - Duplicate tasks are not added.

    Example:

        roll_over(user_id, "2026-08-29", 3)

    looks at:

        2026-08-28
        2026-08-27
        2026-08-26

    and merges their open tasks into 2026-08-29.
    """

    days = max(1, int(days))

    today_dt = datetime.strptime(today, "%Y-%m-%d")

    start_dt = today_dt - timedelta(days=days)

    start_date = start_dt.strftime("%Y-%m-%d")

    # Get the requested historical window.
    cursor = db.days.find(
        {
            "user_id": user_id,
            "date": {
                "$gte": start_date,
                "$lt": today,
            },
        },
        {
            "_id": 0,
            "date": 1,
            "content": 1,
        },
    ).sort("date", 1)

    previous_days = await cursor.to_list(days)

    if not previous_days:
        return {
            "rolled_over": False,
            "days": days,
            "tasks_added": 0,
        }

    # ---------------------------------------------------------
    # Read today's content.
    # ---------------------------------------------------------

    today_doc = await db.days.find_one(
        {
            "user_id": user_id,
            "date": today,
        },
        {
            "_id": 0,
            "content": 1,
        },
    )

    today_content = (
        today_doc.get("content", "")
        if today_doc
        else ""
    )

    # ---------------------------------------------------------
    # Collect existing today's task keys.
    #
    # This prevents us from adding a task that already exists.
    # ---------------------------------------------------------

    existing_today_blocks = extract_open_task_blocks(today_content)

    existing_keys = {
        _task_key(block)
        for block in existing_today_blocks
    }

    # ---------------------------------------------------------
    # Collect historical open tasks grouped by section.
    # ---------------------------------------------------------

    section_groups = _collect_open_tasks_by_section(previous_days)

    added = 0

    for group in section_groups:
        unique_blocks = []

        for block in group["blocks"]:
            key = _task_key(block)

            if not key:
                continue

            if key in existing_keys:
                continue

            # Also prevent the same task from being copied twice
            # when it appears on multiple historical days.
            if key in {_task_key(b) for b in unique_blocks}:
                continue

            unique_blocks.append(block)
            existing_keys.add(key)
            added += 1

        group["blocks"] = unique_blocks

    if added == 0:
        return {
            "rolled_over": False,
            "days": days,
            "tasks_added": 0,
        }

    rollover_content = _build_rollover_content(section_groups)

    if not rollover_content:
        return {
            "rolled_over": False,
            "days": days,
            "tasks_added": 0,
        }

    # ---------------------------------------------------------
    # Merge with today.
    #
    # Today's existing content remains untouched first.
    # Historical rollover content comes afterwards.
    # ---------------------------------------------------------

    if today_content.strip():
        merged_content = (
            today_content.lstrip()
            + "\n\n"
            + rollover_content.rstrip()
        )
    else:
        merged_content = rollover_content

    await _upsert_day(
        user_id,
        today,
        merged_content,
    )

    return {
        "rolled_over": True,
        "days": days,
        "tasks_added": added,
    }


def get_rollover_days(settings: dict, today: str):
    """
    Decide whether rollover should happen today.

    Returns:
        number of days to roll over
        or None if rollover should not happen.

    This function does NOT modify the database.
    """

    if not settings.get("rollover_enabled", True):
        return None

    today_dt = datetime.strptime(today, "%Y-%m-%d")

    # ---------------------------------------------------------
    # Allowed weekdays
    # ---------------------------------------------------------

    carry_weekdays = settings.get(
        "carry_weekdays",
        [0, 1, 2, 3, 4, 5, 6],
    )

    try:
        carry_weekdays = {
            int(day)
            for day in carry_weekdays
            if 0 <= int(day) <= 6
        }
    except (TypeError, ValueError):
        carry_weekdays = {0, 1, 2, 3, 4, 5, 6}

    if today_dt.weekday() not in carry_weekdays:
        return None

    # ---------------------------------------------------------
    # Don't run twice today.
    # ---------------------------------------------------------

    last_rollover_date = settings.get("last_rollover_date")

    if last_rollover_date == today:
        return None

    # ---------------------------------------------------------
    # Determine interval.
    # ---------------------------------------------------------

    mode = (settings.get("interval_mode") or "daily").lower()

    if mode == "weekly":
        interval_days = 7

    elif mode == "custom":
        interval_days = max(
            1,
            int(settings.get("interval_days") or 1),
        )

    else:
        interval_days = 1

    # ---------------------------------------------------------
    # First rollover.
    # ---------------------------------------------------------

    if not last_rollover_date:
        return interval_days

    try:
        last_dt = datetime.strptime(
            last_rollover_date,
            "%Y-%m-%d",
        )
    except (TypeError, ValueError):
        return interval_days

    elapsed = (today_dt - last_dt).days

    if elapsed < interval_days:
        return None

    return interval_days


async def maybe_roll_over(
    user_id: str,
    today: str,
    settings: dict,
):
    days = get_rollover_days(
        settings=settings,
        today=today,
    )

    if days is None:
        return {
            "rolled_over": False,
            "days": 0,
            "tasks_added": 0,
        }

    result = await roll_over(
        user_id=user_id,
        today=today,
        days=days,
    )

    await db.settings.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "last_rollover_date": today,
            }
        },
        upsert=True,
    )

    return result



# ---------------------------------------------------------------------------
# Board endpoints
# ---------------------------------------------------------------------------
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def valid_date(date: str) -> bool:
    if not DATE_RE.match(date):
        return False
    try:
        datetime.strptime(date, "%Y-%m-%d")
        return True
    except ValueError:
        return False


DEFAULT_SETTINGS = {
    "rollover_enabled": True,
    "carry_weekdays": [0, 1, 2, 3, 4, 5, 6],
    "interval_mode": "daily",
    "interval_days": 1,
}


def effective_settings(doc: dict) -> dict:
    """
    Merge stored settings with defaults.

    Keeps last_rollover_date available internally, but it is not part
    of DEFAULT_SETTINGS because it is runtime/state information rather
    than a user-configurable setting.
    """
    doc = doc or {}

    s = dict(DEFAULT_SETTINGS)

    # Legacy migration from the old rollover_mode field.
    if "rollover_enabled" not in doc and "rollover_mode" in doc:
        if doc["rollover_mode"] == "workdays":
            s["carry_weekdays"] = [0, 1, 2, 3, 4]

    for key in DEFAULT_SETTINGS:
        if key in doc and doc[key] is not None:
            s[key] = doc[key]

    s["last_rollover_date"] = doc.get("last_rollover_date")

    return s


@api_router.get("/board")
async def get_board(
    date: str,
    user: dict = Depends(get_current_user),
):
    if not valid_date(date):
        raise HTTPException(
            status_code=400,
            detail="Invalid date",
        )

    uid = user["user_id"]

    # Load effective settings.
    settings_doc = await db.settings.find_one(
        {"user_id": uid},
        {"_id": 0},
    )

    settings = effective_settings(settings_doc)

    # Let the rollover decision/execution logic handle rollover.
    #
    # This checks:
    #   - rollover_enabled
    #   - allowed weekday
    #   - interval
    #   - last_rollover_date
    #
    # and, if appropriate, calls roll_over().
    await maybe_roll_over(
        user_id=uid,
        today=date,
        settings=settings,
    )

    # Reload settings because maybe_roll_over() may have updated
    # last_rollover_date.
    settings_doc = await db.settings.find_one(
        {"user_id": uid},
        {"_id": 0},
    )

    settings = effective_settings(settings_doc)

    # Get all board days.
    days = await db.days.find(
        {"user_id": uid},
        {"_id": 0},
    ).sort("date", -1).to_list(1000)

    # Always create the current day document on open.
    if not any(d["date"] == date for d in days):
        await _upsert_day(uid, date, "")

        days = [
            {"date": date, "content": ""}
        ] + days

    backlog = (
        await db.backlog.find_one(
            {"user_id": uid},
            {"_id": 0},
        )
        or {"items": []}
    )

    return {
        "today": date,
        "days": [
            {
                "date": d["date"],
                "content": d.get("content", ""),
            }
            for d in days
        ],
        "backlog": {
            "items": backlog.get("items", []),
        },
        "settings": {
            key: settings[key]
            for key in DEFAULT_SETTINGS
        },
    }


async def _upsert_day(uid: str, date: str, content: str):
    filt = {"user_id": uid, "date": date}
    update = {"$set": {"content": content, "updated_at": datetime.now(timezone.utc).isoformat()}}
    try:
        await db.days.update_one(filt, update, upsert=True)
    except DuplicateKeyError:
        # Concurrent upsert on the (user_id, date) unique index — plain update is safe.
        await db.days.update_one(filt, update)


@api_router.put("/days/{date}")
async def save_day(date: str, body: DayInput, user: dict = Depends(get_current_user)):
    if not valid_date(date):
        raise HTTPException(status_code=400, detail="Invalid date")
    await _upsert_day(user["user_id"], date, body.content)
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
    if body.interval_mode not in ("daily", "weekly", "custom"):
        raise HTTPException(status_code=400, detail="Invalid interval mode")
    weekdays = sorted({d for d in body.carry_weekdays if 0 <= d <= 6})
    update = {
        "rollover_enabled": body.rollover_enabled,
        "carry_weekdays": weekdays or [0, 1, 2, 3, 4, 5, 6],
        "interval_mode": body.interval_mode,
        "interval_days": max(1, body.interval_days),
    }
    await db.settings.update_one({"user_id": user["user_id"]}, {"$set": update}, upsert=True)
    return update


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
