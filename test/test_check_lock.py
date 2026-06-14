"""
Integration tests for scripts/check_lock.py.
Spawns the script as a subprocess with mocked state files.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

TMPDIR = tempfile.mkdtemp()
SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "scripts", "check_lock.py")
HASH_FILE   = os.path.join(TMPDIR, "passcode.hash")
STATE_FILE  = os.path.join(TMPDIR, "state.json")
CONFIG_FILE = os.path.join(TMPDIR, "config.json")


def _write(path, data):
    with open(path, "w") as f:
        json.dump(data, f) if isinstance(data, dict) else f.write(data)
    os.chmod(path, 0o600)


def _run(payload: dict) -> dict:
    env = os.environ.copy()
    env["CLAUDEGUARD_TEST_DIR"] = TMPDIR
    result = subprocess.run(
        [sys.executable, SCRIPT],
        input=json.dumps(payload),
        capture_output=True, text=True, env=env,
    )
    return json.loads(result.stdout)


class TestCheckLock(unittest.TestCase):

    def setUp(self):
        # Minimal valid hash (won't be verified in these tests, just needs to exist)
        _write(HASH_FILE, "a" * 64 + ":" + "b" * 128)
        _write(CONFIG_FILE, {"enabled": True, "autoLockMinutes": 60})

    def tearDown(self):
        for f in [HASH_FILE, STATE_FILE, CONFIG_FILE]:
            if os.path.exists(f): os.unlink(f)

    def _set_state(self, locked: bool):
        from datetime import datetime, timezone
        _write(STATE_FILE, {
            "locked": locked,
            "lastActivityAt": datetime.now(timezone.utc).isoformat(),
            "failedAttempts": 0,
            "lockoutUntil": None,
        })

    def test_prompt_passes_when_unlocked(self):
        self._set_state(locked=False)
        r = _run({"hook_event_name": "UserPromptSubmit", "prompt": "hello"})
        self.assertTrue(r["continue"])

    def test_prompt_blocked_when_locked(self):
        self._set_state(locked=True)
        r = _run({"hook_event_name": "UserPromptSubmit", "prompt": "hello"})
        self.assertFalse(r["continue"])
        self.assertIn("ClaudeGuard", r["stopReason"])

    def test_read_allowed_nonsensitive_when_unlocked(self):
        self._set_state(locked=False)
        r = _run({
            "hook_event_name": "PreToolUse",
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/some-file.txt"},
        })
        self.assertTrue(r["continue"])

    def test_read_denied_projects_when_locked(self):
        self._set_state(locked=True)
        home = os.path.expanduser("~")
        projects_path = os.path.join(home, ".claude", "projects", "test.jsonl")
        r = _run({
            "hook_event_name": "PreToolUse",
            "tool_name": "Read",
            "tool_input": {"file_path": projects_path},
        })
        self.assertFalse(r["continue"])
        self.assertEqual(r["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_passthrough_when_no_passcode(self):
        os.unlink(HASH_FILE)
        r = _run({"hook_event_name": "UserPromptSubmit", "prompt": "hi"})
        self.assertTrue(r["continue"])


if __name__ == "__main__":
    unittest.main()
