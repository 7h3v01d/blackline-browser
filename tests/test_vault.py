"""
Vault encryption, unlock semantics, and durability.

TestWrongPasswordDoesNotDestroyVault covers the P0 from the audit: a wrong
master password used to be indistinguishable from "no vault yet", and the
caller responded by overwriting credentials.vault with an empty one.
"""

import json
import os

import pytest

from vault import Vault, UnlockResult, BACKUP_SUFFIX, SALT_BYTES

SAMPLE = {
    "logins": [
        {"url": "https://example.com", "username": "leon", "password": "hunter2"},
    ],
    "api_keys": [
        {"service": "openai", "key": "sk-test-123"},
    ],
}


@pytest.fixture
def locked_vault(vault_path):
    """A vault on disk holding SAMPLE, master password 'correct horse'."""
    v = Vault("correct horse", path=vault_path)
    v.create_and_lock_vault(dict(SAMPLE))
    return vault_path


# ── round trip ───────────────────────────────────────────────────────────

def test_create_then_unlock_round_trip(locked_vault):
    v = Vault("correct horse", path=locked_vault)
    assert v.unlock_vault() is UnlockResult.OK
    assert v.get_logins() == SAMPLE["logins"]
    assert v.get_api_keys() == SAMPLE["api_keys"]


def test_get_api_key_by_service(locked_vault):
    v = Vault("correct horse", path=locked_vault)
    v.unlock_vault()
    assert v.get_api_key("openai") == "sk-test-123"
    assert v.get_api_key("nonexistent") is None


def test_file_is_not_plaintext(locked_vault):
    raw = open(locked_vault, "rb").read()
    assert b"hunter2" not in raw
    assert b"sk-test-123" not in raw
    assert b"leon" not in raw


def test_salt_is_random_per_vault(tmp_path):
    a = str(tmp_path / "a.vault")
    b = str(tmp_path / "b.vault")
    Vault("same password", path=a).create_and_lock_vault(dict(SAMPLE))
    Vault("same password", path=b).create_and_lock_vault(dict(SAMPLE))
    assert open(a, "rb").read(SALT_BYTES) != open(b, "rb").read(SALT_BYTES)


def test_unicode_password_and_payload(vault_path):
    data = {"logins": [{"url": "https://例え.jp", "username": "ünïcode", "password": "pä$$"}],
            "api_keys": []}
    Vault("pässwörd–ünicode", path=vault_path).create_and_lock_vault(data)
    v = Vault("pässwörd–ünicode", path=vault_path)
    assert v.unlock_vault() is UnlockResult.OK
    assert v.get_logins() == data["logins"]


# ── unlock result states ─────────────────────────────────────────────────

def test_missing_file_reports_no_vault(vault_path):
    assert Vault("anything", path=vault_path).unlock_vault() is UnlockResult.NO_VAULT


def test_wrong_password_reports_wrong_password(locked_vault):
    assert Vault("wrong", path=locked_vault).unlock_vault() is UnlockResult.WRONG_PASSWORD


def test_truncated_file_reports_corrupt(vault_path):
    with open(vault_path, "wb") as f:
        f.write(b"tooshort")
    assert Vault("anything", path=vault_path).unlock_vault() is UnlockResult.CORRUPT


def test_salt_only_file_reports_corrupt(vault_path):
    with open(vault_path, "wb") as f:
        f.write(os.urandom(SALT_BYTES))
    assert Vault("anything", path=vault_path).unlock_vault() is UnlockResult.CORRUPT


def test_tampered_ciphertext_is_detected(locked_vault):
    raw = bytearray(open(locked_vault, "rb").read())
    raw[-1] ^= 0xFF
    open(locked_vault, "wb").write(bytes(raw))
    result = Vault("correct horse", path=locked_vault).unlock_vault()
    assert result in (UnlockResult.WRONG_PASSWORD, UnlockResult.CORRUPT)
    assert result is not UnlockResult.OK


def test_unlock_result_truthiness():
    """Legacy `if not vault.unlock_vault()` call sites must still behave."""
    assert bool(UnlockResult.OK) is True
    assert bool(UnlockResult.NO_VAULT) is False
    assert bool(UnlockResult.WRONG_PASSWORD) is False
    assert bool(UnlockResult.CORRUPT) is False


# ── password verification ────────────────────────────────────────────────

def test_verify_master_password(locked_vault):
    v = Vault("correct horse", path=locked_vault)
    v.unlock_vault()
    assert v.verify_master_password("correct horse") is True
    assert v.verify_master_password("wrong") is False
    assert v.verify_master_password("") is False


def test_verify_fails_before_unlock(locked_vault):
    v = Vault("correct horse", path=locked_vault)
    assert v.verify_master_password("correct horse") is False


def test_master_password_not_retained_as_plaintext_str(locked_vault):
    """The old implementation kept master_password_str on the instance."""
    v = Vault("correct horse", path=locked_vault)
    v.unlock_vault()
    assert not hasattr(v, "master_password_str")
    leaked = [k for k, val in vars(v).items() if val == "correct horse"]
    assert leaked == []


# ── durability ───────────────────────────────────────────────────────────

class TestDurability:

    def test_backup_written_on_overwrite(self, locked_vault):
        original = open(locked_vault, "rb").read()
        v = Vault("correct horse", path=locked_vault)
        v.unlock_vault()
        v.data["logins"].append({"url": "https://new.com", "username": "u", "password": "p"})
        v.create_and_lock_vault()
        assert os.path.exists(locked_vault + BACKUP_SUFFIX)
        assert open(locked_vault + BACKUP_SUFFIX, "rb").read() == original

    def test_backup_still_opens_with_the_password(self, locked_vault):
        v = Vault("correct horse", path=locked_vault)
        v.unlock_vault()
        v.create_and_lock_vault({"logins": [], "api_keys": []})
        backup = Vault("correct horse", path=locked_vault + BACKUP_SUFFIX)
        assert backup.unlock_vault() is UnlockResult.OK
        assert backup.get_logins() == SAMPLE["logins"]

    def test_no_temp_file_left_behind(self, locked_vault):
        v = Vault("correct horse", path=locked_vault)
        v.unlock_vault()
        v.create_and_lock_vault()
        assert not os.path.exists(locked_vault + ".tmp")

    def test_salt_is_stable_across_resaves(self, locked_vault):
        """Re-saving must not reroll the salt, or the backup and live file diverge."""
        v = Vault("correct horse", path=locked_vault)
        v.unlock_vault()
        first = open(locked_vault, "rb").read(SALT_BYTES)
        v.create_and_lock_vault()
        assert open(locked_vault, "rb").read(SALT_BYTES) == first


# ── the P0 regression ────────────────────────────────────────────────────

class TestWrongPasswordDoesNotDestroyVault:
    """
    Shipped bug: unlock_vault() returned False for both "no vault" and
    "wrong password", and browser.py answered False by calling
    create_and_lock_vault(), which opens the file 'wb'. One typo at the
    prompt wiped every credential, silently and unrecoverably.
    """

    def test_failed_unlock_does_not_touch_the_file(self, locked_vault):
        before = open(locked_vault, "rb").read()
        assert Vault("typo", path=locked_vault).unlock_vault() is UnlockResult.WRONG_PASSWORD
        assert open(locked_vault, "rb").read() == before

    def test_data_survives_a_failed_attempt(self, locked_vault):
        Vault("typo", path=locked_vault).unlock_vault()
        Vault("another typo", path=locked_vault).unlock_vault()
        good = Vault("correct horse", path=locked_vault)
        assert good.unlock_vault() is UnlockResult.OK
        assert good.get_logins() == SAMPLE["logins"]

    def test_wrong_password_is_distinguishable_from_no_vault(self, locked_vault, tmp_path):
        """
        The whole fix in one assertion: these two cases must not compare
        equal, because only one of them may lead to a write.
        """
        wrong = Vault("typo", path=locked_vault).unlock_vault()
        absent = Vault("typo", path=str(tmp_path / "nope.vault")).unlock_vault()
        assert wrong is UnlockResult.WRONG_PASSWORD
        assert absent is UnlockResult.NO_VAULT
        assert wrong is not absent

    def test_creating_on_no_vault_is_still_allowed(self, vault_path):
        v = Vault("brand new", path=vault_path)
        assert v.unlock_vault() is UnlockResult.NO_VAULT
        v.create_and_lock_vault({"logins": [], "api_keys": []})
        assert Vault("brand new", path=vault_path).unlock_vault() is UnlockResult.OK
