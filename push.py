"""
cyberPOS Web Push.
Sends notifications to the phone(s) that enabled them in the console (installed PWA).
VAPID keys are generated on first use and kept in vapid_private.pem (gitignored).
"""

import base64
import json
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid
from pywebpush import webpush, WebPushException

import store

KEY_PATH = Path(__file__).resolve().parent / "vapid_private.pem"
CLAIMS = {"sub": "mailto:hello@fastaf.ca"}


def _vapid():
    if not KEY_PATH.exists():
        v = Vapid()
        v.generate_keys()
        v.save_key(str(KEY_PATH))
        KEY_PATH.chmod(0o600)
    return Vapid.from_file(str(KEY_PATH))


def public_key():
    """The applicationServerKey the browser needs (base64url, uncompressed EC point)"""
    raw = _vapid().public_key.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def send(title, body, url="/", tag=None, actions=None, data=None):
    """
    Push to every subscribed device. Returns the number delivered.
    actions: [{"action": "done", "title": "Done"}, ...] handled by the service worker
    """
    store.init()
    _vapid()
    payload = json.dumps({
        "title": title, "body": body, "url": url, "tag": tag,
        "actions": actions or [], "data": data or {},
    })
    sent = 0
    for sub in store.push_subs():
        try:
            webpush(sub, payload, vapid_private_key=str(KEY_PATH), vapid_claims=dict(CLAIMS), ttl=3600)
            sent += 1
        except WebPushException as e:
            status = getattr(e.response, "status_code", None)
            if status in (404, 410):
                store.remove_push_sub(sub["endpoint"])  # phone unsubscribed or app removed
            else:
                print(f"Push failed ({status}): {e}")
    return sent
