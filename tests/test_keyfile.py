"""Phase 2 — keyfile envelope (DB unlock, multi-user, recovery)."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.crypto import keyfile


@pytest.fixture
def kf(tmp_path: Path) -> Path:
    return tmp_path / "khata.keys"


def test_create_and_unlock(kf: Path):
    master = keyfile.create_keyfile(kf, "Admin", "s3cret")
    assert len(master) == keyfile.MASTER_KEY_BYTES
    assert kf.exists()
    assert keyfile.unlock(kf, "admin", "s3cret") == master  # username case-insensitive


def test_wrong_password_rejected(kf: Path):
    keyfile.create_keyfile(kf, "admin", "right")
    with pytest.raises(keyfile.BadPassword):
        keyfile.unlock(kf, "admin", "wrong")


def test_unknown_user_rejected(kf: Path):
    keyfile.create_keyfile(kf, "admin", "pw")
    with pytest.raises(keyfile.UnknownUser):
        keyfile.unlock(kf, "ghost", "pw")


def test_create_twice_fails(kf: Path):
    keyfile.create_keyfile(kf, "admin", "pw")
    with pytest.raises(keyfile.KeyfileExists):
        keyfile.create_keyfile(kf, "admin", "pw")


def test_second_user_unlocks_same_master_key(kf: Path):
    master = keyfile.create_keyfile(kf, "admin", "adminpw")
    keyfile.add_or_update_user(kf, master, "ramesh", "rameshpw")
    assert keyfile.unlock(kf, "ramesh", "rameshpw") == master
    assert keyfile.unlock(kf, "admin", "adminpw") == master


def test_password_reset_keeps_master_key(kf: Path):
    """Admin recovery path: reset another user's password without rekeying the DB."""
    master = keyfile.create_keyfile(kf, "admin", "adminpw")
    keyfile.add_or_update_user(kf, master, "ramesh", "oldpw")

    # Admin (holding master key) resets ramesh's password.
    keyfile.add_or_update_user(kf, master, "ramesh", "newpw")

    with pytest.raises(keyfile.BadPassword):
        keyfile.unlock(kf, "ramesh", "oldpw")
    assert keyfile.unlock(kf, "ramesh", "newpw") == master


def test_remove_user(kf: Path):
    master = keyfile.create_keyfile(kf, "admin", "pw")
    keyfile.add_or_update_user(kf, master, "ramesh", "pw2")
    keyfile.remove_user(kf, "ramesh")
    assert not keyfile.has_user(kf, "ramesh")
    with pytest.raises(keyfile.UnknownUser):
        keyfile.unlock(kf, "ramesh", "pw2")
