#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="$HOME/.local/share/claudeguard"
SETTINGS_FILE="$HOME/.claude/settings.json"
CLAUDEGUARD_DIR="$HOME/.claude/claudeguard"
LOCAL_BIN="$HOME/.local/bin/claudeguard"

echo "=== ClaudeGuard Uninstall ==="
echo ""
echo "This will:"
echo "  - Remove hooks from $SETTINGS_FILE"
echo "  - Delete $CLAUDEGUARD_DIR (passcode hash, state, config)"
echo "  - Delete $INSTALL_DIR (source files)"
echo "  - Remove $LOCAL_BIN symlink"
echo ""
read -r -p "Continue? [y/N]: " confirm
if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
  echo "Aborted."
  exit 0
fi

# ── 1. Remove hooks from settings.json ───────────────────────────────────────
if [[ -f "$SETTINGS_FILE" ]]; then
  PYTHON=""
  for candidate in python3 python; do
    if command -v "$candidate" &>/dev/null; then
      PYTHON="$candidate"
      break
    fi
  done

  if [[ -n "$PYTHON" ]]; then
    "$PYTHON" - <<PYEOF
import json, os

settings_path = "$SETTINGS_FILE"
markers = ["session_start.py", "check_lock.py"]

with open(settings_path) as f:
    settings = json.load(f)

hooks = settings.get("hooks", {})

def strip_claudeguard(hook_list):
    if not hook_list:
        return hook_list
    cleaned = []
    for entry in hook_list:
        entry_hooks = [
            h for h in entry.get("hooks", [])
            if not any(m in str(a) for a in h.get("args", []) for m in markers)
        ]
        if entry_hooks:
            cleaned.append({**entry, "hooks": entry_hooks})
    return cleaned or None

for event in ["SessionStart", "UserPromptSubmit", "PreToolUse"]:
    result = strip_claudeguard(hooks.get(event))
    if result is None:
        hooks.pop(event, None)
    else:
        hooks[event] = result

if not hooks:
    settings.pop("hooks", None)
else:
    settings["hooks"] = hooks

with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2)
    f.write("\n")

print("Hooks removed from settings.json")
PYEOF
  else
    echo "WARNING: python3 not found — remove ClaudeGuard hooks from $SETTINGS_FILE manually."
  fi
else
  echo "No settings.json found — skipping."
fi

# ── 2. Delete data directory ──────────────────────────────────────────────────
if [[ -d "$CLAUDEGUARD_DIR" ]]; then
  rm -rf "$CLAUDEGUARD_DIR"
  echo "Deleted $CLAUDEGUARD_DIR"
else
  echo "No data directory found — skipping."
fi

# ── 3. Delete install directory ───────────────────────────────────────────────
if [[ -d "$INSTALL_DIR" ]]; then
  rm -rf "$INSTALL_DIR"
  echo "Deleted $INSTALL_DIR"
else
  echo "No install directory found — skipping."
fi

# ── 4. Remove symlink ─────────────────────────────────────────────────────────
if [[ -L "$LOCAL_BIN" || -f "$LOCAL_BIN" ]]; then
  rm "$LOCAL_BIN"
  echo "Removed $LOCAL_BIN"
else
  echo "No symlink found at $LOCAL_BIN — skipping."
fi

echo ""
echo "ClaudeGuard uninstalled."
