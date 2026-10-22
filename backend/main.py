import datetime
import json
import math

import pandas as pd

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.browser_worker import PlaywrightWorker
from config import API_PORT
from backend.web import run_scrape_pipeline, make_event, fetchingUnreadWorks

app = FastAPI()

NDJSON = "application/x-ndjson"


def get_worker():
    return PlaywrightWorker(headless=True)

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
 

def stream(events, worker=None):
    try:
        for event in events:
            yield json.dumps(event, default=_json_default) + "\n"
    finally:
        if worker is not None:
            worker.stop()


def _error_response(message):
    return StreamingResponse(stream([make_event("ERROR", message=message)]), media_type=NDJSON)

# returns (worker, None) or (None, error_msg)
def _start_worker():
    try:
        worker = get_worker()
    except Exception as e:
        return None, f"could not start the browser: {e}"
    print ("worker ready")
    return worker, None


@app.post("/scrape")
def scrape_endpoint(payload: ScrapeRequest):
    print ("scrape!")

    existing_df = pd.DataFrame(payload.df) if payload.df else None
    if not payload.username.strip() or not payload.password.strip():
        return _error_response("username and password are required")

    worker, error = _start_worker()
    if error:
        return _error_response(error)

    return StreamingResponse(
        stream(run_scrape_pipeline(worker, payload.username, payload.password, existing_df), worker),
        media_type=NDJSON,
    )


class FetchWorksRequest(BaseModel):
    username: str
    password: str
    ship: str
    df: list[dict] | None = None


@app.post("/fetch_works")
def fetch_works_endpoint(payload: FetchWorksRequest):
    print ("fetch!")
    if not payload.username.strip() or not payload.password.strip():
        return _error_response("username and password are required")

    if not payload.ship.strip():
        return _error_response("a ship/relationship tag is required")

    worker, error = _start_worker()
    if error:
        return _error_response(error)

    return StreamingResponse(
        stream(fetchingUnreadWorks(worker, payload.username, payload.password, payload.ship, payload.df), worker),
        media_type=NDJSON,
    )

def main():
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=API_PORT)

if __name__ == "__main__":
    main()