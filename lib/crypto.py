"""
Passcode hashing via hashlib.scrypt (Python 3.6+, no deps).
Format on disk: <hex salt>:<hex hash>
Parameters: N=2^15, r=8, p=1, dklen=64  — comparable to bcrypt cost 12.
"""
import hashlib
import hmac
import os
import stat
from lib.paths import HASH_FILE

SALT_LEN = 32
DK_LEN   = 64
N, R, P  = 1 << 15, 8, 1
# OpenSSL caps scrypt memory by default; override to allow N=2^15 (r=8 → 256 MB)
MAXMEM   = 512 * 1024 * 1024  # 512 MB


def _scrypt(passcode: bytes, salt: bytes) -> bytes:
    return hashlib.scrypt(passcode, salt=salt, n=N, r=R, p=P, dklen=DK_LEN, maxmem=MAXMEM)


def hash_passcode(passcode: str) -> str:
    salt = os.urandom(SALT_LEN)
    dk = _scrypt(passcode.encode(), salt)
    return f"{salt.hex()}:{dk.hex()}"


def verify_passcode(passcode: str) -> bool:
    if not os.path.exists(HASH_FILE):
        return False
    with open(HASH_FILE) as f:
        stored = f.read().strip()
    parts = stored.split(":")
    if len(parts) != 2:
        return False
    salt = bytes.fromhex(parts[0])
    expected = bytes.fromhex(parts[1])
    actual = _scrypt(passcode.encode(), salt)
    return hmac.compare_digest(actual, expected)


def save_hash(h: str) -> None:
    with open(HASH_FILE, "w") as f:
        f.write(h)
    os.chmod(HASH_FILE, stat.S_IRUSR | stat.S_IWUSR)  # 0600


def has_passcode() -> bool:
    return os.path.exists(HASH_FILE)
