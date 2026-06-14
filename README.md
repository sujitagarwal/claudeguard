# ClaudeGuard

**Passcode-protect your Claude Code conversation history.**

No more worrying about someone opening Claude Code on your machine and reading all your past conversations.

[![GitHub repository](https://img.shields.io/badge/GitHub-Repository-blue?logo=github)](https://github.com/sujitagarwal/claudeguard)
[![GitHub profile](https://img.shields.io/badge/GitHub-Profile-lightgrey?logo=github)](https://github.com/sujitagarwal)
[![GitHub stars](https://img.shields.io/github/stars/sujitagarwal/claudeguard?style=social)](https://github.com/sujitagarwal/claudeguard/stargazers)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey)](#install)

---

## Install

**macOS / Linux**

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/sujitagarwal/claudeguard/main/install.sh)"
```

**Windows** — open PowerShell and run:

```powershell
irm https://raw.githubusercontent.com/sujitagarwal/claudeguard/main/install.ps1 | iex
```

Requires Python 3.6+. No other dependencies.

---

## Quick Start

```bash
# First-time setup
claudeguard setup

# Lock immediately
claudeguard lock

# Unlock
claudeguard unlock
```

Once set up, every Claude Code session prompts for your passcode before any prompt is processed. Type your passcode directly into the Claude Code message box — no terminal switching needed.

---

## How It Works

Claude Code stores all conversation history as plaintext JSON under `~/.claude/projects/`. Anyone with access to your logged-in machine can read it. ClaudeGuard adds an opt-in lock screen via Claude Code's hook system.

When locked:

1. **First message** — hook intercepts it and asks for your passcode
2. **You type your passcode** — hook verifies inline, unlocks silently
3. **Session continues** — Claude never sees the passcode

Auto-lock kicks in after configurable inactivity (default 60 min).

> Reference: [anthropics/claude-code#53960](https://github.com/anthropics/claude-code/issues/53960)

---

## Commands

| Command | Description |
|---------|-------------|
| `claudeguard setup` | First-time passcode setup |
| `claudeguard lock` | Lock immediately |
| `claudeguard unlock` | Unlock via passcode |
| `claudeguard status` | Show lock state and config |
| `claudeguard config` | Edit configuration |
| `claudeguard change-passcode` | Change the passcode |
| `claudeguard disable` | Remove passcode and disable ClaudeGuard |

---

## Configuration

`~/.claude/claudeguard/config.json`:

| Key | Default | Description |
|-----|---------|-------------|
| `enabled` | `true` | Master switch |
| `autoLockMinutes` | `60` | Inactivity minutes before auto-lock. `0` = never |
| `maxFailedAttempts` | `5` | Failed attempts before lockout |
| `lockoutDurationMinutes` | `15` | Lockout duration after too many failures |

---

## Security

- Passcode stored as a [scrypt](https://en.wikipedia.org/wiki/Scrypt) hash (`N=2^15, r=8, p=1`) — never plaintext
- Verification uses `hmac.compare_digest` to prevent timing attacks
- Data directory `~/.claude/claudeguard/` has mode `0700`, all files `0600`
- Hook-based protection gates Claude Code specifically — not a substitute for OS-level disk encryption (FileVault / BitLocker)

---

## Uninstall

**macOS / Linux**

```bash
bash uninstall.sh
```

You'll be asked to confirm before anything is deleted.

---

## Credits

Created by [Sujit Agarwal](https://github.com/sujitagarwal)
