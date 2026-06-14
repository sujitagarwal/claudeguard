import os
import sys
import tempfile
import unittest

# Redirect paths to temp dir before importing lib modules
TMPDIR = tempfile.mkdtemp()
os.environ["CLAUDEGUARD_TEST_DIR"] = TMPDIR

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Patch paths before any lib import
import lib.paths as _paths
_paths.CLAUDEGUARD_DIR = TMPDIR
_paths.HASH_FILE = os.path.join(TMPDIR, "passcode.hash")
_paths.STATE_FILE = os.path.join(TMPDIR, "state.json")
_paths.CONFIG_FILE = os.path.join(TMPDIR, "config.json")

import lib.crypto as crypto
crypto.HASH_FILE = _paths.HASH_FILE  # propagate patch


class TestCrypto(unittest.TestCase):

    def tearDown(self):
        if os.path.exists(_paths.HASH_FILE):
            os.unlink(_paths.HASH_FILE)

    def test_hash_format(self):
        h = crypto.hash_passcode("test1234")
        parts = h.split(":")
        self.assertEqual(len(parts), 2)
        self.assertEqual(len(parts[0]), 64)   # 32 bytes hex
        self.assertEqual(len(parts[1]), 128)  # 64 bytes hex

    def test_verify_correct(self):
        h = crypto.hash_passcode("correct-horse")
        crypto.save_hash(h)
        self.assertTrue(crypto.verify_passcode("correct-horse"))

    def test_verify_wrong(self):
        h = crypto.hash_passcode("correct-horse")
        crypto.save_hash(h)
        self.assertFalse(crypto.verify_passcode("wrong-passcode"))

    def test_verify_no_file(self):
        self.assertFalse(crypto.verify_passcode("anything"))

    def test_unique_salts(self):
        h1 = crypto.hash_passcode("same")
        h2 = crypto.hash_passcode("same")
        self.assertNotEqual(h1, h2)
        crypto.save_hash(h1)
        self.assertTrue(crypto.verify_passcode("same"))

    def test_has_passcode_false(self):
        self.assertFalse(crypto.has_passcode())

    def test_has_passcode_true(self):
        crypto.save_hash(crypto.hash_passcode("x"))
        self.assertTrue(crypto.has_passcode())

    def test_hash_file_permissions(self):
        crypto.save_hash(crypto.hash_passcode("x"))
        mode = oct(os.stat(_paths.HASH_FILE).st_mode)[-3:]
        self.assertEqual(mode, "600")


if __name__ == "__main__":
    unittest.main()
