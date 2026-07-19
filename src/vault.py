import hmac
import json
import os
import shutil
from base64 import urlsafe_b64encode
from enum import Enum

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

VAULT_FILE = "credentials.vault"
BACKUP_SUFFIX = ".bak"
SALT_BYTES = 16
KDF_ITERATIONS = 100_000


class UnlockResult(Enum):
    """
    Why unlocking succeeded or failed.

    This exists because the old boolean return conflated "no vault yet" with
    "wrong password", and the caller responded to both by creating a fresh
    vault — so a single typo at the prompt silently overwrote every stored
    credential with an empty file. Callers must now distinguish the two.
    """
    OK = "ok"
    NO_VAULT = "no_vault"
    WRONG_PASSWORD = "wrong_password"
    CORRUPT = "corrupt"

    def __bool__(self):
        return self is UnlockResult.OK


class Vault:
    """
    Handles the creation, encryption, and decryption of a secure vault
    for storing passwords and API keys.

    File format (unchanged, so existing vaults still open):
        [16-byte salt][Fernet token]
    """

    def __init__(self, master_password: str, path: str = VAULT_FILE):
        self.path = path
        self.key = None
        self._salt = None
        self._password_bytes = master_password.encode()
        self.data = {"logins": [], "api_keys": []}

    # ── key handling ─────────────────────────────────────────────────────

    def _derive_key(self, salt: bytes, password_bytes: bytes = None) -> bytes:
        # `is None`, not a truthiness check: b"" is falsey, so an empty
        # candidate password silently fell back to the stored one and
        # verify_master_password("") returned True.
        if password_bytes is None:
            password_bytes = self._password_bytes
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=KDF_ITERATIONS,
            backend=default_backend(),
        )
        return urlsafe_b64encode(kdf.derive(password_bytes))

    # ── read ─────────────────────────────────────────────────────────────

    def unlock_vault(self) -> UnlockResult:
        """
        Load and decrypt the vault. Returns an UnlockResult, which is falsey
        for every failure mode so existing `if not vault.unlock_vault()`
        checks keep working — but callers can and should branch on the
        specific reason before writing anything.
        """
        if not os.path.exists(self.path):
            return UnlockResult.NO_VAULT

        try:
            with open(self.path, "rb") as f:
                salt = f.read(SALT_BYTES)
                encrypted = f.read()
        except OSError:
            return UnlockResult.CORRUPT

        if len(salt) < SALT_BYTES or not encrypted:
            return UnlockResult.CORRUPT

        try:
            key = self._derive_key(salt)
            decrypted = Fernet(key).decrypt(encrypted)
        except InvalidToken:
            return UnlockResult.WRONG_PASSWORD
        except Exception:
            return UnlockResult.CORRUPT

        try:
            data = json.loads(decrypted)
        except (ValueError, UnicodeDecodeError):
            return UnlockResult.CORRUPT

        if not isinstance(data, dict):
            return UnlockResult.CORRUPT

        self.key = key
        self._salt = salt
        self.data = {
            "logins": data.get("logins", []),
            "api_keys": data.get("api_keys", []),
        }
        return UnlockResult.OK

    def verify_master_password(self, password_to_check: str) -> bool:
        """
        Verify a password by re-deriving the key rather than comparing
        plaintext. Uses a constant-time compare so the check does not leak
        timing information.
        """
        if self._salt is None or self.key is None:
            return False
        candidate = self._derive_key(self._salt, password_to_check.encode())
        return hmac.compare_digest(candidate, self.key)

    # ── write ────────────────────────────────────────────────────────────

    def create_and_lock_vault(self, data: dict = None):
        """
        Encrypt and persist the vault.

        Written to a temp file and moved into place, so an interrupted write
        cannot truncate the real vault. Any existing vault is copied to
        <path>.bak first.
        """
        if data is not None:
            self.data = data

        salt = self._salt or os.urandom(SALT_BYTES)
        key = self._derive_key(salt)
        token = Fernet(key).encrypt(json.dumps(self.data).encode())

        if os.path.exists(self.path):
            try:
                shutil.copy2(self.path, self.path + BACKUP_SUFFIX)
            except OSError:
                pass

        tmp = self.path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(salt)
            f.write(token)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)

        self.key = key
        self._salt = salt

    # ── accessors ────────────────────────────────────────────────────────

    def get_logins(self):
        return self.data.get("logins", [])

    def get_api_keys(self):
        return self.data.get("api_keys", [])

    def get_api_key(self, service_name: str):
        for key_info in self.get_api_keys():
            if key_info.get("service") == service_name:
                return key_info.get("key")
        return None
