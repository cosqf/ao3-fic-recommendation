import requests
import json
from config import API_PORT
import pandas as pd 
import datetime
import math
import streamlit as st 

BACKEND_URL = st.secrets.get("BACKEND_URL", f"http://localhost:{API_PORT}")

@st.cache_data(ttl=300)
def wakeup_backend():
    try:
        print ("HEALTH")
        response = requests.get(f"{BACKEND_URL}/health", timeout=3)
        print (response)
    except Exception as e:
        print ("health failed")
        pass


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
        if response.status_code >= 400:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text
            yield "ERROR", f"Backend returned {response.status_code}: {detail}", None
            return

        for line in response.iter_lines():
            if not line:
                continue
            try:
                event = json.loads(line.decode("utf-8"))
                print ("received message of type " + event["type"] + " saying " + event["message"])
            except json.JSONDecodeError:
                yield "ERROR", f"Received a non-JSON line from backend: {line[:200]!r}", None
                continue
            yield event.get("type", "ERROR"), event.get("message", ""), event.get("data", None)
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
 