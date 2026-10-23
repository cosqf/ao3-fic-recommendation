import asyncio
import datetime
import json
import math
import os
import re
import threading
import time

import pandas as pd

from fastapi import FastAPI, Header, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from starlette.concurrency import iterate_in_threadpool, run_in_threadpool

from backend.browser_worker import PlaywrightWorker
from backend.jobs import JobRegistry, Busy
from config import API_PORT
from backend.web import run_scrape_pipeline, make_event, fetchingUnreadWorks

app = FastAPI()

NDJSON = "application/x-ndjson"

# one registry per process
registry = JobRegistry(max_jobs=int(os.environ.get("MAX_ACTIVE_JOBS", "2")))
RELEASE_TIMEOUT = 120      # seconds to wait for a cancelled worker to close its browser before freeing the slot
DISCONNECT_POLL = 1.0      # seconds between "is the client still there?" checks
_SESSION_ID_RE = re.compile(r"[0-9a-f]{32}")


def _clean_session_id(value):
    return value if value and _SESSION_ID_RE.fullmatch(value) else None

def get_worker(cancel_event=None):
    return PlaywrightWorker(headless=True, cancel_event=cancel_event)

@app.get("/health")
def health_endpoint():
    print ("HEALTH")
    return {"status": "ok", "message": "UP!"}

class ScrapeRequest(BaseModel):
    username: str
    password: str
    df: list[dict] | None = None

def _json_default(value):
    if value is pd.NaT or (isinstance(value, float) and math.isnan(value)):
        return None
    if isinstance(value, (pd.Timestamp, datetime.date, datetime.datetime)):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return str(value)


def _encode(events):
    for event in events:
        yield json.dumps(event, default=_json_default) + "\n"


def _describe(job):
    session = job.session_id[:8] if job.session_id else "none"
    return f"user={job.key!r} session={session} running_for={time.monotonic() - job.started:.0f}s"


def _release_when_stopped(worker, job, reason):
    def _wait():
        try:
            join = getattr(worker, "join", None)
            if join is not None:
                join(timeout=RELEASE_TIMEOUT)
            print(f"browser closed ({reason}): {_describe(job)}")
        finally:
            registry.release(job)
    threading.Thread(target=_wait, daemon=True).start()


async def _watch_disconnect(request, job, state):
    while not await request.is_disconnected():
        await asyncio.sleep(DISCONNECT_POLL)
    state["logged"] = True
    print(f"client left, cancelling: {_describe(job)} last_event={state['last']}")
    job.cancel()


async def stream(request, events, worker, job):
    state = {"last": "none"}   # last event sent to the client, for the log line when they leave
    watcher = asyncio.create_task(_watch_disconnect(request, job, state))
    finished = False
    try:
        async for chunk in iterate_in_threadpool(_encode(events)):
            state["last"] = json.loads(chunk)["type"]
            yield chunk
        finished = True
    finally:
        watcher.cancel()
        if not finished and not state.get("logged"):
            print(f"run ended early, client left or connection closed: {_describe(job)} last_event={state['last']}")
        job.cancel()          # no-op when the run already finished
        worker.stop()
        _release_when_stopped(worker, job, "finished" if finished else "cancelled")


def _error_response(message):
    return StreamingResponse(_encode([make_event("ERROR", message=message)]), media_type=NDJSON)


def _start(username, session_id):
    try:
        job = registry.acquire(username, _clean_session_id(session_id))
    except Busy as e:
        return None, None, str(e)
    try:
        worker = get_worker(cancel_event=job.cancel_event)
    except Exception as e:
        registry.release(job)
        return None, None, f"could not start the browser: {e}"
    print ("worker ready")
    return job, worker, None


@app.post("/scrape")
async def scrape_endpoint(payload: ScrapeRequest, request: Request, x_session_id: str | None = Header(default=None)):
    print ("scrape!")

    existing_df = pd.DataFrame(payload.df) if payload.df else None
    if not payload.username.strip() or not payload.password.strip():
        return _error_response("username and password are required")

    job, worker, error = await run_in_threadpool(_start, payload.username, x_session_id)
    if error:
        return _error_response(error)

    return StreamingResponse(
        stream(request, run_scrape_pipeline(worker, payload.username, payload.password, existing_df), worker, job),
        media_type=NDJSON,
    )


class FetchWorksRequest(BaseModel):
    ship: str
    username: str | None = None
    password: str | None = None
    df: list[dict] | None = None
    inc_tags : list[str] | None = None
    exc_tags : list[str] | None = None


@app.post("/fetch_works")
async def fetch_works_endpoint(payload: FetchWorksRequest, request: Request, x_session_id: str | None = Header(default=None)):
    print ("fetch!")
    if not payload.ship.strip():
        return _error_response("a ship/relationship tag is required")

    job, worker, error = await run_in_threadpool(_start, payload.username, x_session_id)
    if error:
        return _error_response(error)
    username = payload.username or None
    password = payload.password or None

    inc_tag = payload.inc_tags or [] 
    exc_tag = payload.exc_tags or [] 

    return StreamingResponse(
        stream(request, fetchingUnreadWorks(worker, username, password, payload.ship, payload.df, inc_tag, exc_tag), worker, job),
        media_type=NDJSON,
    )

def main():
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=API_PORT)

if __name__ == "__main__":
    main()