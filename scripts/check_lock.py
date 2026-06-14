#!/usr/bin/env python3
"""
UserPromptSubmit + PreToolUse hook handler.

Lock UX flow (Option 4 — out-of-band token):
  Locked + no token  → block with "run claudeguard unlock in terminal"
  Locked + token     → consume token, unlock, pass through
  Unlocked           → record activity, pass through

PreToolUse: deny sensitive tool calls touching ~/.claude/projects/ while locked.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from lib.crypto import has_passcode
from lib.config import read_config
from lib.state import is_locked, record_activity, is_locked_out, consume_unlock_token, unlock, read_state
from lib.paths import PROJECTS_DIR, CLAUDEGUARD_DIR

SENSITIVE_TOOLS = {"Read", "Write", "Edit", "MultiEdit", "Bash", "Glob", "Grep"}

LOCK_MESSAGE = (
    "🔒 ClaudeGuard is locked.\n\n"
    "Run `claudeguard unlock` in a terminal, then send any message to continue."
)


def _touches_sensitive_path(tool_input: dict) -> bool:
    candidates = [
        tool_input.get("file_path", ""),
        tool_input.get("path", ""),
        tool_input.get("directory", ""),
        tool_input.get("command", ""),
        tool_input.get("pattern", ""),
    ]
    text = " ".join(c for c in candidates if c)
    return (
        PROJECTS_DIR in text
        or CLAUDEGUARD_DIR in text
        or ".claude/projects" in text
        or "~/.claude" in text
    )


def _pass() -> None:
    print(json.dumps({"continue": True}))


def _block(msg: str) -> None:
    print(json.dumps({"continue": False, "stopReason": msg}))


def _deny_tool(msg: str) -> None:
    print(json.dumps({
        "continue": False,
        "hookSpecificOutput": {
            "permissionDecision": "deny",
            "permissionDecisionReason": msg,
        },
    }))


def main():
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except Exception:
        payload = {}

    if not has_passcode():
        _pass()
        return

    config = read_config()
    if not config.get("enabled", True):
        _pass()
        return

    event = payload.get("hook_event_name", "")

    # ── PreToolUse ────────────────────────────────────────────────────────────
    if event == "PreToolUse":
        if not is_locked(config):
            record_activity()
            _pass()
            return
        tool_name = payload.get("tool_name", "")
        if tool_name in SENSITIVE_TOOLS and _touches_sensitive_path(payload.get("tool_input", {})):
            _deny_tool("ClaudeGuard is locked. Run `claudeguard unlock` in a terminal first.")
            return
        _pass()
        return

    # ── UserPromptSubmit ──────────────────────────────────────────────────────
    if event != "UserPromptSubmit":
        _pass()
        return

    if not is_locked(config):
        record_activity()
        _pass()
        return

    # Locked — check for out-of-band unlock token
    if consume_unlock_token():
        unlock()
        _pass()
        return

    # Still locked
    if is_locked_out():
        state = read_state()
        _block(f"🔒 Too many failed attempts. Locked out until {state.get('lockoutUntil')}.")
        return

    _block(LOCK_MESSAGE)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"claudeguard check_lock error: {e}", file=sys.stderr)
        sys.exit(2)
