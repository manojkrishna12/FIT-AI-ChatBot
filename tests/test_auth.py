"""Auth validation logic that runs without a database."""

from __future__ import annotations

import auth


def test_normalize_username():
    assert auth.normalize_username("  Manoj_123!  ") == "manoj_123"
    assert auth.normalize_username("UPPER Case") == "upper-case"


def test_validate_username_rules():
    assert auth.validate_username("ab") is not None  # too short
    assert auth.validate_username("ok-name_1") is None
    assert auth.validate_username("-leads-dash") is not None  # must start alnum


def test_register_rejects_weak_password():
    ok, message = auth.register_user("pwcheck", "short")
    assert ok is False
    assert "8 characters" in message


def test_authenticate_fails_closed():
    ok, _ = auth.authenticate("no-such-user-xyz", "whatever")
    assert ok is False
