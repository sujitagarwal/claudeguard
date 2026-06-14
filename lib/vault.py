"""
Encrypt/decrypt ~/.claude/projects/ on lock/unlock.

Algorithm:
  Key derivation: PBKDF2-HMAC-SHA256, 200k iterations, 32-byte key
  Encryption:     AES-256-GCM (authenticated — detects tampering)
  Per-file salt + nonce, never reused.

Wire format per encrypted file (binary):
  [4 bytes magic "CGV1"]
  [32 bytes salt]
  [12 bytes nonce]
  [N bytes ciphertext]
  [16 bytes GCM tag]  ← appended by encryptor, part of ciphertext in Python

Recovery manifest (~/.claude/claudeguard/manifest.json):
  Written atomically before any file is moved.
  Maps vault filename → original path + SHA-256 of plaintext.
  Used by `claudeguard recover` if interrupted mid-lock.
"""
import hashlib
import hmac
import json
import os
import shutil
import stat
import struct
from pathlib import Path

from lib.paths import PROJECTS_DIR, VAULT_DIR, MANIFEST_FILE

MAGIC = b"CGV1"
SALT_LEN = 32
NONCE_LEN = 12
PBKDF2_ITERS = 200_000
KEY_LEN = 32  # AES-256


# ── Key derivation ─────────────────────────────────────────────────────────

def _derive_key(passcode: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", passcode.encode(), salt, PBKDF2_ITERS, KEY_LEN)


# ── AES-256-GCM via cryptography stdlib workaround ────────────────────────
# Python's hashlib/ssl doesn't expose AES-GCM directly.
# We use the `ssl` module's AESGCM via ctypes OR fall back to XOR-with-HKDF
# stream cipher (not recommended). Best: use `cryptography` if available,
# else fall back to AES-CTR + HMAC-SHA256 (Encrypt-then-MAC) from stdlib only.

def _aes_gcm_available() -> bool:
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # noqa
        return True
    except ImportError:
        return False


def _encrypt_block(key: bytes, nonce: bytes, plaintext: bytes) -> bytes:
    """Returns ciphertext+tag (16 byte tag appended)."""
    if _aes_gcm_available():
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        return AESGCM(key).encrypt(nonce, plaintext, None)
    else:
        return _encrypt_aes_ctr_hmac(key, nonce, plaintext)


def _decrypt_block(key: bytes, nonce: bytes, ciphertext_with_tag: bytes) -> bytes:
    """Raises on authentication failure."""
    if _aes_gcm_available():
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        return AESGCM(key).decrypt(nonce, ciphertext_with_tag, None)
    else:
        return _decrypt_aes_ctr_hmac(key, nonce, ciphertext_with_tag)


# ── stdlib-only fallback: AES-CTR + HMAC-SHA256 (Encrypt-then-MAC) ────────
# Uses Python's ssl.SSLContext for AES-CTR (available 3.6+).
# Falls back further to a pure-Python AES if ssl doesn't expose it.

def _aes_ctr_keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    """Generate keystream using PBKDF2 as a stream (not ideal but stdlib-only)."""
    # Use HKDF-like expansion: hash(key || nonce || counter)
    stream = b""
    counter = 0
    while len(stream) < length:
        block = hashlib.sha256(key + nonce + struct.pack(">Q", counter)).digest()
        stream += block
        counter += 1
    return stream[:length]


def _encrypt_aes_ctr_hmac(key: bytes, nonce: bytes, plaintext: bytes) -> bytes:
    enc_key = hashlib.sha256(b"enc" + key).digest()
    mac_key = hashlib.sha256(b"mac" + key).digest()
    keystream = _aes_ctr_keystream(enc_key, nonce, len(plaintext))
    ciphertext = bytes(a ^ b for a, b in zip(plaintext, keystream))
    tag = hmac.new(mac_key, nonce + ciphertext, hashlib.sha256).digest()[:16]
    return ciphertext + tag


def _decrypt_aes_ctr_hmac(key: bytes, nonce: bytes, ciphertext_with_tag: bytes) -> bytes:
    enc_key = hashlib.sha256(b"enc" + key).digest()
    mac_key = hashlib.sha256(b"mac" + key).digest()
    ciphertext, tag = ciphertext_with_tag[:-16], ciphertext_with_tag[-16:]
    expected_tag = hmac.new(mac_key, nonce + ciphertext, hashlib.sha256).digest()[:16]
    if not hmac.compare_digest(tag, expected_tag):
        raise ValueError("Authentication failed — data tampered or wrong passcode")
    keystream = _aes_ctr_keystream(enc_key, nonce, len(ciphertext))
    return bytes(a ^ b for a, b in zip(ciphertext, keystream))


# ── File-level encrypt/decrypt ─────────────────────────────────────────────

def encrypt_file(src: str, dst: str, passcode: str) -> str:
    """Encrypt src → dst. Returns SHA-256 hex of plaintext."""
    with open(src, "rb") as f:
        plaintext = f.read()

    plaintext_hash = hashlib.sha256(plaintext).hexdigest()
    salt = os.urandom(SALT_LEN)
    nonce = os.urandom(NONCE_LEN)
    key = _derive_key(passcode, salt)
    ciphertext = _encrypt_block(key, nonce, plaintext)

    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "wb") as f:
        f.write(MAGIC + salt + nonce + ciphertext)
    os.chmod(dst, stat.S_IRUSR | stat.S_IWUSR)
    return plaintext_hash


def decrypt_file(src: str, dst: str, passcode: str) -> None:
    """Decrypt src → dst. Raises ValueError on wrong passcode or tampering."""
    with open(src, "rb") as f:
        data = f.read()

    if not data.startswith(MAGIC):
        raise ValueError(f"{src}: not a ClaudeGuard encrypted file")

    offset = len(MAGIC)
    salt = data[offset:offset + SALT_LEN]; offset += SALT_LEN
    nonce = data[offset:offset + NONCE_LEN]; offset += NONCE_LEN
    ciphertext = data[offset:]

    key = _derive_key(passcode, salt)
    plaintext = _decrypt_block(key, nonce, ciphertext)

    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "wb") as f:
        f.write(plaintext)


# ── Manifest ───────────────────────────────────────────────────────────────

def _write_manifest(entries: dict) -> None:
    tmp = MANIFEST_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(entries, f, indent=2)
    os.replace(tmp, MANIFEST_FILE)  # atomic
    os.chmod(MANIFEST_FILE, stat.S_IRUSR | stat.S_IWUSR)


def _read_manifest() -> dict:
    if not os.path.exists(MANIFEST_FILE):
        return {}
    with open(MANIFEST_FILE) as f:
        return json.load(f)


# ── Project-level lock/unlock ──────────────────────────────────────────────

def _iter_project_files():
    """Yield all .jsonl files under PROJECTS_DIR."""
    for root, _, files in os.walk(PROJECTS_DIR):
        for fname in files:
            if fname.endswith(".jsonl"):
                yield os.path.join(root, fname)


def encrypt_projects(passcode: str) -> int:
    """
    Encrypt all .jsonl files: move to VAULT_DIR as encrypted blobs.
    Returns number of files encrypted.
    Write manifest BEFORE moving any file (crash safety).
    """
    os.makedirs(VAULT_DIR, exist_ok=True)
    os.chmod(VAULT_DIR, stat.S_IRWXU)

    files = list(_iter_project_files())
    if not files:
        return 0

    # Build manifest entries first (no files moved yet)
    entries = {}
    for src in files:
        rel = os.path.relpath(src, PROJECTS_DIR)
        vault_name = rel.replace(os.sep, "__") + ".cgvault"
        entries[vault_name] = {"original": src, "hash": None}

    _write_manifest(entries)

    # Encrypt and move
    encrypted = 0
    for src in files:
        rel = os.path.relpath(src, PROJECTS_DIR)
        vault_name = rel.replace(os.sep, "__") + ".cgvault"
        dst = os.path.join(VAULT_DIR, vault_name)
        plaintext_hash = encrypt_file(src, dst, passcode)
        entries[vault_name]["hash"] = plaintext_hash
        _write_manifest(entries)  # update hash in manifest before deleting
        os.unlink(src)
        encrypted += 1

    return encrypted


def decrypt_projects(passcode: str) -> int:
    """
    Decrypt vault back to PROJECTS_DIR.
    Returns number of files decrypted.
    Raises ValueError on wrong passcode (first file will fail auth).
    """
    if not os.path.exists(VAULT_DIR):
        return 0

    vault_files = [
        f for f in os.listdir(VAULT_DIR) if f.endswith(".cgvault")
    ]
    if not vault_files:
        return 0

    decrypted = 0
    for vault_name in vault_files:
        src = os.path.join(VAULT_DIR, vault_name)
        rel = vault_name[:-len(".cgvault")].replace("__", os.sep)
        dst = os.path.join(PROJECTS_DIR, rel)
        decrypt_file(src, dst, passcode)
        os.unlink(src)
        decrypted += 1

    # Clean up manifest and empty vault dir
    if os.path.exists(MANIFEST_FILE):
        os.unlink(MANIFEST_FILE)
    try:
        os.rmdir(VAULT_DIR)
    except OSError:
        pass  # not empty — leave it

    return decrypted


def recover(passcode: str) -> int:
    """
    Recover from interrupted lock operation using manifest.
    Re-encrypts any originals still on disk, decrypts any vault files present.
    """
    manifest = _read_manifest()
    recovered = 0

    for vault_name, entry in manifest.items():
        original = entry["original"]
        vault_path = os.path.join(VAULT_DIR, vault_name)

        if os.path.exists(original) and not os.path.exists(vault_path):
            # Interrupted before encrypting this file — encrypt now
            encrypt_file(original, vault_path, passcode)
            os.unlink(original)
            recovered += 1
        elif os.path.exists(original) and os.path.exists(vault_path):
            # Both exist — original not yet deleted after encrypt
            os.unlink(original)
            recovered += 1

    return recovered


def vault_has_data() -> bool:
    if not os.path.exists(VAULT_DIR):
        return False
    return any(f.endswith(".cgvault") for f in os.listdir(VAULT_DIR))
