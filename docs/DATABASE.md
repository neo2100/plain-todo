# Database

Plain Todo uses **MongoDB**, accessed asynchronously via **Motor**. The connection string
and database name come only from environment variables (`MONGO_URL`, `DB_NAME`) — never
hardcoded.

## Connection & lifecycle
- `server.py` creates one `AsyncIOMotorClient(MONGO_URL)` at startup and uses
  `client[DB_NAME]`.
- On **startup** it creates indexes and seeds the admin account.
- On **shutdown** it closes the client.

## Identity pattern
Every user has a self‑generated `user_id` (e.g. `user_ab12cd34ef56`). All app data is scoped
by `user_id`, and Mongo's internal `_id` is always excluded from API responses (`{"_id": 0}`
projections / explicit field lists) so it never leaks to the client.

## Collections

### `users`
```jsonc
{
  "user_id": "user_ab12cd34ef56",  // primary app id
  "email": "a@b.com",              // unique, lowercased
  "name": "Ada",
  "picture": null,                  // set for Google users
  "password_hash": "$2b$...",      // bcrypt; null for Google‑only users
  "role": "admin",                 // optional
  "created_at": "2026-08-20T..."
}
```

### `user_sessions` (Google OAuth)
```jsonc
{ "user_id": "...", "session_token": "...", "expires_at": "ISO", "created_at": "ISO" }
```

### `days` — one document per user per calendar day
```jsonc
{
  "user_id": "...",
  "date": "2026-08-20",            // YYYY-MM-DD
  "content": "[ ] task\n  - note\n# Section",  // the plain-text canvas
  "updated_at": "ISO"
}
```

### `backlog` — one document per user
```jsonc
{
  "user_id": "...",
  "items": [ { "id": "abc123", "text": "Task", "done": false, "notes": "  - a note" } ],
  "updated_at": "ISO"
}
```

### `settings` — one document per user
```jsonc
{
  "user_id": "...",
  "rollover_enabled": true,
  "carry_weekdays": [0,1,2,3,4,5,6],   // 0=Mon .. 6=Sun
  "interval_mode": "daily",             // daily | weekly | custom
  "interval_days": 1,
  "last_rollover_date": "2026-08-20"   // guards once-per-day carry-over
}
```

## Indexes (created on startup)
| Collection | Index | Type |
|------------|-------|------|
| `users` | `email` | unique |
| `users` | `user_id` | standard |
| `user_sessions` | `session_token` | standard |
| `days` | `(user_id, date)` | unique |

The `days` unique index guarantees one document per day per user. Because carry‑over may
upsert *today* at the same time the client saves it, `save_day` and `run_rollover` share a
race‑safe `_upsert_day` helper that falls back to a plain update on `DuplicateKeyError`.

## Datetimes
All timestamps are timezone‑aware UTC (`datetime.now(timezone.utc)`), stored as ISO strings.

## Backups / operations
- Back up with `mongodump --uri "$MONGO_URL" --db "$DB_NAME"`; restore with `mongorestore`.
- In Docker Compose, data persists in the `mongo_data` named volume.
- All queries are user‑scoped by `user_id`, which is the key sharding/partition dimension if
  the app ever needs to scale horizontally.
