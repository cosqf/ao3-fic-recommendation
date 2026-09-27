import requests
import json
from config import API_PORT, API_URL
import pandas as pd 
import datetime
import math

BACKEND_URL = f"http://{API_URL}:{API_PORT}" 

def stream_backend(endpoint: str, payload: dict):
    body = json.dumps(payload, default=_json_default)
 
    try:
        response = requests.post(
            f"{BACKEND_URL}/{endpoint}",
            data=body,
            headers={"Content-Type": "application/json"},
            stream=True,
            timeout=300,
        )

        for line in response.iter_lines():
            if line:
                event = json.loads(line.decode("utf-8"))
                print ("received message of type " + event["type"] + " saying " + event["message"])
                yield event["type"], event.get("message", ""), event.get("data", None)

    except requests.exceptions.RequestException as e:
        yield "ERROR", f"Connection error: {str(e)}", None


def _json_default(value):
    if isinstance(value, (pd.Timestamp, datetime.date, datetime.datetime)):
        return value.isoformat()
    if value is pd.NaT or (isinstance(value, float) and math.isnan(value)):
        return None
    if hasattr(value, "item"):
        return value.item()
    return str(value)
 