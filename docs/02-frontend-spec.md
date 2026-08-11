# Frontend Specification

React app run with Bun, talking to the FastAPI backend at `http://localhost:8000`. Wireframes: six views — Signup/Signin, Create organization, Dashboard, Settings, Board, Issue (modal).

## Tooling defaults

These are sensible defaults, replaceable if the user supplies references later — everything else in this spec is behavior and does not change with tooling:

- Scaffold: `bun create vite frontend --template react` (or react-ts)
- Routing: `react-router-dom`
- Drag & drop: `@dnd-kit/core` + `@dnd-kit/sortable`
- State: React context + hooks only — no Redux/Zustand in v1
- Styling: plain CSS or CSS modules — dark theme like the wireframes

## Routes

| Route | View | Auth |
|---|---|---|
| `/signup`, `/login` | Signup / Signin form | public |
| `/orgs/new` | Create organization | required |
| `/` | Dashboard | required |
| `/orgs/:orgId/settings` | Org settings (members) | required |
| `/boards/:boardId` | Board | required |
| `/boards/:boardId/issues/:issueId` | Issue modal **over** the board (board stays mounted, WS stays open) | required |

Auth guard: routes marked required redirect to `/login` when no token. After login: go to `/` if the user has ≥1 org, else `/orgs/new`.

## Auth handling

- JWT stored in `localStorage` under `token`; an `AuthContext` exposes `{token, user, login(), logout()}`.
- Single API helper (`src/api.js`): wraps `fetch`, prefixes `http://localhost:8000`, sets `Authorization: Bearer <token>` and `Content-Type: application/json`, parses JSON, and on any 401 response clears the token and redirects to `/login`.

## Views

### Signup / Signin
Email + password + submit, link to switch between the two. Signup calls `POST /auth/signup` then `POST /auth/login` automatically. Show `detail` from error responses (e.g. 409 email taken, 401 invalid credentials) inline.

### Create organization (`/orgs/new`)
Name (+ optional description) → `POST /orgs` → navigate to `/`.

### Dashboard (`/`)
- On load: `GET /orgs`. Org dropdown top-left (selected org persisted in `localStorage`); if the saved org is gone, fall back to the first.
- Board grid: `GET /orgs/{orgId}/boards` for the selected org; each card navigates to `/boards/:id`.
- "Create" button → prompt/inline form for title → `POST /orgs/{orgId}/boards` → append to grid.
- Link to `/orgs/:orgId/settings`; header shows user email + logout.

### Settings (`/orgs/:orgId/settings`)
- `GET /orgs/{orgId}/members` → list of email + role.
- Add-member form (email + role select) → `POST /orgs/{orgId}/members`. Surface 404 ("No user with that email"), 409 (already a member), and 403 (not admin) messages inline. Hide the form entirely if current user's role (from `GET /orgs`) isn't admin.

### Board (`/boards/:boardId`)
- On load: `GET /boards/{boardId}` → render sections as columns (sorted by `position`), issues as cards within (sorted by `position`). Card shows title, its labels as small color chips, and due date if set.
- "Add section" at row end → `POST /boards/{boardId}/sections`. Section header: rename (PATCH) and delete (DELETE, with confirm).
- "+ Add issue" at each column bottom → `POST /sections/{sectionId}/issues` with title.
- **Presence dots** top-right: one avatar circle per user from the latest `presence_changed` (render first letter of email; tooltip shows full email).
- Clicking a card navigates to `/boards/:boardId/issues/:issueId` (modal opens, board stays mounted).

### Drag & drop (dnd-kit)
- Cards draggable within and across columns; columns are drop containers; each card slot is sortable.
- On drop: compute new position by **midpoint rule** (must match backend spec §5): between neighbors `(prev + next) / 2`; top of column `first / 2`; bottom `last + 1`; empty column `1.0`.
- **Optimistic update:** move the card in local state immediately, then `PATCH /issues/{id}/move` with `{section_id, position}`. On failure: revert by refetching `GET /boards/{boardId}`.
- v1 skips section drag-reordering (position field exists; can be added later).

### Issue modal (`/boards/:boardId/issues/:issueId`)
Overlay on the board. On open: `GET /issues/{issueId}` and `GET /issues/{issueId}/comments`.
- Title (click to edit → PATCH), description textarea (save on blur → PATCH), due date input (PATCH).
- Labels: chips of attached labels with remove (×); "add label" shows the board's labels to attach (`POST /issues/{id}/labels`), plus a small create-label form (name + color → `POST /boards/{id}/labels`).
- Comments: list (oldest first) as `email: body` + timestamp; input at bottom sends over **WebSocket** (below), NOT HTTP. The list updates only when `comment_created` arrives — no local echo, the broadcast includes the sender.
- Delete issue button (confirm → `DELETE /issues/{id}` → close modal, remove card).
- Close (× / backdrop / Esc) → navigate back to `/boards/:boardId`.

## WebSocket client (board page only)

A `useBoardSocket(boardId)` hook, mounted for the whole board route (modal included):

- Connect on mount to `ws://localhost:8000/ws/boards/{boardId}?token=<jwt>`; close on unmount.
- On message, switch on `type`:
  - `presence_changed` → update presence dots state.
  - `comment_created` → if the issue modal is open for that `comment.issue_id`, append to its comment list. Otherwise ignore.
  - `error` → show a toast/inline message.
- Sending: `send({type: "comment_create", issue_id, body})` — used by the modal's comment input.
- Reconnect: on unexpected close, retry with a simple delay (e.g. 2s, max 5 tries). Keep it simple.

## Build order (frontend)

1. Scaffold + router + AuthContext + api helper + login/signup pages
2. Create-org page + dashboard (org dropdown, board grid, create board)
3. Settings page (members list, add member)
4. Board page: static rendering of sections/issues from `GET /boards/{id}`
5. Add-section / add-issue / rename / delete flows
6. Drag & drop with optimistic move
7. Issue modal: details, labels, due date, comments history (HTTP parts)
8. WS hook: presence dots + realtime comments
