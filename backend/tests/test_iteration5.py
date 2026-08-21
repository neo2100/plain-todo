"""Iteration 5 backend tests: date validation, rollover across day gaps, save robustness."""
import os
import re
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
API = base_url.rstrip("/") + "/api"

DB = dotenv_values("/app/backend/.env").get("DB_NAME") or "test_database"


def creds():
    content = Path("/app/memory/test_credentials.md").read_text()
    email = re.search(r"(?im)^\s*-\s*Email:\s*(\S+)", content).group(1)
    password = re.search(r"(?im)^\s*-\s*Password:\s*(\S+)", content).group(1)
    return email, password


def mongo(script):
    out = subprocess.run(["mongosh", "--quiet", DB, "--eval", script],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return out.stdout


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    email, password = creds()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def uid(client):
    r = client.get(f"{API}/auth/me")
    assert r.status_code == 200
    return r.json()["user_id"]


@pytest.fixture(scope="module")
def snapshot(uid):
    """Backup then restore admin days/settings around this module."""
    days = json.loads(mongo(f'print(JSON.stringify(db.days.find({{user_id:"{uid}"}},{{_id:0}}).toArray()))'))
    settings = json.loads(mongo(f'print(JSON.stringify(db.settings.findOne({{user_id:"{uid}"}},{{_id:0}}) || {{}}))'))
    yield days
    mongo(f'db.days.deleteMany({{user_id:"{uid}"}})')
    if days:
        mongo(f'db.days.insertMany({json.dumps(days)})')
    mongo(f'db.settings.replaceOne({{user_id:"{uid}"}},{json.dumps({**settings, "user_id": uid})},{{upsert:true}})')


# --- Date validation (GET /api/board, PUT /api/days/{date}) -------------------
@pytest.mark.parametrize("bad", ["2026-02-30", "2026-13-01", "20260101", "abcd-ef-gh", "2026-00-10"])
def test_invalid_date_board(client, bad):
    r = client.get(f"{API}/board", params={"date": bad})
    assert r.status_code == 400, f"{bad} -> {r.status_code} {r.text[:200]}"
    assert "Invalid date" in r.text


@pytest.mark.parametrize("bad", ["2026-02-30", "2026-13-01", "2026-04-31"])
def test_invalid_date_put_day(client, bad):
    r = client.put(f"{API}/days/{bad}", json={"content": "x"})
    assert r.status_code == 400, f"{bad} -> {r.status_code}"


def test_valid_leap_date_accepted(client, snapshot):
    r = client.put(f"{API}/days/2024-02-29", json={"content": "[x] leap"})
    assert r.status_code == 200
    got = client.get(f"{API}/board", params={"date": "2024-02-29"})
    assert got.status_code == 200
    day = next(d for d in got.json()["days"] if d["date"] == "2024-02-29")
    assert day["content"] == "[x] leap"


# --- Rollover / carry-forward across gaps ------------------------------------
def test_carry_forward_skips_gap_days(client, uid, snapshot):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    past = (datetime.now(timezone.utc) - timedelta(days=6)).strftime("%Y-%m-%d")

    mongo(f'db.days.deleteMany({{user_id:"{uid}"}})')
    mongo(f'db.settings.updateOne({{user_id:"{uid}"}},{{$set:{{last_rollover_date:null,rollover_enabled:true,carry_weekdays:[0,1,2,3,4,5,6],interval_mode:"daily",interval_days:1}}}},{{upsert:true}})')

    seed = "[ ] TEST_carry_me\n  - TEST_note\n[x] TEST_already_done"
    assert client.put(f"{API}/days/{past}", json={"content": seed}).status_code == 200

    r = client.get(f"{API}/board", params={"date": today})
    assert r.status_code == 200, r.text
    data = r.json()
    by_date = {d["date"]: d["content"] for d in data["days"]}

    # today exists and holds the carried open task group
    assert today in by_date
    assert "TEST_carry_me" in by_date[today]
    assert "TEST_note" in by_date[today]
    assert "TEST_already_done" not in by_date[today]

    # completed task stays in history, open one removed from the past day
    assert past in by_date
    assert "TEST_already_done" in by_date[past]
    assert "TEST_carry_me" not in by_date[past]

    # no in-between days created
    assert set(by_date) == {today, past}, f"unexpected days: {sorted(by_date)}"

    # today's day is actually persisted in the DB
    cnt = mongo(f'print(db.days.countDocuments({{user_id:"{uid}",date:"{today}"}}))').strip()
    assert cnt == "1", f"today not persisted, count={cnt}"


def test_rollover_idempotent_second_call(client, uid, snapshot):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    r1 = client.get(f"{API}/board", params={"date": today})
    r2 = client.get(f"{API}/board", params={"date": today})
    assert r1.status_code == r2.status_code == 200
    c1 = next(d["content"] for d in r1.json()["days"] if d["date"] == today)
    c2 = next(d["content"] for d in r2.json()["days"] if d["date"] == today)
    assert c1 == c2, "rollover duplicated content on second board load"


def test_rollover_disabled_does_not_carry(client, uid, snapshot):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    past = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%d")
    mongo(f'db.days.deleteMany({{user_id:"{uid}"}})')
    mongo(f'db.settings.updateOne({{user_id:"{uid}"}},{{$set:{{last_rollover_date:null,rollover_enabled:false}}}},{{upsert:true}})')
    client.put(f"{API}/days/{past}", json={"content": "[ ] TEST_stay_put"})
    data = client.get(f"{API}/board", params={"date": today}).json()
    by_date = {d["date"]: d["content"] for d in data["days"]}
    assert "TEST_stay_put" in by_date[past]
    assert "TEST_stay_put" not in by_date.get(today, "")
    mongo(f'db.settings.updateOne({{user_id:"{uid}"}},{{$set:{{rollover_enabled:true}}}})')


# --- Save robustness (repeated PUTs must never fail) -------------------------
def test_rapid_repeated_day_saves(client, snapshot):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    codes = []
    for i in range(15):
        r = client.put(f"{API}/days/{today}", json={"content": f"[ ] TEST_rapid {i}"})
        codes.append(r.status_code)
    assert all(c == 200 for c in codes), codes
    data = client.get(f"{API}/board", params={"date": today}).json()
    content = next(d["content"] for d in data["days"] if d["date"] == today)
    assert "TEST_rapid 14" in content, content
    assert "TEST_rapid 13" not in content, content


def test_rapid_settings_and_backlog_saves(client, snapshot):
    codes = []
    for i in range(10):
        codes.append(client.put(f"{API}/settings", json={
            "rollover_enabled": True, "carry_weekdays": [0, 1, 2, 3, 4],
            "interval_mode": "daily", "interval_days": 1}).status_code)
        codes.append(client.put(f"{API}/backlog", json={
            "items": [{"id": "t1", "text": f"TEST_b{i}", "done": False, "notes": ""}]}).status_code)
    assert all(c == 200 for c in codes), codes
    # restore defaults + empty backlog
    assert client.put(f"{API}/settings", json={
        "rollover_enabled": True, "carry_weekdays": [0, 1, 2, 3, 4, 5, 6],
        "interval_mode": "daily", "interval_days": 1}).status_code == 200
    assert client.put(f"{API}/backlog", json={"items": []}).status_code == 200


def test_unauthenticated_board_is_401():
    r = requests.get(f"{API}/board", params={"date": "2026-08-21"})
    assert r.status_code == 401
