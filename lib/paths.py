import os
import stat

HOME = os.path.expanduser("~")
CLAUDEGUARD_DIR = os.path.join(HOME, ".claude", "claudeguard")
HASH_FILE       = os.path.join(CLAUDEGUARD_DIR, "passcode.hash")
STATE_FILE      = os.path.join(CLAUDEGUARD_DIR, "state.json")
CONFIG_FILE     = os.path.join(CLAUDEGUARD_DIR, "config.json")
PROJECTS_DIR    = os.path.join(HOME, ".claude", "projects")
TOKEN_FILE      = os.path.join(CLAUDEGUARD_DIR, "unlock.token")
VAULT_DIR       = os.path.join(CLAUDEGUARD_DIR, "vault")
MANIFEST_FILE   = os.path.join(CLAUDEGUARD_DIR, "manifest.json")

def ensure_dir():
    os.makedirs(CLAUDEGUARD_DIR, exist_ok=True)
    os.chmod(CLAUDEGUARD_DIR, stat.S_IRWXU)  # 0700

ensure_dir()
