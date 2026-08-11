# Trello Clone — Project Overview

A Trello/Jira-style project management app. Users belong to organizations, organizations own boards, boards contain sections (columns), sections contain issues (cards). Issues support labels, due dates, and realtime comments. The board page shows live presence of connected users.

## Locked technology decisions (do NOT substitute)

| Layer | Choice |
|---|---|
| Backend HTTP + WebSocket | FastAPI |
| ORM | SQLModel |
| Database | SQLite (file-based, via SQLModel `create_all` — no Alembic in v1) |
| JWT | PyJWT |
| Password hashing | passlib[bcrypt] |
| Frontend | React, run with Bun |
| Auth style | Custom JWT (NO Supabase, NO third-party auth) |

## Repository layout

```
trello-clone/
├── docs/                    # these spec files
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI app, CORS, router registration
│   │   ├── config.py        # loads .env (SECRET_KEY, DATABASE_URL)
│   │   ├── database.py      # engine + get_session dependency
│   │   ├── models.py        # all 9 SQLModel table classes
│   │   ├── schemas.py       # request/response Pydantic models
│   │   ├── auth.py          # hashing, JWT create/verify, get_current_user
│   │   ├── deps.py          # shared permission helpers (require_membership etc.)
│   │   ├── ws.py            # ConnectionManager + WS endpoint
│   │   └── routers/
│   │       ├── auth.py
│   │       ├── orgs.py
│   │       ├── boards.py
│   │       ├── sections.py
│   │       ├── issues.py
│   │       └── labels.py
│   ├── requirements.txt
│   └── .env                 # never committed
├── frontend/                # see 02-frontend-spec.md
└── .gitignore
```

## Core architectural rules

1. **HTTP for all writes except comments.** Every create/update/delete goes through REST endpoints. The single exception: comments are created by sending a WebSocket message (see backend spec §6).
2. **WebSocket scope is deliberately narrow:** board page only, carrying exactly (a) live presence and (b) realtime comments. Card/section changes are NOT broadcast in v1.
3. **Table models never cross the API boundary.** Every endpoint uses separate request/response schemas from `schemas.py`. The `password` column must be impossible to serialize into a response.
4. **All permission checks go through shared helpers** in `deps.py` — never inline-duplicated in routers.
5. **Issue view is a modal over the board page** (route `/boards/:boardId/issues/:issueId`), so the board's WS connection stays open while viewing an issue.

## Error convention (used by every endpoint)

| Status | Meaning | Example |
|---|---|---|
| 401 | Missing/invalid/expired JWT | bad token |
| 403 | Resource exists but requester lacks access | not a member of the org / not admin |
| 404 | Resource id does not exist | unknown board_id |
| 409 | Conflict / duplicate | email already registered, member already added, label already attached |
| 422 | Body validation failed | FastAPI automatic |

Error body shape is always FastAPI's default: `{"detail": "human readable message"}`.

## Role rules

- Creating an org makes the creator an `admin` (via an auto-created membership row).
- `admin` only: add members, delete boards.
- `member` (and admin): everything else — view org, CRUD boards/sections/issues/labels, comment.

## Build order

1. Backend: skeleton + `models.py` (all 9 tables) + `database.py` + `config.py`
2. Backend: auth (signup/login, `get_current_user`)
3. Backend: orgs + memberships (incl. add-member-by-email)
4. Backend: boards → sections → issues CRUD
5. Backend: issue move endpoint (position logic)
6. Backend: labels + comments GET
7. Backend: WebSocket layer (presence + comment_create handling)
8. Frontend: scaffold, auth pages, API client
9. Frontend: dashboard + org settings
10. Frontend: board page (sections/issues rendering, then drag & drop)
11. Frontend: issue modal (details, labels, due date, comments history)
12. Frontend: WS client (presence dots + live comments)

## Run commands (user runs these themselves)

- Backend: `cd backend && uvicorn app.main:app --reload --port 8000`
- Frontend: `cd frontend && bun dev` (frontend origin assumed `http://localhost:5173`)

## Deliberately out of scope for v1

Alembic migrations, Docker, automated tests, rate limiting, board-change broadcasts over WS, assignees, board archiving, email invitations, password reset.
