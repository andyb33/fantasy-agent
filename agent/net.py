"""Tiny HTTP helpers (standard library only, so runs start fast)."""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "fantasy-agent/1.0 (personal use)"


def request(url, data=None, headers=None, method=None, timeout=30, retries=2):
    hdrs = {"User-Agent": UA}
    hdrs.update(headers or {})
    body = None
    if data is not None:
        if isinstance(data, dict):
            body = urllib.parse.urlencode(data).encode()
            hdrs.setdefault("Content-Type", "application/x-www-form-urlencoded")
        elif isinstance(data, (bytes, bytearray)):
            body = bytes(data)
        else:
            body = str(data).encode()
    last = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            # Client errors won't fix themselves; return them to the caller.
            if e.code < 500 and e.code != 429:
                return e.code, e.read()
            last = e
        except (urllib.error.URLError, TimeoutError) as e:
            last = e
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Request failed after retries: {url} ({last})")


def get_json(url, headers=None):
    status, body = request(url, headers=headers)
    if status != 200:
        raise RuntimeError(f"GET {url} -> HTTP {status}: {body[:200]!r}")
    return json.loads(body)


def post_json(url, payload, headers=None, timeout=120):
    hdrs = {"Content-Type": "application/json"}
    hdrs.update(headers or {})
    status, body = request(url, data=json.dumps(payload).encode(), headers=hdrs,
                           method="POST", timeout=timeout)
    return status, json.loads(body) if body else {}
