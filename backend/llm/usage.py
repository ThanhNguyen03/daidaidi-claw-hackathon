"""
Per-model call accounting
=========================
What model served a call, how many calls each model has taken, and which models
have said they are out of quota.

Why count locally at all: Google publishes no API that reports the remaining quota
for a key. The AI Studio Rate Limit page has it; nothing reachable from here does.
So this module counts what this process sent and compares it against the ceilings
declared in `config/model_limits.yaml`. That makes every number here a lower bound
— the same key used from a browser or a second deployment is invisible to it — and
callers are expected to label it as such rather than present it as authoritative.

The one thing here that is authoritative is `state`: when Gemini answers 429 and
names a per-day limit, that model is genuinely spent until the window rolls over,
and we heard it from the provider rather than inferred it.

Thread-safe because every LLM call funnels through a thread-pool executor.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIMITS_PATH = os.path.normpath(
    os.path.join(_HERE, "..", "config", "model_limits.yaml")
)

# A minute window for RPM, and a rolling 24h window for RPD.
#
# A rolling window rather than a calendar day because the provider's reset boundary
# is in a timezone we would have to guess at, and guessing wrong would show a full
# allowance to someone who has none left. Rolling is never optimistic by more than
# the real window.
_RPM_WINDOW_S = 60
_RPD_WINDOW_S = 24 * 60 * 60


def _load_limits() -> dict[str, dict]:
    """Read the declared ceilings. Missing or broken file is not fatal — usage
    counting still works, it just has nothing to compare against."""
    try:
        import yaml  # a hard dependency of this project; see CLAUDE.md
    except ImportError:
        print("[usage] pyyaml missing — model limits unavailable, counts only")
        return {}
    try:
        with open(_LIMITS_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data.get("models") or {}
    except FileNotFoundError:
        print(f"[usage] no model limits file at {_LIMITS_PATH} — counts only")
        return {}
    except Exception as e:
        print(f"[usage] could not read model limits ({e}) — counts only")
        return {}


@dataclass
class _ModelRecord:
    calls: list[float] = field(default_factory=list)  # timestamps of attempts
    ok: int = 0
    rate_limited: int = 0
    other_errors: int = 0
    # Set when the provider itself said the daily allowance is gone. Cleared by the
    # rolling window, not by us guessing when midnight is somewhere.
    day_exhausted_at: float | None = None
    minute_limited_at: float | None = None
    last_error: str = ""


class ModelUsageTracker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._models: dict[str, _ModelRecord] = {}
        self._limits = _load_limits()
        # Which model most recently served each caller, so the UI can say what is
        # running rather than what is configured — they differ the moment a
        # fallback fires, and that difference is the whole point of showing it.
        self._last_model_by_agent: dict[str, str] = {}

    # -- recording ---------------------------------------------------------
    def _rec(self, model: str) -> _ModelRecord:
        r = self._models.get(model)
        if r is None:
            r = _ModelRecord()
            self._models[model] = r
        return r

    def record_attempt(self, model: str, agent: str) -> None:
        now = time.time()
        with self._lock:
            r = self._rec(model)
            r.calls.append(now)
            # Keep the list bounded; anything older than the day window is dead data.
            cutoff = now - _RPD_WINDOW_S
            if len(r.calls) > 4096:
                r.calls = [t for t in r.calls if t >= cutoff]
            self._last_model_by_agent[agent] = model

    def record_success(self, model: str) -> None:
        with self._lock:
            self._rec(model).ok += 1

    def record_rate_limit(self, model: str, daily: bool, detail: str = "") -> None:
        now = time.time()
        with self._lock:
            r = self._rec(model)
            r.rate_limited += 1
            r.last_error = detail[:200]
            if daily:
                r.day_exhausted_at = now
            else:
                r.minute_limited_at = now

    def record_error(self, model: str, detail: str = "") -> None:
        with self._lock:
            r = self._rec(model)
            r.other_errors += 1
            r.last_error = detail[:200]

    def last_model_for(self, agent: str) -> str | None:
        with self._lock:
            return self._last_model_by_agent.get(agent)

    # -- reporting ---------------------------------------------------------
    def _state(self, r: _ModelRecord, now: float) -> str:
        if r.day_exhausted_at and now - r.day_exhausted_at < _RPD_WINDOW_S:
            return "out_of_quota_today"
        if r.minute_limited_at and now - r.minute_limited_at < _RPM_WINDOW_S:
            return "rate_limited"
        return "ok"

    def snapshot(self) -> dict:
        """Everything the UI needs, with the counting caveat attached."""
        now = time.time()
        with self._lock:
            models = []
            for name, r in sorted(self._models.items()):
                limits = self._limits.get(name) or {}
                per_min = sum(1 for t in r.calls if t >= now - _RPM_WINDOW_S)
                per_day = sum(1 for t in r.calls if t >= now - _RPD_WINDOW_S)
                models.append({
                    "model": name,
                    "state": self._state(r, now),
                    "used_rpm": per_min,
                    "used_rpd": per_day,
                    "limit_rpm": limits.get("rpm"),
                    "limit_rpd": limits.get("rpd"),
                    "note": limits.get("note", ""),
                    "successes": r.ok,
                    "rate_limits": r.rate_limited,
                    "other_errors": r.other_errors,
                    "last_error": r.last_error,
                })
            # Models we know about but have not called yet still belong in the list:
            # the point of the panel is to pick one, and one you have not used is
            # exactly the one with quota left.
            seen = {m["model"] for m in models}
            for name, limits in sorted(self._limits.items()):
                if name in seen:
                    continue
                models.append({
                    "model": name,
                    "state": "unused",
                    "used_rpm": 0,
                    "used_rpd": 0,
                    "limit_rpm": limits.get("rpm"),
                    "limit_rpd": limits.get("rpd"),
                    "note": limits.get("note", ""),
                    "successes": 0,
                    "rate_limits": 0,
                    "other_errors": 0,
                    "last_error": "",
                })
            return {
                "models": models,
                "counted_since_restart": True,
                "caveat": (
                    "Số lượt gọi do chính app này đếm từ lần khởi động gần nhất. "
                    "Google không cung cấp API báo quota còn lại, nên nếu key được "
                    "dùng ở nơi khác thì con số thực tế sẽ cao hơn. Trạng thái "
                    "'hết quota hôm nay' thì lấy trực tiếp từ lỗi 429 của Google."
                ),
            }


_tracker: ModelUsageTracker | None = None
_tracker_lock = threading.Lock()


def get_tracker() -> ModelUsageTracker:
    global _tracker
    if _tracker is None:
        with _tracker_lock:
            if _tracker is None:
                _tracker = ModelUsageTracker()
    return _tracker
