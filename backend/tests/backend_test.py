"""Plain Todo backend API tests."""
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")
API = f"{BASE_URL}/api"


def creds():
    p = Path("/app/memory/test_credentials.md")
    c = p.read_text(encoding="utf-8")
    e = re.search(r"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?email(?:\*\*)?\s*:\s*`?([^`\s]+)", c)
    pw = re.search(r"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?password(?:\*\*)?\s*:\s*`?([^`\s]+)", c)
    return e.group(1), pw.group(1)


ADMIN_EMAIL, ADMIN_PASSWORD = creds()


def new_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def today_str():
    return datetime.now().strftime("%Y-%m-%d")


# ---------------- health / root ----------------
class TestHealth:
    def test_root(self):
        r = requests.get(f"{API}/")
        assert r.status_code == 200
        assert r.json().get("message") == "Plain Todo API"


# ---------------- auth ----------------
class TestAuth:
    def test_login_success_sets_cookie(self):
        s = new_session()
        r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["email"] == ADMIN_EMAIL
        assert isinstance(d["user_id"], str) and d["user_id"].startswith("user_")
        assert "_id" not in d
        assert "password_hash" not in d
        assert "access_token" in s.cookies.get_dict(), s.cookies.get_dict()
        # cookie flags
        raw = r.headers.get("set-cookie", "")
        assert "HttpOnly" in raw and "Secure" in raw, raw

    def test_login_wrong_password(self):
        r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": "wrongpass"})
        assert r.status_code == 401
        assert "detail" in r.json()

    def test_login_unknown_email(self):
        r = requests.post(f"{API}/auth/login", json={"email": f"nobody{uuid.uuid4().hex[:6]}@x.com", "password": "x"})
        assert r.status_code == 401

    def test_login_invalid_email_format(self):
        r = requests.post(f"{API}/auth/login", json={"email": "notanemail", "password": "abcdef"})
        assert r.status_code == 422

    def test_me_unauthenticated(self):
        r = requests.get(f"{API}/auth/me")
        assert r.status_code == 401

    def test_me_authenticated(self):
        s = new_session()
        s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        r = s.get(f"{API}/auth/me")
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN_EMAIL

    def test_register_and_duplicate_and_short_password(self):
        email = f"TEST_{uuid.uuid4().hex[:8]}@example.com".lower()
        s = new_session()
        r = s.post(f"{API}/auth/register", json={"email": email, "password": "secret1", "name": "TEST User"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["email"] == email and d["name"] == "TEST User"
        assert "access_token" in s.cookies.get_dict()
        # session works
        assert s.get(f"{API}/auth/me").json()["email"] == email
        # duplicate
        r2 = requests.post(f"{API}/auth/register", json={"email": email, "password": "secret1"})
        assert r2.status_code == 400
        # short password
        r3 = requests.post(f"{API}/auth/register",
                           json={"email": f"TEST_{uuid.uuid4().hex[:8]}@example.com", "password": "abc"})
        assert r3.status_code == 422

    def test_logout_clears_session(self):
        s = new_session()
        s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        r = s.post(f"{API}/auth/logout")
        assert r.status_code == 200 and r.json() == {"ok": True}
        assert s.get(f"{API}/auth/me").status_code == 401

    def test_google_session_missing_id(self):
        r = requests.post(f"{API}/auth/session", json={})
        assert r.status_code == 400

    def test_google_session_invalid_id(self):
        r = requests.post(f"{API}/auth/session", headers={"X-Session-ID": "invalid-session-xyz"})
        assert r.status_code == 401

    def test_bearer_session_token_auth(self):
        """Simulated Google user (mongosh-style insert via pymongo) authenticates with Bearer token."""
        from pymongo import MongoClient
        be = dotenv_values("/app/backend/.env")
        cli = MongoClient(be["MONGO_URL"])
        db = cli[be["DB_NAME"]]
        uid = f"user_TEST_{uuid.uuid4().hex[:8]}"
        tok = f"TEST_session_{uuid.uuid4().hex}"
        email = f"TEST_g_{uuid.uuid4().hex[:6]}@example.com"
        db.users.insert_one({"user_id": uid, "email": email, "name": "TEST Google",
                             "picture": None, "created_at": datetime.now(timezone.utc).isoformat()})
        db.user_sessions.insert_one({
            "user_id": uid, "session_token": tok,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat()})
        try:
            r = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {tok}"})
            assert r.status_code == 200, r.text
            assert r.json()["email"] == email
            # board access works for google user
            rb = requests.get(f"{API}/board", params={"date": today_str()},
                              headers={"Authorization": f"Bearer {tok}"})
            assert rb.status_code == 200
            # expired token rejected
            db.user_sessions.update_one({"session_token": tok}, {"$set": {
                "expires_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()}})
            assert requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {tok}"}).status_code == 401
        finally:
            db.user_sessions.delete_many({"user_id": uid})
            db.users.delete_many({"user_id": uid})
            db.days.delete_many({"user_id": uid})
            db.settings.delete_many({"user_id": uid})
            cli.close()

    def test_bcrypt_hash_format(self):
        from pymongo import MongoClient
        be = dotenv_values("/app/backend/.env")
        cli = MongoClient(be["MONGO_URL"])
        db = cli[be["DB_NAME"]]
        u = db.users.find_one({"email": ADMIN_EMAIL})
        cli.close()
        assert u is not None
        assert u["password_hash"].startswith("$2b$"), u["password_hash"][:6]

    def test_brute_force_lockout(self):
        """Playbook expects lockout after 5 failed attempts."""
        email = f"TEST_bf_{uuid.uuid4().hex[:8]}@example.com".lower()
        requests.post(f"{API}/auth/register", json={"email": email, "password": "secret1"})
        codes = []
        for _ in range(6):
            codes.append(requests.post(f"{API}/auth/login",
                                       json={"email": email, "password": "badpass"}).status_code)
        assert any(c == 429 for c in codes), f"No lockout; codes={codes}"


# ---------------- board / days ----------------
@pytest.fixture(scope="class")
def auth_client():
    s = new_session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    if r.status_code != 200:
        pytest.fail(f"login failed: {r.status_code} {r.text}")
    return s


class TestBoard:
    def test_board_requires_auth(self):
        assert requests.get(f"{API}/board", params={"date": today_str()}).status_code == 401

    def test_board_invalid_date(self, auth_client):
        r = auth_client.get(f"{API}/board", params={"date": "2026/06/09"})
        assert r.status_code == 400

    def test_board_missing_date_param(self, auth_client):
        r = auth_client.get(f"{API}/board")
        assert r.status_code == 422

    def test_board_shape(self, auth_client):
        t = today_str()
        r = auth_client.get(f"{API}/board", params={"date": t})
        assert r.status_code == 200
        d = r.json()
        assert d["today"] == t
        assert isinstance(d["days"], list)
        assert any(x["date"] == t for x in d["days"])
        assert "items" in d["backlog"]
        assert d["settings"]["rollover_mode"] in ("everyday", "workdays")
        for day in d["days"]:
            assert set(day.keys()) == {"date", "content"}

    def test_save_day_and_persist(self, auth_client):
        t = today_str()
        content = "[ ] TEST task one\n- TEST note\nhttps://example.com"
        r = auth_client.put(f"{API}/days/{t}", json={"content": content})
        assert r.status_code == 200 and r.json() == {"ok": True}
        board = auth_client.get(f"{API}/board", params={"date": t}).json()
        day = next(x for x in board["days"] if x["date"] == t)
        assert day["content"] == content

    def test_save_day_invalid_date(self, auth_client):
        assert auth_client.put(f"{API}/days/13-01-2026", json={"content": "x"}).status_code == 400

    def test_save_day_requires_auth(self):
        assert requests.put(f"{API}/days/{today_str()}", json={"content": "x"}).status_code == 401

    def test_backlog_crud(self, auth_client):
        items = [{"id": "abc1234567", "text": "TEST backlog item", "done": False}]
        r = auth_client.put(f"{API}/backlog", json={"items": items})
        assert r.status_code == 200
        assert r.json()["items"][0]["text"] == "TEST backlog item"
        board = auth_client.get(f"{API}/board", params={"date": today_str()}).json()
        assert board["backlog"]["items"][0]["text"] == "TEST backlog item"
        # update done
        items[0]["done"] = True
        auth_client.put(f"{API}/backlog", json={"items": items})
        board = auth_client.get(f"{API}/board", params={"date": today_str()}).json()
        assert board["backlog"]["items"][0]["done"] is True
        # clear
        auth_client.put(f"{API}/backlog", json={"items": []})
        board = auth_client.get(f"{API}/board", params={"date": today_str()}).json()
        assert board["backlog"]["items"] == []

    def test_backlog_autogen_id(self, auth_client):
        r = auth_client.put(f"{API}/backlog", json={"items": [{"text": "TEST no id"}]})
        assert r.status_code == 200
        assert len(r.json()["items"][0]["id"]) == 10
        auth_client.put(f"{API}/backlog", json={"items": []})

    def test_settings_persist_and_validation(self, auth_client):
        r = auth_client.put(f"{API}/settings", json={"rollover_mode": "workdays"})
        assert r.status_code == 200 and r.json()["rollover_mode"] == "workdays"
        board = auth_client.get(f"{API}/board", params={"date": today_str()}).json()
        assert board["settings"]["rollover_mode"] == "workdays"
        bad = auth_client.put(f"{API}/settings", json={"rollover_mode": "monthly"})
        assert bad.status_code == 400
        auth_client.put(f"{API}/settings", json={"rollover_mode": "everyday"})


# ---------------- rollover ----------------
class TestRollover:
    def _db(self):
        from pymongo import MongoClient
        be = dotenv_values("/app/backend/.env")
        cli = MongoClient(be["MONGO_URL"])
        return cli, cli[be["DB_NAME"]]

    def test_rollover_moves_only_open_tasks(self):
        email = f"TEST_roll_{uuid.uuid4().hex[:8]}@example.com".lower()
        s = new_session()
        reg = s.post(f"{API}/auth/register", json={"email": email, "password": "secret1"})
        assert reg.status_code == 200
        uid = reg.json()["user_id"]
        cli, db = self._db()
        try:
            past = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
            t = today_str()
            past_content = "[ ] open past task\n[x] done past task\n- past note"
            r = s.put(f"{API}/days/{past}", json={"content": past_content})
            assert r.status_code == 200
            # ensure rollover not already marked for today
            db.settings.delete_many({"user_id": uid})
            board = s.get(f"{API}/board", params={"date": t}).json()
            today_content = next(x["content"] for x in board["days"] if x["date"] == t)
            past_after = next(x["content"] for x in board["days"] if x["date"] == past)
            assert "[ ] open past task" in today_content, today_content
            assert "[ ] open past task" not in past_after
            assert "[x] done past task" in past_after
            assert "- past note" in past_after
            # idempotent: second call same day should not duplicate
            board2 = s.get(f"{API}/board", params={"date": t}).json()
            c2 = next(x["content"] for x in board2["days"] if x["date"] == t)
            assert c2.count("[ ] open past task") == 1, c2
        finally:
            db.days.delete_many({"user_id": uid})
            db.settings.delete_many({"user_id": uid})
            db.backlog.delete_many({"user_id": uid})
            db.users.delete_many({"user_id": uid})
            cli.close()

    def test_rollover_workdays_skips_weekend(self):
        email = f"TEST_wd_{uuid.uuid4().hex[:8]}@example.com".lower()
        s = new_session()
        uid = s.post(f"{API}/auth/register", json={"email": email, "password": "secret1"}).json()["user_id"]
        cli, db = self._db()
        try:
            s.put(f"{API}/settings", json={"rollover_mode": "workdays"})
            # find a past monday and the saturday after it
            base = datetime.now() - timedelta(days=30)
            sat = base + timedelta(days=(5 - base.weekday()) % 7)
            fri = sat - timedelta(days=1)
            s.put(f"{API}/days/{fri.strftime('%Y-%m-%d')}", json={"content": "[ ] friday open task"})
            db.settings.update_one({"user_id": uid}, {"$unset": {"last_rollover_date": ""}})
            board = s.get(f"{API}/board", params={"date": sat.strftime("%Y-%m-%d")}).json()
            sat_content = next((x["content"] for x in board["days"] if x["date"] == sat.strftime("%Y-%m-%d")), "")
            assert "friday open task" not in sat_content, "workdays mode rolled over onto Saturday"
        finally:
            db.days.delete_many({"user_id": uid})
            db.settings.delete_many({"user_id": uid})
            db.users.delete_many({"user_id": uid})
            cli.close()


# ---------------- data isolation ----------------
class TestIsolation:
    def test_users_do_not_see_each_others_data(self):
        from pymongo import MongoClient
        be = dotenv_values("/app/backend/.env")
        cli = MongoClient(be["MONGO_URL"])
        db = cli[be["DB_NAME"]]
        t = today_str()
        e1 = f"TEST_iso1_{uuid.uuid4().hex[:6]}@example.com".lower()
        e2 = f"TEST_iso2_{uuid.uuid4().hex[:6]}@example.com".lower()
        s1, s2 = new_session(), new_session()
        u1 = s1.post(f"{API}/auth/register", json={"email": e1, "password": "secret1"}).json()["user_id"]
        u2 = s2.post(f"{API}/auth/register", json={"email": e2, "password": "secret1"}).json()["user_id"]
        try:
            s1.put(f"{API}/days/{t}", json={"content": "[ ] user1 secret task"})
            s1.put(f"{API}/backlog", json={"items": [{"text": "user1 backlog"}]})
            b2 = s2.get(f"{API}/board", params={"date": t}).json()
            all_content = "".join(d["content"] for d in b2["days"])
            assert "user1 secret task" not in all_content
            assert b2["backlog"]["items"] == []
        finally:
            for u in (u1, u2):
                db.days.delete_many({"user_id": u})
                db.backlog.delete_many({"user_id": u})
                db.settings.delete_many({"user_id": u})
                db.users.delete_many({"user_id": u})
            cli.close()
