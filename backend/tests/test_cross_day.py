"""Plain Todo — iteration 4 backend tests.

Covers the backend surface used by the new frontend features:
- Add-a-past-day: PUT /api/days/{date} upserts an *empty* day and GET /api/board returns it.
- Cross-day move: two PUTs (source stripped, target appended) both persist.
- Inline-conversion serialisation round-trip ("- x", "# X", "[ ] x").
"""
import os
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
API = base_url.rstrip("/") + "/api"
BE = dotenv_values("/app/backend/.env")


def creds():
    c = Path("/app/memory/test_credentials.md").read_text(encoding="utf-8")
    e = re.search(r"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?email(?:\*\*)?\s*:\s*`?([^`\s]+)", c)
    pw = re.search(r"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?password(?:\*\*)?\s*:\s*`?([^`\s]+)", c)
    if not e or not pw:
        pytest.skip("credentials missing")
    return e.group(1), pw.group(1)


@pytest.fixture(scope="module")
def mongo():
    cli = MongoClient(BE["MONGO_URL"])
    yield cli[BE["DB_NAME"]]
    cli.close()


@pytest.fixture
def user(mongo):
    email = f"test_xday_{uuid.uuid4().hex[:8]}@example.com"
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/register", json={"email": email, "password": "secret1"})
    assert r.status_code == 200, r.text
    uid = r.json()["user_id"]
    yield s, uid
    for coll in ("days", "settings", "backlog", "users"):
        mongo[coll].delete_many({"user_id": uid})


def today_str():
    return datetime.now().strftime("%Y-%m-%d")


def offset_str(days):
    return (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")


def board(s, date=None):
    r = s.get(f"{API}/board", params={"date": date or today_str()})
    assert r.status_code == 200, r.text
    return r.json()


def content_of(b, date):
    return next((d["content"] for d in b["days"] if d["date"] == date), None)


# ---------------- add a past day ----------------
class TestAddPastDay:
    def test_empty_past_day_upsert_is_returned_by_board(self, user):
        s, _ = user
        past = offset_str(-9)
        r = s.put(f"{API}/days/{past}", json={"content": ""})
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True

        b = board(s)
        assert content_of(b, past) == "", f"past day missing from board: {[d['date'] for d in b['days']]}"

    def test_past_day_upsert_is_idempotent_no_duplicates(self, user):
        s, _ = user
        past = offset_str(-11)
        for _ in range(3):
            assert s.put(f"{API}/days/{past}", json={"content": ""}).status_code == 200
        b = board(s)
        assert [d["date"] for d in b["days"]].count(past) == 1

    def test_days_sorted_newest_first(self, user):
        s, _ = user
        for off in (-3, -15, -7):
            assert s.put(f"{API}/days/{offset_str(off)}", json={"content": ""}).status_code == 200
        dates = [d["date"] for d in board(s)["days"]]
        assert dates == sorted(dates, reverse=True), dates

    @pytest.mark.xfail(reason="PUT /api/days accepts syntactically-valid but impossible dates (2026-13-99)")
    def test_bad_date_rejected(self, user):
        s, _ = user
        assert s.put(f"{API}/days/2026-13-99", json={"content": ""}).status_code in (400, 422)


# ---------------- cross-day move persistence ----------------
class TestCrossDayMove:
    def test_group_move_between_days_persists(self, user):
        s, _ = user
        # disable rollover so past-day content is not auto-carried into today
        s.put(f"{API}/settings", json={"rollover_enabled": False, "carry_weekdays": [0,1,2,3,4,5,6],
                                       "interval_mode": "daily", "interval_days": 1})
        src, dst = today_str(), offset_str(-5)
        assert s.put(f"{API}/days/{src}", json={"content": "[ ] Task A\n  - note a\n[ ] Task B"}).status_code == 200
        assert s.put(f"{API}/days/{dst}", json={"content": "[ ] Old"}).status_code == 200

        # simulate the frontend's two writes for a cross-day move
        assert s.put(f"{API}/days/{src}", json={"content": "[ ] Task B"}).status_code == 200
        assert s.put(f"{API}/days/{dst}", json={"content": "[ ] Old\n[ ] Task A\n  - note a"}).status_code == 200

        b = board(s)
        assert content_of(b, src) == "[ ] Task B"
        assert content_of(b, dst) == "[ ] Old\n[ ] Task A\n  - note a"

    def test_day_can_be_emptied(self, user):
        s, _ = user
        s.put(f"{API}/settings", json={"rollover_enabled": False, "carry_weekdays": [0,1,2,3,4,5,6],
                                       "interval_mode": "daily", "interval_days": 1})
        d = offset_str(-6)
        assert s.put(f"{API}/days/{d}", json={"content": "[ ] only"}).status_code == 200
        assert s.put(f"{API}/days/{d}", json={"content": ""}).status_code == 200
        assert content_of(board(s), d) == ""


# ---------------- inline conversion serialisation ----------------
class TestInlineConversionSerialisation:
    def test_bullet_heading_task_round_trip(self, user):
        s, _ = user
        d = today_str()
        text = "# EVENING\n- milk\n[ ] call mom"
        assert s.put(f"{API}/days/{d}", json={"content": text}).status_code == 200
        got = content_of(board(s), d)
        assert got == text, got

    def test_requires_auth(self):
        anon = requests.Session()
        assert anon.put(f"{API}/days/{today_str()}", json={"content": "x"}).status_code in (401, 403)
