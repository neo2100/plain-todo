# Plain Todo

A **PWA plain-text to‑do editor**. Each day is a simple text canvas: type `[ ]` checkbox
tasks, `-` bullet notes, links and `#` section titles. Unfinished tasks automatically roll
over to the next day, and anything you want to remember but not do today goes to the
**Backlog**. Works great on the phone (installable PWA) and on the desktop side‑by‑side.

Repo: https://github.com/neo2100/plain-todo/

---

## Features

- **Plain‑text daily canvas** — tasks, notes, links; each day has a date title; scroll back
  through all previous days.
- **Three views** — rich interactive editor, per‑day plain text, and a **single‑file** view
  that shows *all* days as one big text file (with `=== YYYY-MM-DD ===` day separators).
- **Grouped tasks** — notes / sub‑tasks written under a task belong to it and move with it.
- **Checkbox cascade** — checking a parent checks its sub‑tasks; a parent auto‑checks when
  all its children are done (unchecking stays independent).
- **Auto carry‑over** — unfinished tasks roll to the next day. Configurable: enable/disable,
  choose which weekdays to carry onto, and frequency (daily / weekly / every N days). Gaps
  are skipped — opening the app on a later date creates today and pulls forward open tasks.
- **Backlog** — park tasks (side panel on desktop, drawer on mobile); drag a task in, send it
  back to today with one click.
- **Drag & drop** — reorder within a day, move a task to another day, or drop it on the
  Backlog (mouse + touch).
- **Inline conversion** — start a line with `- `, `# ` or `[] ` to convert it live; select
  multiple lines in the single‑file view and bulk‑convert to Task / Note / Section.
- **Add past days** via a calendar picker.
- **Auth** — email/password (JWT) **and** Google sign‑in; every user has a private canvas.
- **Autosave** with an honest status indicator (Saving… / Saved / Retry) — never a false alarm.
- **Light/dark** theme (follows the system by default) and installable PWA (offline shell).

See [`docs/SHORTCUTS.md`](docs/SHORTCUTS.md) for the keyboard/typing guide (also in‑app via the
`?` button).

---

## Tech stack

| Layer     | Tech |
|-----------|------|
| Frontend  | React 19, Tailwind, shadcn/ui, dnd‑kit, next‑themes, framer‑motion |
| Backend   | FastAPI, Motor (async MongoDB), PyJWT, bcrypt |
| Database  | MongoDB |
| Auth      | JWT (email/password) + Emergent‑managed Google OAuth |

Architecture details: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
Database model & management: [`docs/DATABASE.md`](docs/DATABASE.md).

---

## Run locally (Docker Compose)

```bash
docker compose up --build
```

- Frontend: http://localhost:8080
- Backend API: http://localhost:8001/api
- MongoDB: localhost:27017
- Default admin: `admin@plaintodo.com` / `admin123`

> The compose file sets `COOKIE_SECURE=false` / `COOKIE_SAMESITE=lax` so auth cookies work over
> plain HTTP locally. **In production, serve over HTTPS** and keep the defaults
> (`COOKIE_SECURE=true`, `SameSite=None`). Google OAuth requires an HTTPS origin.

## Run locally (without Docker)

Backend:
```bash
cd backend
pip install -r requirements.txt --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/
# .env: MONGO_URL, DB_NAME, JWT_SECRET, CORS_ORIGINS, FRONTEND_URL, ADMIN_EMAIL, ADMIN_PASSWORD
uvicorn server:app --host 0.0.0.0 --port 8001
```

Frontend:
```bash
cd frontend
yarn install
# .env: REACT_APP_BACKEND_URL=http://localhost:8001
yarn start
```

---

## Environment variables

**Backend** (`backend/.env`)

| Key | Purpose |
|-----|---------|
| `MONGO_URL` | MongoDB connection string |
| `DB_NAME` | Database name |
| `JWT_SECRET` | Secret for signing JWT access tokens |
| `CORS_ORIGINS` | Comma‑separated allowed origins |
| `FRONTEND_URL` | Frontend origin |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | Seeded admin account |
| `COOKIE_SECURE` | `true` (default) or `false` for local HTTP |
| `COOKIE_SAMESITE` | `none` (default when secure) / `lax` |

**Frontend** (`frontend/.env`)

| Key | Purpose |
|-----|---------|
| `REACT_APP_BACKEND_URL` | Base URL the frontend calls (must expose `/api`) |

---

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Licensed under the [MIT License](LICENSE).
