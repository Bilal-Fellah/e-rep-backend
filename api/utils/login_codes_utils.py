import json
import os
import time
import threading

LOGIN_CODE_FILE = 'api/database/temp_login_codes.json'

_LOCK = threading.Lock()


def _load():
    if not os.path.exists(LOGIN_CODE_FILE):
        return {}
    with open(LOGIN_CODE_FILE, "r") as f:
        return json.load(f)


def _save(data):
    with open(LOGIN_CODE_FILE, "w") as f:
        json.dump(data, f)


def _cleanup(data):
    now = time.time()
    return {
        code: v
        for code, v in data.items()
        if v["exp"] > now
    }


def store_login_code(code, user_id, ttl=300):
    with _LOCK:
        data = _load()
        data = _cleanup(data)

        data[code] = {
            "user_id": user_id,
            "exp": time.time() + ttl
        }

        _save(data)


def consume_login_code(code):
    with _LOCK:
        data = _load()
        data = _cleanup(data)

        entry = data.pop(code, None)
        _save(data)

        return entry
