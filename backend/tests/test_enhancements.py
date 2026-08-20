"""Plain Todo — enhancement iteration backend tests.

Covers: group-aware carry-over (task owns notes/sub-tasks), rollover_enabled off,
carry_weekdays weekend skip, weekly / custom interval gating, backlog notes field,
settings validation (new schema).
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


ADMIN_EMAIL, ADMIN_PASSWORD = creds()


@pytest.fixture(scope="module")
def mongo():
    cli = MongoClient(BE["MONGO_URL"])
    yield cli[BE["DB_NAME"]]
    cli.close()


def _sess():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture
def user(mongo):
    """Fresh throwaway user, cleaned up after the test."""
    email = f"test_enh_{uuid.uuid4().hex[:8]}@example.com"
    s = _sess()
    r = s.post(f"{API}/auth/register", json={"email": email, "password": "secret1"})
    assert r.status_code == 200, r.text
    uid = r.json()["user_id"]
    yield s, uid
    for coll in ("days", "settings", "backlog", "users"):
        mongo[coll].delete_many({"user_id": uid} if coll != "users" else {"user_id": uid})


def _set_settings(s, **kw):
    body = {"rollover_enabled": True, "carry_weekdays": [0, 1, 2, 3, 4, 5, 6],
            "interval_mode": "daily", "interval_days": 1}
    body.update(kw)
    r = s.put(f"{API}/settings", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _reset_last_rollover(mongo, uid):
    mongo.settings.update_one({"user_id": uid}, {"$unset": {"last_rollover_date": ""}}, upsert=True)


def _content(board, date):
    return next((d["content"] for d in board["days"] if d["date"] == date), None)


# ---------------- group ownership on carry-over ----------------
class TestGroupCarryOver:
    def test_open_task_carries_its_notes_and_subtasks(self, user, mongo):
        s, uid = user
        past = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
        today = datetime.now().strftime("%Y-%m-%d")
        content = "\n".join([
            "# Work",
            "[ ] parent open",
            "  - note under parent",
            "  [ ] sub open",
            "  [x] sub done",
            "[x] other done",
            "- loose bullet",
        ])
        assert s.put(f"{API}/days/{past}", json={"content": content}).status_code == 200
        _set_settings(s)
        _reset_last_rollover(mongo, uid)

        board = s.get(f"{API}/board", params={"date": today}).json()
        t = _content(board, today)
        p = _content(board, past)
        # whole group moved
        assert "[ ] parent open" in t
        assert "  - note under parent" in t
        assert "  [ ] sub open" in t
        assert "  [x] sub done" in t
        # group lines removed from history
        assert "parent open" not in p
        assert "note under parent" not in p
        # done tasks / headings / loose bullets stay
        assert "# Work" in p and "[x] other done" in p and "- loose bullet" in p
        # not duplicated on second call
        board2 = s.get(f"{API}/board", params={"date": today}).json()
        assert _content(board2, today).count("[ ] parent open") == 1

    def test_rollover_disabled_keeps_task_in_past(self, user, mongo):
        s, uid = user
        past = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
        today = datetime.now().strftime("%Y-%m-%d")
        s.put(f"{API}/days/{past}", json={"content": "[ ] should stay"})
        _set_settings(s, rollover_enabled=False)
        _reset_last_rollover(mongo, uid)
        board = s.get(f"{API}/board", params={"date": today}).json()
        assert "should stay" in _content(board, past)
        assert "should stay" not in (_content(board, today) or "")


# ---------------- weekday / interval gating ----------------
class TestCarryWeekdaysAndInterval:
    def test_weekend_excluded_blocks_saturday(self, user, mongo):
        s, uid = user
        base = datetime.now() - timedelta(days=40)
        sat = base + timedelta(days=(5 - base.weekday()) % 7)
        fri = sat - timedelta(days=1)
        mon = sat + timedelta(days=2)
        s.put(f"{API}/days/{fri.strftime('%Y-%m-%d')}", json={"content": "[ ] friday task"})
        _set_settings(s, carry_weekdays=[0, 1, 2, 3, 4])
        _reset_last_rollover(mongo, uid)

        b_sat = s.get(f"{API}/board", params={"date": sat.strftime("%Y-%m-%d")}).json()
        assert "friday task" not in (_content(b_sat, sat.strftime("%Y-%m-%d")) or "")

        b_mon = s.get(f"{API}/board", params={"date": mon.strftime("%Y-%m-%d")}).json()
        assert "[ ] friday task" in (_content(b_mon, mon.strftime("%Y-%m-%d")) or "")

    def test_custom_interval_requires_elapsed_days(self, user, mongo):
        s, uid = user
        d0 = datetime.now() - timedelta(days=40)
        s.put(f"{API}/days/{d0.strftime('%Y-%m-%d')}", json={"content": "[ ] interval task"})
        _set_settings(s, interval_mode="custom", interval_days=5)
        # last rollover 2 days before target -> should not fire
        target = d0 + timedelta(days=3)
        mongo.settings.update_one(
            {"user_id": uid},
            {"$set": {"last_rollover_date": (target - timedelta(days=2)).strftime("%Y-%m-%d")}},
            upsert=True)
        b = s.get(f"{API}/board", params={"date": target.strftime("%Y-%m-%d")}).json()
        assert "interval task" not in (_content(b, target.strftime("%Y-%m-%d")) or "")

        # last rollover 6 days before -> should fire
        target2 = d0 + timedelta(days=8)
        mongo.settings.update_one(
            {"user_id": uid},
            {"$set": {"last_rollover_date": (target2 - timedelta(days=6)).strftime("%Y-%m-%d")}})
        b2 = s.get(f"{API}/board", params={"date": target2.strftime("%Y-%m-%d")}).json()
        assert "[ ] interval task" in (_content(b2, target2.strftime("%Y-%m-%d")) or "")

    def test_weekly_interval_step_is_seven(self, user, mongo):
        s, uid = user
        d0 = datetime.now() - timedelta(days=40)
        s.put(f"{API}/days/{d0.strftime('%Y-%m-%d')}", json={"content": "[ ] weekly task"})
        _set_settings(s, interval_mode="weekly")
        target = d0 + timedelta(days=4)
        mongo.settings.update_one(
            {"user_id": uid},
            {"$set": {"last_rollover_date": (target - timedelta(days=3)).strftime("%Y-%m-%d")}},
            upsert=True)
        b = s.get(f"{API}/board", params={"date": target.strftime("%Y-%m-%d")}).json()
        assert "weekly task" not in (_content(b, target.strftime("%Y-%m-%d")) or "")

        target2 = d0 + timedelta(days=12)
        mongo.settings.update_one(
            {"user_id": uid},
            {"$set": {"last_rollover_date": (target2 - timedelta(days=8)).strftime("%Y-%m-%d")}})
        b2 = s.get(f"{API}/board", params={"date": target2.strftime("%Y-%m-%d")}).json()
        assert "[ ] weekly task" in (_content(b2, target2.strftime("%Y-%m-%d")) or "")


# ---------------- settings endpoint ----------------
class TestSettingsSchema:
    def test_defaults_and_round_trip(self, user):
        s, _ = user
        today = datetime.now().strftime("%Y-%m-%d")
        board = s.get(f"{API}/board", params={"date": today}).json()
        st = board["settings"]
        assert st["rollover_enabled"] is True
        assert st["carry_weekdays"] == [0, 1, 2, 3, 4, 5, 6]
        assert st["interval_mode"] == "daily" and st["interval_days"] == 1

        out = _set_settings(s, rollover_enabled=False, carry_weekdays=[6, 0, 3],
                            interval_mode="custom", interval_days=4)
        assert out["carry_weekdays"] == [0, 3, 6], out
        reread = s.get(f"{API}/board", params={"date": today}).json()["settings"]
        assert reread == {"rollover_enabled": False, "carry_weekdays": [0, 3, 6],
                          "interval_mode": "custom", "interval_days": 4}

    def test_invalid_values_sanitised(self, user):
        s, _ = user
        bad = s.put(f"{API}/settings", json={"rollover_enabled": True, "carry_weekdays": [1],
                                            "interval_mode": "yearly", "interval_days": 1})
        assert bad.status_code == 400
        # out-of-range weekdays dropped; empty list falls back to all days
        out = _set_settings(s, carry_weekdays=[9, -2])
        assert out["carry_weekdays"] == [0, 1, 2, 3, 4, 5, 6]
        # interval_days floored at 1
        out2 = _set_settings(s, interval_mode="custom", interval_days=0)
        assert out2["interval_days"] == 1

    def test_settings_requires_auth(self):
        r = requests.put(f"{API}/settings", json={"rollover_enabled": True, "carry_weekdays": [0],
                                                 "interval_mode": "daily", "interval_days": 1})
        assert r.status_code in (401, 403)


# ---------------- backlog notes ----------------
class TestBacklogNotes:
    def test_backlog_item_notes_persist(self, user):
        s, _ = user
        today = datetime.now().strftime("%Y-%m-%d")
        items = [{"id": "b1", "text": "TEST_Buy groceries", "done": False,
                  "notes": "- milk and eggs\n[ ] check pantry"}]
        r = s.put(f"{API}/backlog", json={"items": items})
        assert r.status_code == 200, r.text
        assert r.json()["items"][0]["notes"] == "- milk and eggs\n[ ] check pantry"
        board = s.get(f"{API}/board", params={"date": today}).json()
        got = board["backlog"]["items"][0]
        assert got["text"] == "TEST_Buy groceries"
        assert got["notes"] == "- milk and eggs\n[ ] check pantry"
        assert "_id" not in got
        # clearing works
        assert s.put(f"{API}/backlog", json={"items": []}).status_code == 200
        assert s.get(f"{API}/board", params={"date": today}).json()["backlog"]["items"] == []
