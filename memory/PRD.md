# Plain Todo — PRD

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
- Email/password + Google auth; protected routes; logout.
- Board: today + all previous days, autosave (debounced, flushed on logout/unmount).
- Rich editor (checkbox toggle, add task/bullet, Enter/Backspace/Tab handling, links,
  move-to-backlog) and plain-text textarea; view toggle persisted (localStorage), mobile-reachable.
- Backlog panel with add / edit / complete / delete / move-to-today; mobile drawer.
- Auto rollover (everyday + workdays weekend-skip, once/day idempotent) — only open `[ ]`
  tasks move; `[x]` and bullets stay in history.
- Settings dialog for rollover mode; search across days; PWA manifest + service worker.
- Verified by testing agent: backend 26/27, all tested frontend flows pass.

## Backlog (prioritized)
- **P1**: Login brute-force/rate limiting (429 after N failures).
- **P2**: Async HTTP client (httpx) for Google session-data; purge expired `user_sessions`.
- **P2**: Pagination / date-range for GET /api/board (currently returns all days).
- **P2**: a11y roles on settings radio options.
- **P3**: Drag to reorder tasks; per-line task -> bullet conversion; reminders.

## Next Tasks
- Consider P1 rate limiting if abuse is a concern.
