"""
Figma wireframe job store
=========================
A wireframe spec cannot be pushed into a rep's Figma file from here. Figma exposes no REST
API for creating nodes, and OAuth grants no Plugin-API access — drawing is only possible from
inside a running Figma session. So the flow is inverted: the backend parks a finished spec
under a short code, and the AdtimaBox Figma plugin (see figma-plugin/) pulls it when the rep
opens it in their own file. This module is that parking space.

The code is the only credential the plugin presents, so it is generated with `secrets` from an
unambiguous alphabet (no O/0/I/1 — a rep reads this off a screen and types it into Figma) and
expires. It is not a session id and cannot be turned into one: nothing here exposes the
session it came from.

Specs go to disk under ARTIFACTS_DIR/figma/ for the same reason deck HTML does — an in-memory
store dies with the container, and a rep who pressed the button before a redeploy would open
the plugin to a dead code with no way to tell why.
"""

from __future__ import annotations

import json
import os
import secrets
import time
from typing import Any, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
JOBS_DIR = os.path.join(_HERE, "..", "data", "artifacts", "figma")

# Ambiguous glyphs removed: a rep reading a code off the chat and typing it into the Figma
# plugin cannot tell O from 0 or I from 1, and a mistyped code is indistinguishable from an
# expired one. 8 chars from 32 symbols is ~40 bits — far more than a guessing attack gets
# through against a 24-hour window, and still short enough to retype.
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_CODE_LEN = 8

# A spec is consumed within minutes of the button press in every real flow. A day is
# generous; anything longer is just a wireframe spec sitting on disk with a bearer code.
_TTL_SECONDS = 24 * 60 * 60


def _path(code: str) -> str:
    return os.path.join(JOBS_DIR, f"{code}.json")


def _new_code() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(_CODE_LEN))


def create_job(spec: dict[str, Any]) -> str:
    """Park a spec and return the code the rep types into the plugin."""
    os.makedirs(JOBS_DIR, exist_ok=True)
    code = _new_code()
    payload = {"code": code, "created_at": time.time(), **spec}
    with open(_path(code), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    screens = spec.get("screens") or []
    print(f"[figma] job {code} created — {len(screens)} screen(s)")
    return code


def load_job(code: str) -> Optional[dict[str, Any]]:
    """The spec for this code, or None if it never existed or has expired.

    Expiry is checked on read rather than swept on a timer: the plugin's fetch is the only
    thing that cares, and a background sweeper is one more moving part for a directory that
    holds a few KB per proposal.
    """
    # The code lands here straight from a URL path, so it decides a filename — anything
    # outside the generated alphabet is rejected before it can traverse out of JOBS_DIR.
    if not code or len(code) != _CODE_LEN or any(c not in _ALPHABET for c in code):
        return None

    path = _path(code)
    if not os.path.exists(path):
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            job = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[figma] job {code} unreadable: {e}")
        return None

    if time.time() - float(job.get("created_at") or 0) > _TTL_SECONDS:
        print(f"[figma] job {code} expired")
        try:
            os.remove(path)
        except OSError:
            pass
        return None

    return job


def purge_jobs(codes: list[str]) -> None:
    """Drop specs belonging to a deleted conversation.

    Called from main.py's _purge_session_everywhere: a wireframe spec carries the client's
    real brand, prices and journey, so deleting the conversation has to delete this too.
    """
    for code in codes:
        if not code:
            continue
        try:
            os.remove(_path(code))
        except OSError:
            pass
