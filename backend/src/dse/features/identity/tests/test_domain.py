from dataclasses import replace
from datetime import timedelta
from uuid import uuid4

import pytest

from dse.features.identity.domain.entities import (
    Email,
    RefreshToken,
    hash_refresh_secret,
    new_refresh_secret,
    validate_password,
)
from dse.features.identity.tests.fakes import NOW
from dse.shared_kernel.errors import ValidationFailedError
from dse.shared_kernel.principal import Principal, Role


def test_email_is_normalised_and_validated() -> None:
    assert Email("  Trader@Example.COM ").value == "trader@example.com"
    assert Email("a@b.co") == Email("A@B.CO")
    for bad in ("", "no-at-sign", "a@b", "a b@c.com", "@x.com", "a@@b.com", "x" * 250 + "@a.com", "a@b.c"):
        with pytest.raises(ValidationFailedError):
            Email(bad)


@pytest.mark.parametrize(
    ("password", "message"),
    [
        ("short1", "at least 10"),
        ("x" * 129, "at most 128"),
        ("trader@example.com", "email"),
        ("my-trader-pass", "email"),  # contains the local part (>= 6 chars)
        ("aaaaaaaaaaaa", "repetitive"),
        ("abababababab", "repetitive"),
    ],
)
def test_password_policy_rejects(password: str, message: str) -> None:
    with pytest.raises(ValidationFailedError, match=message):
        validate_password(password, Email("trader@example.com"), 10)


def test_password_policy_accepts_long_passphrases_and_unicode() -> None:
    mail = Email("trader@example.com")
    for ok in ("correct horse battery staple", "pässwörd-with-ünicode-9", "0123456789ab!"):
        validate_password(ok, mail, 10)
    validate_password("short-but-ok", mail, 8)  # the minimum is configurable


def test_refresh_secrets_are_random_and_only_their_hash_is_stored() -> None:
    a, b = new_refresh_secret(), new_refresh_secret()
    assert a != b
    assert len(a) >= 43  # 256 bits, url-safe base64
    h = hash_refresh_secret(a)
    assert h == hash_refresh_secret(a)
    assert len(h) == 64
    assert a not in h


def test_refresh_token_lifecycle_rules() -> None:
    t = RefreshToken(uuid4(), uuid4(), uuid4(), "h", NOW, NOW + timedelta(days=14))
    assert not t.is_expired(NOW + timedelta(days=13))
    assert t.is_expired(NOW + timedelta(days=14))
    assert not t.is_revoked()
    nxt = uuid4()
    spent = t.revoked(NOW, nxt)
    assert spent.is_revoked()
    assert spent.replaced_by == nxt
    grace = timedelta(seconds=10)
    assert spent.recently_rotated(NOW + timedelta(seconds=5), grace)
    assert not spent.recently_rotated(NOW + timedelta(seconds=11), grace)
    killed = t.revoked(NOW)  # revoked by logout/theft handling: not a rotation
    assert not killed.recently_rotated(NOW, grace)
    assert not replace(t).recently_rotated(NOW, grace)


def test_principal_roles() -> None:
    uid = uuid4()
    assert Principal(uid, Role.ADMIN).is_admin
    assert not Principal(uid, Role.USER).is_admin
