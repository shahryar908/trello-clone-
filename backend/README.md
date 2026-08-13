# Backend — FastAPI + SQLModel

## Run it

```bash
uv sync
uv run uvicorn app.main:app --reload
```

Docs at http://localhost:8000/docs.

## Tests

```bash
uv run pytest          # the suite
uv run pytest -q       # what CI runs
uv run ruff check .    # lint, also a CI gate
uv run ruff check --fix .
```

Every test runs against a fresh **in-memory** SQLite database, built and thrown
away per test. `trello.db` is never touched, and no test can see another test's
data. Two details in `tests/conftest.py` make that work:

- `StaticPool` forces every connection to reuse the same in-memory database.
  Without it, each connection opens its own empty one and nothing persists
  between requests.
- `app.database.engine` and `app.ws.engine` are both patched. `get_session()`
  reads the module attribute when it runs, but `ws.py` did
  `from .database import engine`, which copied the reference at import time — so
  it needs its own patch or the WebSocket handler writes to the real file.

`bcrypt` is dropped to 4 rounds in tests. It is deliberately slow in production
and would otherwise dominate the runtime.

### What is covered

| File | What it protects |
|---|---|
| `test_auth.py` | signup/login, duplicate emails, forged and missing tokens, identical wording for "wrong password" and "no such user" |
| `test_authorization.py` | org isolation — an outsider cannot read, write, or delete another org's data; members cannot do admin actions |
| `test_boards.py` | positions, the nested board payload, cross-board moves, cascade deletes |
| `test_ws.py` | room auth, presence, comment broadcast, and the multi-device regression below |

### The regression test worth knowing about

`ConnectionManager` used to store **one socket per user**. Opening a board on a
second device evicted the first, so comments only showed up after a refresh —
which is exactly what happened in production. It now stores a set of sockets per
user, and `test_both_devices_of_one_user_receive_a_broadcast` fails if anyone
ever changes it back.

## Metrics

Prometheus metrics are served on **port 9100**, not on the API port. The
Ingress only routes to 8000, so `/metrics` is reachable inside the cluster and
nowhere else — on the app port it would publish every route name, traffic
volume and latency figure to the internet.

```bash
uv run uvicorn app.main:app          # API on 8000
curl localhost:9100/metrics          # metrics on 9100
METRICS_PORT=0 uv run uvicorn ...    # or turn it off
```

Definitions live in `app/metrics.py`. The one rule worth internalising: the
request counter is labelled with the route **template** (`/boards/{board_id}`),
never the actual URL. Labelling with `/boards/417` mints a new time series per
board id and eventually takes Prometheus down. Unmatched paths collapse to
`__unmatched__` so a vulnerability scanner cannot do the same thing on purpose.
`test_metrics.py` enforces both.

## Health endpoints

Two probes, two questions:

| | checks | on failure |
|---|---|---|
| `GET /health` | nothing but the event loop | k8s **restarts** the pod |
| `GET /health/ready` | runs `SELECT 1` | k8s removes the pod from the Service |

Liveness deliberately does not touch the database. If it did, a brief database
hiccup would restart the pod — which does not fix a database, and turns a blip
into a crash loop. Readiness is the one allowed to care about dependencies,
because failing it is reversible.

## In CI

`.github/workflows/beci.yml` runs `ruff check` then `pytest`. Only if both pass
does it build the image, push it, and bump the tag in `infraops/k8s/`, which is
what ArgoCD watches. A failing test stops the deploy at the first step.

The image itself is built with `uv sync --no-dev`, so pytest and ruff decide
whether to ship it but never ship inside it.
