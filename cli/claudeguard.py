#!/usr/bin/env python3
"""
claudeguard CLI
Commands: setup | lock | unlock | status | config | change-passcode | disable
"""
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from lib.crypto import hash_passcode, verify_passcode, save_hash, has_passcode
from lib.config import read_config, write_config
from lib.state import read_state, lock, unlock, is_locked, is_locked_out, record_failed_attempt, write_unlock_token
from lib.paths import HASH_FILE


# ── Helpers ────────────────────────────────────────────────────────────────

def ask(question: str, hidden: bool = False) -> str:
    if hidden:
        return getpass.getpass(question)
    return input(question).strip()


def die(msg: str, code: int = 1):
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(code)


# ── Commands ───────────────────────────────────────────────────────────────

def cmd_setup():
    if has_passcode():
        die("ClaudeGuard already set up. Use `claudeguard change-passcode` to change it.")

    print("=== ClaudeGuard Setup ===\n")
    pass1 = ask("Enter passcode: ", hidden=True)
    if len(pass1) < 4:
        die("Passcode must be at least 4 characters.")
    pass2 = ask("Confirm passcode: ", hidden=True)
    if pass1 != pass2:
        die("Passcodes do not match.")

    save_hash(hash_passcode(pass1))

    raw = ask("Auto-lock after minutes (default 60, 0=never): ")
    try:
        auto_lock = int(raw)
    except ValueError:
        auto_lock = 60
    write_config({"autoLockMinutes": auto_lock})

    lock()
    print("\nClaudeGuard is active. Claude Code sessions will require your passcode on first prompt.")


def cmd_lock():
    lock()
    print("Locked.")


def cmd_unlock():
    if not has_passcode():
        die("ClaudeGuard not set up. Run `claudeguard setup`.")

    if is_locked_out():
        state = read_state()
        die(f"Too many failed attempts. Locked out until {state.get('lockoutUntil')}.")

    config = read_config()
    passcode = ask("Passcode: ", hidden=True)
    if not verify_passcode(passcode):
        record_failed_attempt(config)
        state = read_state()
        attempts = state.get("failedAttempts", 0)
        remaining = max(0, config.get("maxFailedAttempts", 5) - attempts)
        die(f"Wrong passcode. {remaining} attempt(s) remaining.")

    write_unlock_token()
    print("✓ Passcode accepted. Switch to Claude Code and send any message to continue.")


def cmd_status():
    config = read_config()
    state = read_state()
    locked = is_locked(config)
    locked_out = is_locked_out()

    print(f"Status:       {'LOCKED' if locked else 'UNLOCKED'}")
    if locked_out:
        print("              (locked out — too many failed attempts)")
    if not locked and state.get("lastActivityAt"):
        from datetime import datetime, timezone
        last = datetime.fromisoformat(state["lastActivityAt"])
        elapsed_min = (datetime.now(timezone.utc) - last).total_seconds() / 60
        auto_min = config.get("autoLockMinutes", 60)
        if auto_min > 0:
            remaining = max(0, int(auto_min - elapsed_min))
            print(f"Auto-lock in: {remaining} min")
        else:
            print("Auto-lock:    disabled")
    print(f"Passcode set: {'yes' if has_passcode() else 'no'}")
    auto_min = config.get("autoLockMinutes", 60)
    print(f"Auto-lock:    {'never' if auto_min == 0 else f'{auto_min} min'}")


def cmd_config():
    config = read_config()
    raw = ask(f"Auto-lock minutes [{config.get('autoLockMinutes', 60)}]: ")
    if raw:
        try:
            write_config({"autoLockMinutes": int(raw)})
        except ValueError:
            pass
    print("Config saved.")


def cmd_change_passcode():
    if not has_passcode():
        die("ClaudeGuard not set up.")

    current = ask("Current passcode: ", hidden=True)
    if not verify_passcode(current):
        die("Wrong passcode.")

    pass1 = ask("New passcode: ", hidden=True)
    if len(pass1) < 4:
        die("Passcode must be at least 4 characters.")
    pass2 = ask("Confirm new passcode: ", hidden=True)
    if pass1 != pass2:
        die("Passcodes do not match.")

    save_hash(hash_passcode(pass1))
    print("Passcode changed.")


def cmd_disable():
    if not has_passcode():
        print("ClaudeGuard not enabled.")
        return

    passcode = ask("Confirm current passcode to disable: ", hidden=True)
    if not verify_passcode(passcode):
        die("Wrong passcode.")

    if os.path.exists(HASH_FILE):
        os.unlink(HASH_FILE)
    write_config({"enabled": False})
    print("ClaudeGuard disabled. Passcode hash deleted.")


# ── Dispatch ───────────────────────────────────────────────────────────────

COMMANDS = {
    "setup":           cmd_setup,
    "lock":            cmd_lock,
    "unlock":          cmd_unlock,
    "status":          cmd_status,
    "config":          cmd_config,
    "change-passcode": cmd_change_passcode,
    "disable":         cmd_disable,
}

USAGE = """\
Usage: claudeguard <command>

Commands:
  setup           Set up passcode for the first time
  lock            Lock immediately
  unlock          Prompt for passcode and unlock
  status          Show lock status and config
  config          Edit configuration
  change-passcode Change the passcode
  disable         Remove passcode and disable ClaudeGuard
"""

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else None
    if not cmd or cmd not in COMMANDS:
        print(USAGE)
        sys.exit(0 if not cmd else 1)
    try:
        COMMANDS[cmd]()
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(1)
    except Exception as e:
        die(str(e))
