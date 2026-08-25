# Plain Todo PRD

## Original Problem Statement
A PWA-ready todo management web app ("Plain Todo") usable on phone. A plain-text-editor
style todo list for the day with checkboxes; unfinished tasks auto-move to the next day.
Editor feel: add checkbox tasks, bullet points and links; data conceptually a large text file.
See all previous days (each separated by a date title). Backlog to park tasks (side panel on
desktop, mobile-friendly). Auth so each user has a private canvas.

## Architecture
- **Frontend**: React 19 (CRA/craco), Tailwind, shadcn/ui, next-themes, framer-motion, sonner.
  PWA via `manifest.json` + `sw.js`. Fonts: Cabinet Grotesk (headings), IBM Plex Sans (UI),
  JetBrains Mono (editor). Swiss high-contrast monochrome theme, light/dark (system default).
- **Backend**: FastAPI + Motor (MongoDB). All routes under `/api`.
- **Auth (both)**: Email/password JWT (`access_token` httpOnly cookie) + Emergent Google OAuth
  (`session_token` cookie, `user_sessions` collection). `get_current_user` resolves either.
- **Data model**: `users`, `user_sessions`, `days` {user_id, date, content}, `backlog`
  {user_id, items[]}, `settings` {user_id, rollover_mode, last_rollover_date}.
- **Editor storage**: each day is a plain-text string (markdown-like: `[ ]`/`[x]` tasks, `-`
  bullets, URLs). Parsed on the client into structured lines for the rich view.

## User Personas
- Individual who wants a frictionless, keyboard-first daily task page that feels like a text file.

## Core Requirements (static)
- Daily canvas with checkbox tasks, bullets, links; date-titled day sections; history of days.
- Auto carry-over of unfinished tasks to the next day (configurable: everyday / workdays).
- Backlog to park tasks (desktop side panel, mobile drawer).
- Toggle between rich interactive editor and plain-text editor.
- Per-user private data; both email/password and Google auth.
- PWA installable; light/dark theme (system default).

## Implemented (2026-08-20)
- Email/password + Google auth; protected routes; logout (with pending-save flush).
- Board: today + all previous days, autosave (debounced, flushed on logout/unmount).
- Rich editor and plain-text editor with view toggle (persisted, mobile-reachable).
- Backlog panel with add / edit / complete / delete / move-to-today; mobile drawer.
- Auto rollover (config-driven) — only open `[ ]` task groups move; `[x]`, headings and
  loose bullets stay in history. Group = task + its notes/sub-tasks.
- Settings dialog for rollover mode; search across days; PWA manifest + service worker.

## Enhancements (2026-08-20, iterations 2-5)
- **Drag & drop**: reorder task groups within a day; drag a task onto the Backlog to park it
  (dnd-kit, mouse + touch). Groups move as a unit.
- **Task grouping**: a task owns the notes/sub-tasks under it; they carry over / archive together.
- **Checkbox cascade**: checking a parent checks all sub-tasks; when all children are checked the
  parent auto-checks; unchecking is independent.
- **Sections**: `# Title` heading lines to group tasks within a day (add-section button).
- **Advanced carry-over settings**: enable/disable, choose carry weekdays, and frequency
  (daily / weekly / custom every N days). Backend honours all of it.
- Backlog items store `notes` so a moved group keeps and restores its notes/sub-tasks (indent-stable).
- **Iteration 4-5**: cross-day drag; add past day (calendar); middle-insert `+`; inline conversion
  (`- `/`# `/`[] `); single-file view (all days in one file) with multi-line Task/Note/Section
  convert; quick-guide Help sheet + GitHub/Contact links; robust autosave (per-day retry +
  honest Saving/Saved/Retry status, race-safe backend upsert) fixing the false "Save failed";
  strict date validation; Docker Compose (BE+FE+Mongo), LICENSE (MIT), CONTRIBUTING, and
  docs/ (ARCHITECTURE, DATABASE, SHORTCUTS).
- Verified by testing agent across iterations: backend green (only missing brute-force lockout),
  all frontend/enhancement/regression flows pass.

## Backlog (prioritized)
- **P1**: Login brute-force/rate limiting (429 after N failures).
- **P2**: Async HTTP client (httpx) for Google session-data; purge expired `user_sessions`.
- **P2**: Pagination / date-range for GET /api/board (currently returns all days).
- **P2**: a11y roles on settings radio options.
- **P3**: Drag to reorder tasks; per-line task -> bullet conversion; reminders.

## Next Tasks
- Consider P1 rate limiting if abuse is a concern.
