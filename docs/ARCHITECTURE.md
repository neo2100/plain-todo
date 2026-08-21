# Architecture

```
┌────────────┐     /api/*      ┌──────────────┐      Motor       ┌──────────┐
│  React SPA │ ───────────────▶│  FastAPI     │ ───────────────▶ │ MongoDB  │
│ (PWA)      │◀─── httpOnly ───│  (server.py) │◀──────────────── │          │
└────────────┘   cookies       └──────────────┘                  └──────────┘
```

## Frontend (`frontend/src`)
- `pages/Board.jsx` — the app shell: loads the board, owns `days`/`backlog`/`settings`
  state, autosave manager, drag‑and‑drop (`DndContext`) and view switching.
- `pages/Login.jsx`, `pages/AuthCallback.jsx` — auth screens; Google OAuth callback handling.
- `components/DayEditor.jsx` — the rich per‑day editor: parses content into lines, renders
  draggable task **blocks**, handles checkbox cascade, indent, inline conversion and
  move‑to‑backlog.
- `components/FileEditor.jsx` — the single‑file view (all days in one textarea) with
  multi‑line Task/Note/Section conversion.
- `components/BacklogPanel.jsx` — backlog list + drop target.
- `components/Header.jsx` — nav, view toggle, save status, search, help, settings, user menu.
- `components/SettingsDialog.jsx`, `components/HelpSheet.jsx`.
- `context/AuthContext.jsx` — auth state via `/api/auth/me`.
- `lib/parser.js` — the text model: `parseContent`/`serializeLines`, `parseBlocks`/`groupEnd`
  (task grouping) and `toggleTaskCascade` (checkbox cascade).

### The text model
A day's content is a **plain string**. Each line is one of:
- Task: `[ ] text` / `[x] text`
- Bullet note: `- text`
- Section: `# Title`
- Free text, or blank.
Indentation (2 spaces = 1 level) nests items. A **task group** = a task plus the following
lines until the next task at the same/shallower indent or a heading — this group is the unit
that carries over, archives to the backlog and drags together.

## Backend (`backend/server.py`)
- All endpoints are under `/api`.
- **Auth**: `resolve_user()` accepts either a Google `session_token` (looked up in
  `user_sessions`) or a JWT `access_token`; both delivered as httpOnly cookies (Bearer header
  fallback). `/api/auth/{register,login,logout,me,session}`.
- **Board**: `GET /api/board?date=YYYY-MM-DD` runs carry‑over then returns all days, backlog
  and settings. `PUT /api/days/{date}`, `PUT /api/backlog`, `PUT /api/settings`.
- **Carry‑over** (`run_rollover` + `split_open_tasks`): moves open task groups from every
  day before `today` into `today`, honouring `rollover_enabled`, `carry_weekdays`,
  `interval_mode`/`interval_days`, and guarded to run at most once per day via
  `settings.last_rollover_date`.

## Auth flows
- **Email/password**: bcrypt hashes; JWT (7‑day) set as `access_token` httpOnly cookie.
- **Google (Emergent)**: frontend redirects to `auth.emergentagent.com`; the returned
  `session_id` is exchanged server‑side for a `session_token` stored in `user_sessions` and
  set as an httpOnly cookie.

## Autosave
The frontend coalesces edits per day (600 ms debounce), retries once on failure, and reports
`Saving… / Saved / Retry` — so a transient network blip never shows a false "save failed".
The backend day upsert is race‑safe against the concurrent carry‑over write
(`DuplicateKeyError` fallback).
