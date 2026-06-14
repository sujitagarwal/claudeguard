import json
import os
import stat
from datetime import datetime, timezone
from lib.paths import STATE_FILE

DEFAULT_STATE = {
    "locked": True,
    "awaitingPasscode": False,
    "unlockedAt": None,
    "lastActivityAt": None,
    "failedAttempts": 0,
    "lockoutUntil": None,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(s) -> datetime | None:
    if not s:
        return None
    return datetime.fromisoformat(s)


def read_state() -> dict:
    if not os.path.exists(STATE_FILE):
        return dict(DEFAULT_STATE)
    try:
        with open(STATE_FILE) as f:
            return {**DEFAULT_STATE, **json.load(f)}
    except Exception:
        return dict(DEFAULT_STATE)


def write_state(patch: dict) -> dict:
    s = read_state()
    s.update(patch)
    with open(STATE_FILE, "w") as f:
        json.dump(s, f, indent=2)
    os.chmod(STATE_FILE, stat.S_IRUSR | stat.S_IWUSR)
    return s


def is_locked(config: dict) -> bool:
    s = read_state()
    if s["locked"]:
        return True
    timeout_min = config.get("autoLockMinutes", 60)
    if timeout_min == 0:
        return False
    last = _parse_iso(s.get("lastActivityAt"))
    if last is None:
        return True
    elapsed_min = (datetime.now(timezone.utc) - last).total_seconds() / 60
    if elapsed_min > timeout_min:
        write_state({"locked": True, "unlockedAt": None})
        return True
    return False


def lock() -> dict:
    return write_state({"locked": True, "awaitingPasscode": False, "unlockedAt": None})


def set_awaiting_passcode(waiting: bool) -> dict:
    return write_state({"awaitingPasscode": waiting})


def is_awaiting_passcode() -> bool:
    return read_state().get("awaitingPasscode", False)


def unlock() -> dict:
    return write_state({
        "locked": False,
        "awaitingPasscode": False,
        "unlockedAt": _now_iso(),
        "lastActivityAt": _now_iso(),
        "failedAttempts": 0,
        "lockoutUntil": None,
    })


def record_activity() -> dict:
    return write_state({"lastActivityAt": _now_iso()})


def record_failed_attempt(config: dict) -> dict:
    s = read_state()
    attempts = s.get("failedAttempts", 0) + 1
    patch = {"failedAttempts": attempts}
    max_attempts = config.get("maxFailedAttempts", 5)
    if attempts >= max_attempts:
        from datetime import timedelta
        lockout_min = config.get("lockoutDurationMinutes", 15)
        until = datetime.now(timezone.utc) + timedelta(minutes=lockout_min)
        patch["lockoutUntil"] = until.isoformat()
    return write_state(patch)


def is_locked_out() -> bool:
    s = read_state()
    until = _parse_iso(s.get("lockoutUntil"))
    if until is None:
        return False
    if datetime.now(timezone.utc) < until:
        return True
    write_state({"lockoutUntil": None, "failedAttempts": 0})
    return False
