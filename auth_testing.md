# Auth Testing — Plain Todo

Two auth methods coexist:
1. Email/password (JWT cookie `access_token`, 7 days)
2. Emergent Google OAuth (cookie `session_token`, stored in `user_sessions`)

## Admin credentials
- Email: admin@plaintodo.com
- Password: admin123

## API tests
```
# Register
curl -c c.txt -X POST $URL/api/auth/register -H 'Content-Type: application/json' \
  -d '{"email":"t1@example.com","password":"secret1","name":"T1"}'

# Login (admin)
curl -c c.txt -X POST $URL/api/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"admin@plaintodo.com","password":"admin123"}'

# Me
curl -b c.txt $URL/api/auth/me

# Board for a date
curl -b c.txt "$URL/api/board?date=2026-06-09"

# Save a day
curl -b c.txt -X PUT $URL/api/days/2026-06-09 -H 'Content-Type: application/json' \
  -d '{"content":"[ ] first task\n- a note\n[x] done task"}'
```

## Google OAuth test (browser / mongosh session)
```
mongosh --eval "
use('test_database');
var uid='user_'+Date.now();
var tok='test_session_'+Date.now();
db.users.insertOne({user_id:uid,email:'g'+Date.now()+'@example.com',name:'G',picture:null,created_at:new Date().toISOString()});
db.user_sessions.insertOne({user_id:uid,session_token:tok,expires_at:new Date(Date.now()+7*864e5).toISOString(),created_at:new Date().toISOString()});
print(tok);
"
# Then: curl -H "Authorization: Bearer <tok>" $URL/api/auth/me
```

## Rollover
- Open tasks (`[ ]`) from days before `today` are removed from those days and appended to today's content on GET /api/board.
- `workdays` mode skips rollover on Sat/Sun.
- Completed tasks (`[x]`), bullets and notes stay in history.
