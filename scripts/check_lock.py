#!/usr/bin/env python3
"""
UserPromptSubmit + PreToolUse hook handler.

Lock UX flow (Option A — inline passcode):
  First prompt while locked  → set awaitingPasscode=True, block with passcode prompt
  Second prompt               → treat input as passcode, verify inline
    - correct → unlock, suppress prompt (don't send passcode to Claude)
    - wrong   → record failure, block with error + re-prompt
  Subsequent prompts (unlocked) → pass through
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from lib.crypto import has_passcode, verify_passcode
from lib.config import read_config
from lib.state import (
    is_locked, record_activity, is_locked_out,
    is_awaiting_passcode, set_awaiting_passcode,
    unlock, record_failed_attempt, read_state,
)
from lib.paths import PROJECTS_DIR, CLAUDEGUARD_DIR

SENSITIVE_TOOLS = {"Read", "Write", "Edit", "MultiEdit", "Bash", "Glob", "Grep"}

PASSCODE_PROMPT = (
    "🔒 ClaudeGuard is locked.\n\n"
    "Type your passcode in the message box and press Enter to unlock."
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


def _pass() -> None:
    print(json.dumps({"continue": True}))


def _suppress() -> None:
    """Allow the turn to continue but tell Claude the prompt was handled by the hook."""
    print(json.dumps({
        "continue": True,
        "suppressOutput": True,
        "hookSpecificOutput": {
            "additionalContext": "ClaudeGuard: passcode accepted, session unlocked. Greet the user briefly.",
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
        if tool_name not in SENSITIVE_TOOLS:
            _pass()
            return
        if _touches_sensitive_path(payload.get("tool_input", {})):
            _deny_tool("ClaudeGuard is locked. Unlock first.")
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

    # Locked out entirely
    if is_locked_out():
        state = read_state()
        _block(f"🔒 Too many failed attempts. Locked out until {state.get('lockoutUntil', 'unknown')}.")
        return

    prompt_text = payload.get("prompt", "").strip()

    # ── State: awaiting passcode — treat prompt as passcode attempt ───────────
    if is_awaiting_passcode():
        if verify_passcode(prompt_text):
            unlock()
            _suppress()
            return
        # Wrong passcode
        record_failed_attempt(config)
        state = read_state()
        attempts = state.get("failedAttempts", 0)
        max_a = config.get("maxFailedAttempts", 5)
        remaining = max(0, max_a - attempts)
        if is_locked_out():
            _block(f"🔒 Too many failed attempts. Locked out until {state.get('lockoutUntil')}.")
        else:
            _block(f"❌ Wrong passcode. {remaining} attempt(s) remaining.\n\nType your passcode to try again.")
        return

    # ── State: locked, first prompt → ask for passcode ────────────────────────
    set_awaiting_passcode(True)
    _block(PASSCODE_PROMPT)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"claudeguard check_lock error: {e}", file=sys.stderr)
        sys.exit(2)
