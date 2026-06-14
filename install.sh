#!/usr/bin/env bash
set -euo pipefail

REPO="https://github.com/sujitagarwal/claudeguard.git"
INSTALL_DIR="$HOME/.local/share/claudeguard"
SETTINGS_FILE="$HOME/.claude/settings.json"
LOCAL_BIN="$HOME/.local/bin"

echo "=== ClaudeGuard Install ==="
echo ""

# ── 1. Python 3.6+ check ──────────────────────────────────────────────────────
PYTHON=""
for candidate in python3 python; do
  if command -v "$candidate" &>/dev/null; then
    VER=$("$candidate" -c "import sys; print(sys.version_info.major * 100 + sys.version_info.minor)")
    if [[ "$VER" -ge 306 ]]; then
      PYTHON="$candidate"
      break
    fi
  fi
done

if [[ -z "$PYTHON" ]]; then
  echo "ERROR: Python 3.6+ not found." >&2
  echo "  macOS:   brew install python3  OR  https://python.org" >&2
  echo "  Linux:   apt install python3   OR  dnf install python3" >&2
  echo "  Windows: https://python.org/downloads" >&2
  exit 1
fi
echo "✓ $($PYTHON --version)"

if ! "$PYTHON" -c "import hashlib; hashlib.scrypt(b'x', salt=b'y'*16, n=1024, r=8, p=1)" 2>/dev/null; then
  echo "ERROR: hashlib.scrypt unavailable in this Python build. Install from python.org." >&2
  exit 1
fi
echo "✓ hashlib.scrypt available"

# ── 2. git check ──────────────────────────────────────────────────────────────
if ! command -v git &>/dev/null; then
  echo "ERROR: git not found. Install git and retry." >&2
  exit 1
fi

# ── 3. Clone or update repo ───────────────────────────────────────────────────
if [[ -d "$INSTALL_DIR/.git" ]]; then
  echo "Updating existing install..."
  git -C "$INSTALL_DIR" pull --ff-only --quiet
  echo "✓ Updated"
else
  echo "Cloning ClaudeGuard..."
  git clone --quiet "$REPO" "$INSTALL_DIR"
  echo "✓ Cloned to $INSTALL_DIR"
fi

# ── 4. Make scripts executable ────────────────────────────────────────────────
chmod +x "$INSTALL_DIR/scripts/session_start.py"
chmod +x "$INSTALL_DIR/scripts/check_lock.py"
chmod +x "$INSTALL_DIR/cli/claudeguard.py"

# ── 5. Symlink claudeguard into PATH ──────────────────────────────────────────
mkdir -p "$LOCAL_BIN"
ln -sf "$INSTALL_DIR/cli/claudeguard.py" "$LOCAL_BIN/claudeguard"
echo "✓ claudeguard linked → $LOCAL_BIN/claudeguard"

if [[ ":$PATH:" != *":$LOCAL_BIN:"* ]]; then
  echo ""
  echo "NOTE: Add $LOCAL_BIN to your PATH:"
  echo "  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.zshrc"
  echo "  source ~/.zshrc"
  echo ""
fi

# ── 6. Register hooks in ~/.claude/settings.json ─────────────────────────────
echo "Registering hooks in $SETTINGS_FILE ..."
mkdir -p "$(dirname "$SETTINGS_FILE")"

"$PYTHON" - <<PYEOF
import json, os

settings_path = "$SETTINGS_FILE"
plugin_dir    = "$INSTALL_DIR"

settings = {}
if os.path.exists(settings_path):
    try:
        with open(settings_path) as f:
            settings = json.load(f)
    except Exception:
        settings = {}

if "hooks" not in settings:
    settings["hooks"] = {}

def already_registered(hook_list, script_name):
    for entry in (hook_list or []):
        for h in entry.get("hooks", []):
            if any(script_name in str(a) for a in h.get("args", [])):
                return True
    return False

session_hook = {
    "hooks": [{
        "type": "command", "command": "python3",
        "args": [plugin_dir + "/scripts/session_start.py"],
        "timeout": 30, "async": True,
    }]
}
check_hook = {
    "hooks": [{
        "type": "command", "command": "python3",
        "args": [plugin_dir + "/scripts/check_lock.py"],
        "timeout": 30,
    }]
}
check_hook_pre = {
    "matcher": "Read|Write|Edit|MultiEdit|Bash|Glob|Grep",
    "hooks": [{
        "type": "command", "command": "python3",
        "args": [plugin_dir + "/scripts/check_lock.py"],
        "timeout": 30,
    }]
}

if not already_registered(settings["hooks"].get("SessionStart"), "session_start.py"):
    settings["hooks"].setdefault("SessionStart", []).append(session_hook)

if not already_registered(settings["hooks"].get("UserPromptSubmit"), "check_lock.py"):
    settings["hooks"].setdefault("UserPromptSubmit", []).append(check_hook)

if not already_registered(settings["hooks"].get("PreToolUse"), "check_lock.py"):
    settings["hooks"].setdefault("PreToolUse", []).append(check_hook_pre)

with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2)
    f.write("\n")
os.chmod(settings_path, 0o600)
print("Hooks registered.")
PYEOF

echo "✓ Hooks registered"

# ── 7. First-time passcode setup ──────────────────────────────────────────────
if [[ ! -f "$HOME/.claude/claudeguard/passcode.hash" ]]; then
  echo ""
  echo "Running first-time passcode setup..."
  echo ""
  "$PYTHON" "$INSTALL_DIR/cli/claudeguard.py" setup
fi

echo ""
echo "=== ClaudeGuard installed ==="
echo ""
echo "Commands:"
echo "  claudeguard lock            Lock now"
echo "  claudeguard unlock          Unlock with passcode"
echo "  claudeguard status          Show status"
echo "  claudeguard config          Edit config"
echo "  claudeguard change-passcode Change passcode"
echo "  claudeguard disable         Remove passcode and disable"
