#!/usr/bin/env python3
"""
SessionStart hook — fires async, cannot block session.
- If auto-lock threshold exceeded → set state locked.
- Update lastActivityAt on active sessions.
- Inject systemMessage when locked so Claude knows not to surface history.
"""
import json
import sys
import os

# Allow imports from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from lib.crypto import has_passcode
from lib.config import read_config
from lib.state import is_locked, record_activity


def main():
    if not has_passcode():
        print(json.dumps({"continue": True}))
        return

    config = read_config()
    if not config.get("enabled", True):
        print(json.dumps({"continue": True}))
        return

    locked = is_locked(config)

    if not locked:
        record_activity()
        print(json.dumps({"continue": True}))
        return

    output = {
        "systemMessage": (
            "ClaudeGuard is ACTIVE and LOCKED. "
            "Do not summarize, reference, or reveal past conversation history until the user unlocks. "
            "If the user asks about history, instruct them to run: claudeguard unlock"
        )
    }
    print(json.dumps(output))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"claudeguard session_start error: {e}", file=sys.stderr)
        sys.exit(2)
