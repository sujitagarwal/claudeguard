import json
import os
import stat
from lib.paths import CONFIG_FILE

DEFAULTS = {
    "enabled": True,
    "autoLockMinutes": 60,
    "maxFailedAttempts": 5,
    "lockoutDurationMinutes": 15,
}


def read_config() -> dict:
    if not os.path.exists(CONFIG_FILE):
        return dict(DEFAULTS)
    try:
        with open(CONFIG_FILE) as f:
            return {**DEFAULTS, **json.load(f)}
    except Exception:
        return dict(DEFAULTS)


def write_config(patch: dict) -> dict:
    cfg = read_config()
    cfg.update(patch)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)
    os.chmod(CONFIG_FILE, stat.S_IRUSR | stat.S_IWUSR)
    return cfg
