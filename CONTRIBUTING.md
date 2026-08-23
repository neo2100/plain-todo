# Contributing to Plain Todo

Thanks for your interest in improving Plain Todo! 🎉

Repo: https://github.com/neo2100/plain-todo/

## Ways to contribute
- Report bugs or request features via [GitHub Issues](https://github.com/neo2100/plain-todo/issues).
- Improve docs.
- Submit pull requests for fixes and features.

## Development setup
See the "Run locally" sections in [`README.md`](README.md). Quickest path:

```bash
docker compose up --build
```

Or run backend (`uvicorn server:app --port 8001`) and frontend (`yarn start`) separately.

## Project layout
```
backend/    FastAPI app (server.py), tests in backend/tests/
frontend/   React app (src/pages, src/components, src/lib)
docs/       Architecture, database and shortcut docs
```

## Coding guidelines
- **Backend**: keep all routes under `/api`; never hardcode secrets (use env vars); use
  timezone‑aware datetimes; keep MongoDB access via Motor and never leak `_id`.
- **Frontend**: use existing shadcn/ui components; every interactive element needs a
  `data-testid`; use the design tokens (`bg-background`, `text-foreground`, etc.); keep
  components small.
- Match the existing style; keep changes focused.

## Tests
Backend test suites live in `backend/tests/`:
```bash
cd backend && python -m pytest tests/ -q
```
Please add/adjust tests for behavioural changes.

## Pull requests
1. Fork and create a feature branch.
2. Make focused commits with clear messages.
3. Ensure the app builds and tests pass.
4. Open a PR describing the change and linking any related issue.

## Code of conduct
Be respectful and constructive. Assume good intent.
