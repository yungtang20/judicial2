from __future__ import annotations

import os
from app.accounts import AccountStore


def test_registration_requires_invite_and_persists_only_single_hashed_account(tmp_path):
    path = tmp_path / "accounts.sqlite3"
    store = AccountStore(path)
    password = "correct-horse-battery-staple"
    invite = "secret-invite-for-account-test-32chars"

    assert not store.register("owner", password, "wrong", invite)
    assert not store.has_account()
    assert not store.register("bad name", password, invite, invite)
    assert not store.register("owner", "short", invite, invite)
    assert store.register("owner", password, invite, invite)
    assert not store.register("another", password, invite, invite)

    reopened = AccountStore(path)
    assert reopened.authenticate("owner", password)
    assert not reopened.authenticate("owner", "incorrect-password")
    assert not reopened.authenticate("another", password)
    assert not reopened.authenticate("owner", password + "x" * 300)
    if os.name != "nt":
        assert path.stat().st_mode & 0o777 == 0o600
