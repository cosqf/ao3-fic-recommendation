import json
import pandas as pd

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.browser_worker import PlaywrightWorker
from config import API_PORT, API_URL
from backend.web import run_scrape_pipeline, make_event, scrap_unread_fics, fetchingUnreadWorks

app = FastAPI()

def get_worker():
    return PlaywrightWorker(headless=True)

class ScrapeRequest(BaseModel):
    username: str
    password: str
    df: list[dict] | None = None

def _json_default(value):
    if isinstance(value, (pd.Timestamp, datetime.date, datetime.datetime)):
        return value.isoformat()
    if value is pd.NaT or (isinstance(value, float) and math.isnan(value)):
        return None
    if hasattr(value, "item"):
        return value.item()
    return str(value)
 

def stream(events):
    for event in events:
        yield json.dumps(event, default=_json_default) + "\n"


@app.post("/scrape")
def scrape_endpoint(payload: ScrapeRequest):
    print ("scrape!")

    existing_df = pd.DataFrame(payload.df) if payload.df else None
    if not payload.username.strip() or not payload.password.strip():
        return StreamingResponse(
            stream([make_event("ERROR", message="username and password are required")]),
            media_type="application/x-ndjson",
        )

    worker = get_worker()
    return StreamingResponse(
        stream(run_scrape_pipeline(worker, payload.username, payload.password, existing_df)),
        media_type="application/x-ndjson",
    )


class FetchWorksRequest(BaseModel):
    username: str
    password: str
    ship: str
    df: list[dict] | None = None
 

@app.post("/fetch_works")
def fetch_works_endpoint(payload: FetchWorksRequest):
    if not payload.username.strip() or not payload.password.strip():
        return StreamingResponse(
            stream([make_event("ERROR", message="username and password are required")]),
            media_type="application/x-ndjson",
        )
 
    if not payload.ship.strip():
        return StreamingResponse(
            stream([make_event("ERROR", message="a ship/relationship tag is required")]),
            media_type="application/x-ndjson",
        )
 
    worker = get_worker()
    return StreamingResponse(
        stream(fetchingUnreadWorks(worker, payload.username, payload.password, payload.ship, payload.df)),
        media_type="application/x-ndjson",
    )

def main():
    import uvicorn

    #uvicorn.run(app, host="0.0.0.0", port=8000)
    uvicorn.run(app, host=API_URL, port=API_PORT)

if __name__ == "__main__":
    main()
