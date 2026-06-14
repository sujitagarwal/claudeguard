import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta

TMPDIR = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lib.paths as _paths
_paths.CLAUDEGUARD_DIR = TMPDIR
_paths.HASH_FILE  = os.path.join(TMPDIR, "passcode.hash")
_paths.STATE_FILE = os.path.join(TMPDIR, "state.json")
_paths.CONFIG_FILE = os.path.join(TMPDIR, "config.json")

import lib.state as state
state.STATE_FILE = _paths.STATE_FILE


def _clean():
    for f in [_paths.STATE_FILE]:
        if os.path.exists(f):
            os.unlink(f)


class TestState(unittest.TestCase):

    def setUp(self):
        _clean()

    def test_default_locked(self):
        s = state.read_state()
        self.assertTrue(s["locked"])
        self.assertEqual(s["failedAttempts"], 0)

    def test_unlock(self):
        state.unlock()
        s = state.read_state()
        self.assertFalse(s["locked"])
        self.assertIsNotNone(s["unlockedAt"])
        self.assertEqual(s["failedAttempts"], 0)

    def test_lock(self):
        state.unlock()
        state.lock()
        self.assertTrue(state.read_state()["locked"])

    def test_is_locked_when_locked(self):
        state.lock()
        self.assertTrue(state.is_locked({"autoLockMinutes": 60}))

    def test_is_locked_false_when_unlocked_recent(self):
        state.unlock()
        self.assertFalse(state.is_locked({"autoLockMinutes": 60}))

    def test_auto_lock_on_inactivity(self):
        old = (datetime.now(timezone.utc) - timedelta(minutes=61)).isoformat()
        state.write_state({"locked": False, "lastActivityAt": old})
        self.assertTrue(state.is_locked({"autoLockMinutes": 60}))

    def test_never_auto_lock_when_zero(self):
        old = (datetime.now(timezone.utc) - timedelta(days=999)).isoformat()
        state.write_state({"locked": False, "lastActivityAt": old})
        self.assertFalse(state.is_locked({"autoLockMinutes": 0}))

    def test_lockout_after_max_attempts(self):
        config = {"maxFailedAttempts": 3, "lockoutDurationMinutes": 15}
        state.record_failed_attempt(config)
        state.record_failed_attempt(config)
        state.record_failed_attempt(config)
        self.assertTrue(state.is_locked_out())

    def test_lockout_expires(self):
        past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        state.write_state({"lockoutUntil": past})
        self.assertFalse(state.is_locked_out())


if __name__ == "__main__":
    unittest.main()
