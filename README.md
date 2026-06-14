# ClaudeGuard

Local passcode lock for [Claude Code](https://claude.ai/code) conversation history.

Claude Code stores all past conversations as plaintext JSON under `~/.claude/projects/`. Anyone with access to your logged-in machine can read them. ClaudeGuard adds an optional, opt-in lock screen — similar to Telegram Desktop's "Local Passcode" — that gates access behind a bcrypt-hashed passcode with optional Touch ID / Windows Hello unlock.

> **Reference:** [anthropics/claude-code#53960](https://github.com/anthropics/claude-code/issues/53960)

---

## Features

- **Opt-in, off by default** — no impact until you run `claudeguard setup`
- **Passcode stored as bcrypt hash** (cost=12) — never plaintext
- **Auto-lock** after configurable inactivity period (default 60 min, supports 0 = never)
- **Biometric unlock** — Touch ID on macOS, Windows Hello on Windows
- **Manual lock** — `claudeguard lock` or `/claudeguard lock` inside Claude Code
- **Lockout protection** — configurable max failed attempts + lockout duration
- **Hook-based** — uses Claude Code's `UserPromptSubmit` + `PreToolUse` hooks to gate all prompts and file access to `~/.claude/projects/`

---

## How it Works

Claude Code's hook system cannot block session startup, so ClaudeGuard uses two hooks:

1. **`SessionStart`** — checks if auto-lock threshold was exceeded; if so, sets state to locked and injects a system message telling Claude not to reference history
2. **`UserPromptSubmit`** — blocks every prompt while locked, instructing the user to run `claudeguard unlock`
3. **`PreToolUse`** — denies any tool (`Read`, `Write`, `Edit`, `Bash`, etc.) that would access `~/.claude/projects/` while locked

The passcode hash lives in `~/.claude/claudeguard/passcode.hash` (mode 0600). Lock state lives in `~/.claude/claudeguard/state.json`. Neither the passcode nor any derivative key is held in memory longer than needed.

---

## Requirements

- Node.js 18+
- Claude Code 2.x+

Optional:
- `keytar` — required for biometric unlock (Keychain / Credential Manager integration)

---

## Installation

### Option A: npm global install

```bash
npm install -g claudeguard
claudeguard setup
```

Then register the hooks in your Claude Code user settings (`~/.claude/settings.json`):

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [{ "type": "command", "command": "node", "args": ["/path/to/claudeguard/scripts/session-start.js"], "async": true }]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [{ "type": "command", "command": "node", "args": ["/path/to/claudeguard/scripts/check-lock.js"], "timeout": 30 }]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Read|Write|Edit|MultiEdit|Bash|Glob|Grep",
        "hooks": [{ "type": "command", "command": "node", "args": ["/path/to/claudeguard/scripts/check-lock.js"], "timeout": 30 }]
      }
    ]
  }
}
```

### Option B: Claude Code Plugin (when plugin marketplace supports it)

Clone this repo to `~/.claude/plugins/claudeguard/` and enable via Claude Code settings.

---

## Usage

### First-time setup

```bash
claudeguard setup
```

Interactive prompts:
- Set a passcode (min 4 characters)
- Choose auto-lock timeout
- Optionally enable Touch ID / Windows Hello

### Daily use

```bash
claudeguard lock       # Lock immediately
claudeguard unlock     # Prompt for passcode (or biometric)
claudeguard status     # Show current state
```

Inside Claude Code, use the skill:
```
/claudeguard unlock
/claudeguard lock
/claudeguard status
```

### Change passcode

```bash
claudeguard change-passcode
```

### Reconfigure

```bash
claudeguard config
```

### Disable ClaudeGuard

```bash
claudeguard disable
```

Removes the hash file and disables all hooks. Claude Code returns to default behavior.

---

## Configuration

`~/.claude/claudeguard/config.json`:

| Key | Default | Description |
|-----|---------|-------------|
| `enabled` | `true` | Master switch |
| `autoLockMinutes` | `60` | Minutes of inactivity before auto-lock. `0` = never |
| `biometricEnabled` | `false` | Touch ID / Windows Hello unlock |
| `maxFailedAttempts` | `5` | Failed attempts before lockout |
| `lockoutDurationMinutes` | `15` | Duration of lockout after too many failures |

---

## Security Notes

- The hook-based lock is **defense-in-depth within Claude Code**. An attacker with direct filesystem access can bypass it by deleting `~/.claude/claudeguard/state.json`.
- For full protection against local attackers, combine with OS-level disk encryption (FileVault on macOS, BitLocker on Windows).
- The passcode hash uses bcrypt with cost factor 12 (~300ms per attempt), making offline brute-force expensive.
- Biometric authentication delegates to the OS (Touch ID via macOS Security framework, Windows Hello via UserConsentVerifier). The actual passcode is stored in the OS keychain and only retrieved after successful biometric authentication.

---

## Development

```bash
git clone https://github.com/YOUR_USERNAME/claudeguard
cd claudeguard
npm install
npm test
```

### Project structure

```
claudeguard/
├── .claude-plugin/plugin.json   # Plugin manifest
├── hooks/hooks.json             # Hook registrations
├── scripts/
│   ├── session-start.js         # SessionStart hook handler
│   └── check-lock.js            # UserPromptSubmit + PreToolUse handler
├── cli/claudeguard.js           # CLI entry point
├── lib/
│   ├── paths.js                 # Path constants
│   ├── config.js                # Config read/write
│   ├── crypto.js                # bcrypt hash/verify
│   ├── state.js                 # Lock state machine
│   ├── keychain.js              # OS keychain (keytar)
│   └── biometric.js             # Touch ID / Windows Hello
├── skills/claudeguard-unlock/   # Claude Code skill
├── test/                        # Jest tests
└── PLAN.md                      # Architecture decisions
```

---

## Contributing

PRs welcome. Please open an issue first for significant changes.

---

## License

MIT
