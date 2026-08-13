from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlmodel import Session

# imported as a module, not `from .database import engine`, so that reading
# database.engine happens at call time — otherwise the tests' patched engine
# would never be seen here
from . import database, ws
from .config import METRICS_PORT
from .database import create_db_and_tables
from .metrics import start_metrics_server, track_requests
from .routers import auth, boards, issues, labels, orgs, sections


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    start_metrics_server(METRICS_PORT)
    yield


app = FastAPI(title="Trello Clone API", lifespan=lifespan)

# registered first so it wraps everything below it and sees the real status code
app.middleware("http")(track_requests)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    """Liveness: is the process alive?

    Deliberately checks nothing. A liveness probe that queried the database
    would restart the pod every time the database hiccuped — which does not fix
    a database, and turns a brief blip into a crash loop.
    """
    return {"status": "ok"}


@app.get("/health/ready")
def ready():
    """Readiness: can this pod serve a real request right now?

    This one DOES touch the database, because a pod that cannot read its own
    data has no business being in the Service's endpoint list. Failing here
    takes the pod out of rotation without killing it, so it can come back on
    its own the moment the dependency recovers.
    """
    try:
        with Session(database.engine) as session:
            session.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status_code=503, detail="database unavailable")
    return {"status": "ready"}


app.include_router(auth.router)
app.include_router(orgs.router)
app.include_router(boards.router)
app.include_router(sections.router)
app.include_router(issues.router)
app.include_router(labels.router)
app.include_router(ws.router)
