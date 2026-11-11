"""Password hashing, JWT handling and the auth dependencies. Forged and malformed tokens must all be 401."""

import base64
import json
from datetime import timedelta
from typing import Annotated
from uuid import uuid4

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from dse.core.auth import AdminOnly, CurrentPrincipal, require_role
from dse.core.errors import install_error_handlers
from dse.core.security import Argon2PasswordHasher, JwtCodec
from dse.features.identity.tests.fakes import FakeClock
from dse.shared_kernel.errors import TooManyRequestsError, UnauthorizedError
from dse.shared_kernel.principal import Principal, Role

SECRET, ISSUER = "a-test-secret-" + "x" * 64, "dse-analyzer"  # >= 64 bytes: no key-length warnings


def codec(clock: FakeClock | None = None, secret: str = SECRET, issuer: str = ISSUER) -> JwtCodec:
    return JwtCodec(secret, issuer, timedelta(minutes=15), clock or FakeClock())


def b64(obj: dict[str, object]) -> str:
    return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()


# ------------------------------------------------------------------------------------- argon2
def test_argon2_hashes_verify_and_never_leak_the_password() -> None:
    h = Argon2PasswordHasher()
    hashed = h.hash("correct horse battery staple")
    assert hashed.startswith("$argon2id$")
    assert "correct horse" not in hashed
    assert hashed != h.hash("correct horse battery staple")  # per-hash random salt
    assert h.verify(hashed, "correct horse battery staple")
    assert not h.verify(hashed, "correct horse battery stapl")
    assert not h.verify("not-a-hash", "whatever")  # a corrupt stored hash fails closed, never raises
    assert not h.verify("", "")
    assert not h.needs_rehash(hashed)


def test_argon2_flags_hashes_made_with_weaker_parameters() -> None:
    from argon2 import PasswordHasher

    weak = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1).hash("x" * 12)
    assert Argon2PasswordHasher().needs_rehash(weak)


# ----------------------------------------------------------------------------------------- jwt
def test_access_token_round_trip() -> None:
    clock, uid = FakeClock(), uuid4()
    token, expires = codec(clock).encode(uid, Role.ADMIN)
    assert expires == clock.now() + timedelta(minutes=15)
    assert codec(clock).decode(token) == Principal(uid, Role.ADMIN)


def test_expiry_uses_the_injected_clock() -> None:
    clock = FakeClock()
    token, _ = codec(clock).encode(uuid4(), Role.USER)
    clock.advance(minutes=14, seconds=59)
    codec(clock).decode(token)
    clock.advance(seconds=1)
    with pytest.raises(UnauthorizedError, match="expired"):
        codec(clock).decode(token)


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(lambda t: t[:-2] + ("AA" if not t.endswith("AA") else "BB"), id="bad-signature"),
        pytest.param(lambda t: t.rsplit(".", 1)[0] + ".", id="signature-stripped"),
        pytest.param(lambda t: "garbage", id="garbage"),
        pytest.param(lambda t: "", id="empty"),
        pytest.param(lambda t: "a.b.c", id="not-base64-json"),
    ],
)
def test_malformed_tokens_are_unauthorized(mutate) -> None:  # type: ignore[no-untyped-def]
    token, _ = codec().encode(uuid4(), Role.USER)
    with pytest.raises(UnauthorizedError):
        codec().decode(mutate(token))


def test_payload_tampering_is_detected() -> None:
    token, _ = codec().encode(uuid4(), Role.USER)
    head, payload, sig = token.split(".")
    claims = json.loads(base64.urlsafe_b64decode(payload + "=="))
    claims["role"] = "admin"  # privilege escalation attempt with the original signature
    with pytest.raises(UnauthorizedError):
        codec().decode(f"{head}.{b64(claims)}.{sig}")


def test_alg_none_and_foreign_algorithms_are_rejected() -> None:
    claims = {"sub": str(uuid4()), "role": "admin", "iss": ISSUER, "iat": 1, "exp": 9_999_999_999, "jti": "x"}
    unsigned = f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64(claims)}."
    with pytest.raises(UnauthorizedError):
        codec().decode(unsigned)
    hs512 = jwt.encode(claims, SECRET, algorithm="HS512")  # right key, algorithm we never issue
    with pytest.raises(UnauthorizedError):
        codec().decode(hs512)


def test_tokens_from_another_key_or_issuer_are_rejected() -> None:
    clock = FakeClock()
    foreign_key, _ = codec(clock, secret="another-secret-" + "y" * 64).encode(uuid4(), Role.USER)
    foreign_iss, _ = codec(clock, issuer="someone-else").encode(uuid4(), Role.USER)
    for t in (foreign_key, foreign_iss):
        with pytest.raises(UnauthorizedError):
            codec(clock).decode(t)


def test_tokens_missing_required_claims_or_with_bad_values_are_rejected() -> None:
    base = {"sub": str(uuid4()), "role": "user", "iss": ISSUER, "iat": 1, "exp": 9_999_999_999, "jti": "x"}
    for broken in (
        {k: v for k, v in base.items() if k != "exp"},
        {k: v for k, v in base.items() if k != "sub"},
        {**base, "sub": "not-a-uuid"},
        {**base, "role": "superuser"},
    ):
        with pytest.raises(UnauthorizedError):
            codec().decode(jwt.encode(broken, SECRET, algorithm="HS256"))


# --------------------------------------------------------------------------- dependencies and responses
@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.state.jwt = codec()
    install_error_handlers(app)

    @app.get("/me")
    def me(p: CurrentPrincipal) -> dict[str, str]:
        return {"user": str(p.user_id), "role": p.role.value}

    @app.get("/admin")
    def admin(p: AdminOnly) -> dict[str, str]:
        return {"ok": p.role.value}

    @app.get("/user-area")
    def user_area(_: Annotated[Principal, Depends(require_role(Role.USER))]) -> dict[str, str]:
        return {"ok": "yes"}

    @app.get("/throttled")
    def throttled() -> None:
        raise TooManyRequestsError("slow down", retry_after_s=42)

    return TestClient(app)


def bearer(role: Role) -> dict[str, str]:
    return {"Authorization": f"Bearer {codec().encode(uuid4(), role)[0]}"}


def test_missing_or_non_bearer_credentials_are_401_with_a_challenge(client: TestClient) -> None:
    for headers in (
        {},
        {"Authorization": "Basic abc"},
        {"Authorization": "Bearer "},
        {"Authorization": "Bearer junk"},
    ):
        r = client.get("/me", headers=headers)
        assert r.status_code == 401, headers
        assert r.headers["www-authenticate"] == "Bearer"
        assert r.headers["content-type"] == "application/problem+json"


def test_a_valid_token_authenticates(client: TestClient) -> None:
    r = client.get("/me", headers=bearer(Role.USER))
    assert r.status_code == 200
    assert r.json()["role"] == "user"
    token = bearer(Role.USER)["Authorization"].split(" ", 1)[1]
    assert (
        client.get("/me", headers={"Authorization": f"bearer {token}"}).status_code == 200
    )  # case-insensitive


def test_roles_are_enforced(client: TestClient) -> None:
    assert client.get("/admin").status_code == 401
    forbidden = client.get("/admin", headers=bearer(Role.USER))
    assert forbidden.status_code == 403
    assert forbidden.headers["content-type"] == "application/problem+json"
    assert client.get("/admin", headers=bearer(Role.ADMIN)).status_code == 200
    assert client.get("/user-area", headers=bearer(Role.ADMIN)).status_code == 200  # admins hold every role
    assert client.get("/user-area", headers=bearer(Role.USER)).status_code == 200


def test_throttling_is_429_with_retry_after(client: TestClient) -> None:
    r = client.get("/throttled")
    assert r.status_code == 429
    assert r.headers["retry-after"] == "42"
    assert r.json()["retry_after_s"] == 42
