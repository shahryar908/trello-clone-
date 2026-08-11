# Backend Specification

Stack: FastAPI + SQLModel + SQLite + PyJWT + passlib[bcrypt]. See `00-overview.md` for layout, error convention, and role rules.

`requirements.txt`:

```
fastapi
uvicorn[standard]
sqlmodel
pyjwt
passlib[bcrypt]
python-dotenv
```

`.env` keys: `SECRET_KEY` (long random string), `DATABASE_URL=sqlite:///./trello.db`, `ACCESS_TOKEN_EXPIRE_MINUTES=10080` (7 days).

---

## 1. Database schema — 9 tables (`models.py`)

All `id` columns: integer, primary key, auto-increment. All timestamps: UTC datetime, set server-side (`created_at` on insert, `updated_at` on every update). FK = foreign key with the referenced table's `id`.

### users
| column | type | rules |
|---|---|---|
| id | int PK | |
| email | str | unique, indexed |
| password | str | bcrypt hash — NEVER plain text, NEVER returned by any endpoint |

### orgs
| column | type | rules |
|---|---|---|
| id | int PK | |
| name | str | required |
| description | str \| None | optional |

### memberships
| column | type | rules |
|---|---|---|
| id | int PK | |
| user_id | int FK users | |
| org_id | int FK orgs | |
| role | str | `"member"` or `"admin"` only |
| | | unique constraint on (user_id, org_id) |

### boards
| column | type | rules |
|---|---|---|
| id | int PK | |
| title | str | required |
| organization_id | int FK orgs | |
| created_at / updated_at | datetime | |

### sections
| column | type | rules |
|---|---|---|
| id | int PK | |
| title | str | required |
| board_id | int FK boards | |
| position | float | ordering within board; new section = max(position)+1, or 1.0 if first |

### issues
| column | type | rules |
|---|---|---|
| id | int PK | |
| title | str | required |
| description | str \| None | |
| board_id | int FK boards | denormalized on purpose (cheap board-level queries); always equals its section's board_id |
| section_id | int FK sections | |
| position | float | ordering within section; new issue = max(position)+1 in that section, or 1.0 |
| due_date | date \| None | |
| created_at / updated_at | datetime | |

### labels
| column | type | rules |
|---|---|---|
| id | int PK | |
| name | str | required |
| color | str | hex string like `"#ef4444"` |
| board_id | int FK boards | labels are board-scoped |

### issue_labels
| column | type | rules |
|---|---|---|
| id | int PK | |
| issue_id | int FK issues | |
| label_id | int FK labels | |
| | | unique constraint on (issue_id, label_id) |

### comments
| column | type | rules |
|---|---|---|
| id | int PK | |
| body | str | required, non-empty |
| issue_id | int FK issues | |
| user_id | int FK users | the author |
| created_at | datetime | |

**Delete cascades (enforce in endpoint code, since SQLite FK cascade needs care):** deleting a board deletes its sections, issues, labels, issue_labels, comments. Deleting a section deletes its issues (and their issue_labels + comments). Deleting an issue deletes its issue_labels + comments. Deleting a label deletes its issue_labels rows.

---

## 2. Auth (`auth.py`)

- Hash with passlib `CryptContext(schemes=["bcrypt"])`.
- JWT: HS256, payload `{"sub": "<user_id as str>", "exp": <now + ACCESS_TOKEN_EXPIRE_MINUTES>}`, signed with `SECRET_KEY`.
- `get_current_user` FastAPI dependency: read `Authorization: Bearer <token>` header, decode, load user, raise 401 on any failure. Every endpoint below except signup/login requires it.

### POST /auth/signup
Request: `{"email": "a@b.com", "password": "secret123"}`
- 409 if email already registered.
- Response 201: `{"id": 1, "email": "a@b.com"}`

### POST /auth/login
Request: `{"email": "a@b.com", "password": "secret123"}`
- 401 `"Invalid email or password"` if no such user OR wrong password (same message for both — don't reveal which).
- Response 200: `{"access_token": "<jwt>", "token_type": "bearer"}`

---

## 3. Permission helpers (`deps.py`)

- `require_membership(org_id, user, session) -> Membership` — 404 if org doesn't exist, 403 if no membership row. Returns the membership.
- `require_admin(org_id, user, session) -> Membership` — same, plus 403 if role != admin.
- `get_board_or_404(board_id, session) -> Board` — then callers run `require_membership(board.organization_id, ...)`.
- Section/issue/label/comment endpoints resolve upward to the board, then to the org, and check membership. Rule of thumb: **every endpoint's first act is resolving the resource and proving membership.**

---

## 4. Org endpoints (`routers/orgs.py`)

### POST /orgs
Request: `{"name": "Zepto", "description": "quick commerce"}` (description optional)
- Creates org AND a membership row `{user_id: current_user.id, org_id, role: "admin"}` in the same transaction.
- Response 201: `{"id": 1, "name": "Zepto", "description": "quick commerce"}`

### GET /orgs
- Orgs the current user belongs to, with their role.
- Response 200: `[{"id": 1, "name": "Zepto", "description": "quick commerce", "role": "admin"}]`

### GET /orgs/{org_id}/members  (member-only)
- Response 200: `[{"user_id": 1, "email": "a@b.com", "role": "admin"}]`

### POST /orgs/{org_id}/members  (admin-only)
Request: `{"email": "teammate@x.com", "role": "member"}` (role optional, default `"member"`, must be member|admin)
- 404 `"No user with that email"` if the email isn't a registered user.
- 409 if already a member.
- Response 201: `{"user_id": 2, "email": "teammate@x.com", "role": "member"}`

---

## 5. Boards / sections / issues / labels / comments

### GET /orgs/{org_id}/boards  (member-only)
Response 200: `[{"id": 1, "title": "Frontend", "organization_id": 1, "created_at": "...", "updated_at": "..."}]`

### POST /orgs/{org_id}/boards  (member-only)
Request: `{"title": "Frontend"}` → 201, board object.

### GET /boards/{board_id}  (member-only) — the big one, powers the board page
Response 200:
```json
{
  "id": 1, "title": "Frontend", "organization_id": 1,
  "sections": [
    {
      "id": 1, "title": "Upcoming", "position": 1.0,
      "issues": [
        {"id": 1, "title": "fix bg", "description": null, "section_id": 1,
         "board_id": 1, "position": 1.0, "due_date": null, "label_ids": [1],
         "created_at": "...", "updated_at": "..."}
      ]
    }
  ],
  "labels": [{"id": 1, "name": "bug", "color": "#ef4444"}]
}
```
Sections sorted by position; issues sorted by position within each section.

### PATCH /boards/{board_id}  (member) — `{"title": "..."}` → 200 board.
### DELETE /boards/{board_id}  (ADMIN only) — cascade per §1 → 204.

### POST /boards/{board_id}/sections  (member)
Request: `{"title": "Upcoming"}` → 201 `{"id", "title", "board_id", "position"}` (position auto-assigned).

### PATCH /sections/{section_id}  (member) — `{"title"?: str, "position"?: float}` → 200.
### DELETE /sections/{section_id}  (member) — cascade its issues → 204.

### POST /sections/{section_id}/issues  (member)
Request: `{"title": "fix bg", "description": "...", "due_date": "2026-08-20"}` (only title required)
- Server sets `board_id` from the section and auto-assigns position. → 201 issue object.

### GET /issues/{issue_id}  (member)
Response 200: issue object + `"labels": [{"id","name","color"}]` (comments come from their own endpoint).

### PATCH /issues/{issue_id}  (member) — any of `{"title", "description", "due_date"}` → 200.

### PATCH /issues/{issue_id}/move  (member) — the drag & drop endpoint
Request: `{"section_id": 2, "position": 1.5}`
- 422/400 if target section's board_id != issue.board_id (cross-board moves not allowed).
- Sets both fields, bumps updated_at. → 200 issue object.
- **Position strategy (client-computed midpoint):** frontend computes `(prev.position + next.position) / 2` for the drop slot; dropped at top = `first.position / 2`; at bottom = `last.position + 1`; empty section = `1.0`. Server stores the float as-is. (Float precision exhaustion is accepted for v1 — do not build renormalization.)

### DELETE /issues/{issue_id}  (member) → 204.

### GET /boards/{board_id}/labels  (member) → 200 list.
### POST /boards/{board_id}/labels  (member) — `{"name": "bug", "color": "#ef4444"}` → 201.
### POST /issues/{issue_id}/labels  (member) — `{"label_id": 1}`; 409 if attached; 400 if label belongs to a different board → 201.
### DELETE /issues/{issue_id}/labels/{label_id}  (member) → 204.

### GET /issues/{issue_id}/comments  (member)
Response 200 (oldest first): `[{"id": 1, "body": "I think this is fixed", "created_at": "...", "author": {"id": 2, "email": "harkirat@gmail.com"}}]`
(No POST endpoint — comments are created over WebSocket, §6.)

---

## 6. WebSocket (`ws.py`)

### ConnectionManager
In-memory: `rooms: dict[int, dict[int, WebSocket]]` mapping `board_id -> {user_id: websocket}`. Methods: `connect`, `disconnect`, `broadcast(board_id, message: dict)` (JSON-send to every socket in the room, ignoring send failures). One connection per user per board (a reconnect replaces the old socket).

### Endpoint: `WS /ws/boards/{board_id}?token=<jwt>`
Connect flow:
1. Decode token → user (close with code 4401 on failure — browsers can't set headers on WS, hence the query param).
2. Board must exist and user must be a member of its org (close 4403 otherwise).
3. `accept()`, add to room, then broadcast `presence_changed` to the whole room.

On disconnect (`WebSocketDisconnect`): remove from room, broadcast `presence_changed`.

### Message protocol (all JSON)

**server → all clients in room:**
```json
{"type": "presence_changed", "users": [{"id": 1, "email": "a@b.com"}]}
```
```json
{"type": "comment_created", "comment": {"id": 5, "issue_id": 7, "body": "yes this is fixed",
  "created_at": "...", "author": {"id": 2, "email": "raman@gmail.com"}}}
```

**client → server (the only accepted incoming type):**
```json
{"type": "comment_create", "issue_id": 7, "body": "I think this is fixed"}
```
Handling: validate the issue exists AND `issue.board_id == board_id` of this room AND body is non-empty → save comment (author = connection's user) → broadcast `comment_created` to the room (sender included — the sender renders their comment from the broadcast, no local echo needed).

**server → sender only, on any invalid message:**
```json
{"type": "error", "detail": "reason"}
```
Never close the connection over a bad message; just reply with the error.

---

## 7. main.py

- `create_all` on startup.
- `CORSMiddleware`: allow origin `http://localhost:5173`, all methods/headers, credentials on.
- Include all routers + the WS endpoint.
