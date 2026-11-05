"""Local web UI for the job agent.

    python -m job_agent.web            # http://127.0.0.1:8765

A thin FastAPI layer over the same functions the CLI uses. Local-first by design:
binds to 127.0.0.1 only, never writes secrets, and gates the irreversible submit
step behind an explicit confirmation. Start it from the same venv as the CLI.
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import api
from .config import PRIVATE, ROOT, load_config, load_env, load_profile
from .db import DB

log = logging.getLogger("job_agent.web")
WEBAPP = ROOT / "webapp"

app = FastAPI(title="Job Agent", docs_url="/api/docs", openapi_url="/api/openapi.json")


# ------------------------------------------------------------- dependencies
def get_db():
    db = DB(PRIVATE / "tracker.db")
    try:
        yield db
    finally:
        db.con.close()


def get_profile() -> dict:
    try:
        return load_profile()
    except SystemExit as e:
        raise HTTPException(400, str(e))


# ------------------------------------------------------------- read models
@app.get("/api/dashboard")
def dashboard(db: DB = Depends(get_db)):
    return api.dashboard(db)


@app.get("/api/jobs")
def jobs(status: str = "scored", limit: int = 50, db: DB = Depends(get_db)):
    return {"status": status, "counts": api.job_status_counts(db),
            "jobs": api.jobs(db, status, limit)}


@app.get("/api/applications")
def applications(status: str | None = None, db: DB = Depends(get_db)):
    return {"status": status, "applications": api.applications(db, status)}


@app.get("/api/applications/{app_id}")
def application_detail(app_id: int, db: DB = Depends(get_db)):
    detail = api.application_detail(db, app_id)
    if detail is None:
        raise HTTPException(404, f"no application {app_id}")
    return detail


# ------------------------------------------------------------- actions
@app.post("/api/applications/{app_id}/approve")
def approve(app_id: int, db: DB = Depends(get_db)):
    api.approve(db, app_id)
    return {"ok": True, "app_id": app_id, "status": "approved"}


@app.post("/api/applications/{app_id}/reject")
def reject(app_id: int, db: DB = Depends(get_db)):
    api.reject(db, app_id)
    return {"ok": True, "app_id": app_id, "status": "withdrawn"}


class Outcome(BaseModel):
    outcome: str
    note: str = ""


@app.post("/api/applications/{app_id}/status")
def set_status(app_id: int, body: Outcome, db: DB = Depends(get_db)):
    try:
        api.set_outcome(db, app_id, body.outcome, body.note)
    except SystemExit as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "app_id": app_id, "status": body.outcome}


# ------------------------------------------------------------- pipeline
@app.post("/api/pipeline/discover")
def run_discover(db: DB = Depends(get_db)):
    from . import discover
    return discover.run(db, load_config())


@app.post("/api/pipeline/score")
def run_score(rescore: bool = False, db: DB = Depends(get_db),
              profile: dict = Depends(get_profile)):
    from . import matcher
    return matcher.run(db, profile, load_config(), rescore=rescore)


@app.post("/api/pipeline/prepare")
def run_prepare(limit: int | None = None, db: DB = Depends(get_db),
                profile: dict = Depends(get_profile)):
    from . import prepare
    return prepare.run(db, profile, load_config(), limit)


class ApplyRequest(BaseModel):
    confirm: bool = False
    ids: list[int] | None = None
    max: int | None = 5


@app.post("/api/pipeline/apply")
def run_apply(body: ApplyRequest, db: DB = Depends(get_db),
              profile: dict = Depends(get_profile)):
    """Fill + submit. Irreversible, so it requires {"confirm": true}. Runs
    non-interactive: the app's own approval gate still decides what may submit —
    during the approval phase nothing is auto-submitted."""
    if not body.confirm:
        raise HTTPException(400, "apply requires confirm=true (this can submit real applications)")
    from . import apply as apply_mod
    result = apply_mod.run(db, profile, load_config(), interactive=False,
                           headless=True, max_apps=body.max, only_ids=body.ids)
    return result


@app.post("/api/ask")
def ask(body: dict, profile: dict = Depends(get_profile)):
    from .answers import Answerer
    question = (body or {}).get("question", "").strip()
    if not question:
        raise HTTPException(400, "question required")
    a = Answerer(profile).answer(question)
    return {"question": question, "value": a.value,
            "confidence": a.confidence, "note": a.note}


# ------------------------------------------------------------- documents
@app.get("/api/files/{app_id}/{which}")
def document(app_id: int, which: str, db: DB = Depends(get_db)):
    """Serve a prepared resume/cover file, but only via its recorded path for
    that application — no arbitrary filesystem access."""
    if which not in ("resume", "cover"):
        raise HTTPException(404, "unknown document")
    col = "resume_path" if which == "resume" else "cover_path"
    row = db.one(f"SELECT {col} p FROM applications WHERE id=?", (app_id,))
    if not row or not row["p"]:
        raise HTTPException(404, "no such document")
    path = Path(row["p"]).resolve()
    # Must stay inside the private directory the agent writes to.
    if not str(path).startswith(str(PRIVATE.resolve())) or not path.exists():
        raise HTTPException(404, "file not available")
    return FileResponse(path, filename=path.name)


# ------------------------------------------------------------- static UI
if WEBAPP.exists():
    app.mount("/", StaticFiles(directory=str(WEBAPP), html=True), name="ui")


def main():
    import uvicorn
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    load_env()
    host, port = "127.0.0.1", 8765
    print(f"Job Agent UI  ->  http://{host}:{port}   (API docs at /api/docs)")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
