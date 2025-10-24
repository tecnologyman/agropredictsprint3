# predicciones/services/fastapi_client.py
import httpx
from django.conf import settings

BASE = getattr(settings, "FASTAPI_BASE_URL", "http://localhost:8001")
TIMEOUT = 5.0

def ping():
    url = f"{BASE}/health"
    with httpx.Client(timeout=TIMEOUT) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.json()

def echo(msg: str):
    url = f"{BASE}/echo"
    with httpx.Client(timeout=TIMEOUT) as client:
        r = client.post(url, json={"msg": msg})
        r.raise_for_status()
        return r.json()