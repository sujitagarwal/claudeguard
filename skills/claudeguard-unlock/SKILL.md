---
name: claudeguard-unlock
description: Unlock ClaudeGuard by running the passcode or biometric check. Use when the user types /claudeguard unlock or when ClaudeGuard reports it is locked.
triggers:
  - /claudeguard unlock
  - /claudeguard lock
  - /claudeguard status
---

When the user runs `/claudeguard unlock`:
1. Tell the user: "Running ClaudeGuard unlock in your terminal..."
2. Use the Bash tool to run: `claudeguard unlock`
3. If the command exits 0, tell the user they are unlocked and can continue.
4. If the command exits non-zero, relay the error message verbatim.

When the user runs `/claudeguard lock`:
1. Use the Bash tool to run: `claudeguard lock`
2. Confirm locked.

When the user runs `/claudeguard status`:
1. Use the Bash tool to run: `claudeguard status`
2. Display the output.

Do not attempt to read or infer the passcode. Do not bypass the lock by other means.
