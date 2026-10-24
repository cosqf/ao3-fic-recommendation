import requests
import json
import threading
import uuid
from config import API_PORT
import pandas as pd 
import datetime
import math
import streamlit as st 
from google.oauth2 import service_account
from google.auth.transport.requests import Request as GoogleAuthRequest


def _secret(name, default=None):
    try:
        return st.secrets[name] if name in st.secrets else default
    except Exception:
        return default

BACKEND_URL = _secret("BACKEND_URL", f"http://localhost:{API_PORT}")

_token_lock = threading.Lock()


@st.cache_resource
def _id_token_credentials():
    info = dict(_secret("gcp_service_account"))
    return service_account.IDTokenCredentials.from_service_account_info(info, target_audience=BACKEND_URL)
 
 
def _auth_headers():
    if _secret("gcp_service_account") is None:
        return {}
    credentials = _id_token_credentials()
    with _token_lock:
        if not credentials.valid:  # first call, or the ~1 hour token expired
            credentials.refresh(GoogleAuthRequest())
        token = credentials.token
    return {"Authorization": f"Bearer {token}"}
 
 
def _session_id():
    if "backend_session_id" not in st.session_state:
        st.session_state.backend_session_id = uuid.uuid4().hex
    return st.session_state.backend_session_id

@st.cache_data(ttl=300)
def wakeup_backend():
    try:
        response = requests.get(f"{BACKEND_URL}/health", headers=_auth_headers(), timeout=3)
        print(f"health: {response.status_code}")
    except Exception as e:
        print(f"health failed: {e}")


def stream_backend(endpoint: str, payload: dict):
    body = json.dumps(payload, default=_json_default)
 
    try:
        headers = {"Content-Type": "application/json", "X-Session-Id": _session_id(), **_auth_headers()}
    except Exception as e:
        yield "ERROR", f"Could not authenticate with the backend: {e}", None
        return
 
    try:
        with requests.post(
            f"{BACKEND_URL}/{endpoint}",
            data=body,
            headers=headers,
            stream=True,
            timeout=(10, 300),
        ) as response:
            if response.status_code in (401, 403):
                yield "ERROR", f"The backend refused the request (HTTP {response.status_code}). Check the service account and its Invoker role.", None
                return
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
                except json.JSONDecodeError:
                    yield "ERROR", f"Received a non-JSON line from backend: {line[:200]!r}", None
                    continue

                if event.get("type") == "HEARTBEAT":  # keep-alive from the backend, nothing to show
                    continue

                print (f"received message of type {event.get('type')} saying {event.get('message', '')}")
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
 