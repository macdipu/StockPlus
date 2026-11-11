"""Accounts, sessions and user-owned data through the real stack (Postgres dse_test + Redis db 15).

DSE is faked where needed (recorded page / snapshot); every other layer is real: argon2, JWT, cookies,
Postgres constraints, Redis throttle.
"""

import asyncio
import gzip
import json
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from dse.cli import _identity
from dse.core.cache import create_redis
from dse.core.clock import SystemClock
from dse.core.config import Settings, get_settings
from dse.core.db import Database
from dse.features.live_feed.infrastructure.dse_snapshot import parse_live_snapshot
from dse.features.live_feed.infrastructure.redis_adapters import RedisLiveStateStore
from dse.features.market_data.infrastructure.dse_parser import parse_company_page
from dse.features.market_data.presentation.dependencies import MarketDataContainer
from dse.features.market_data.tests.fakes import NOW, FakeSource
from dse.main import create_app
from dse.shared_kernel.symbol import Symbol

pytestmark = pytest.mark.integration
FEATURES = Path(__file__).parents[2] / "src/dse/features"
PASSWORD = "correct horse battery staple"
API = "/api/v1"
COOKIE = "dse_refresh"
TABLES = (
    "users, refresh_tokens, watchlists, saved_scans, instruments, fundamentals, daily_bars, announcements"
)


def uniq(prefix: str = "user") -> str:
    return f"{prefix}-{uuid4().hex[:10]}@example.com"


async def _reset(snapshot: Any | None) -> None:
    db = Database(get_settings().database)
    async with db.engine.begin() as c:
        await c.execute(text(f"TRUNCATE {TABLES} CASCADE"))
    await db.dispose()
    r = create_redis(get_settings().redis)
    await r.flushdb()
    if snapshot is not None:
        await RedisLiveStateStore(r).save_snapshot(snapshot, list(snapshot.quotes.values()), full=True)
    await r.aclose()


async def _sql(statement: str, **params: Any) -> list[Any]:
    db = Database(get_settings().database)
    try:
        async with db.engine.begin() as c:
            res = await c.execute(text(statement), params)
            return list(res.fetchall()) if res.returns_rows else []
    finally:
        await db.dispose()


def sql(statement: str, **params: Any) -> list[Any]:
    return asyncio.run(_sql(statement, **params))


@pytest.fixture(scope="module")
def snapshot() -> Any:
    with gzip.open(FEATURES / "live_feed/tests/fixtures/snapshot.json.gz", "rt") as f:
        return parse_live_snapshot(json.load(f))


@pytest.fixture
def make_app(snapshot: Any) -> Iterator[Callable[..., Any]]:
    """Build isolated app instances (own DB pool, own event loop) over one clean database."""
    asyncio.run(_reset(snapshot))
    stack: list[Any] = []

    @contextmanager
    def factory(**security: Any) -> Iterator[TestClient]:
        base: Settings = get_settings()
        s = base.model_copy(update={"security": base.security.model_copy(update=security)})
        with TestClient(create_app(s)) as c:
            yield c

    yield factory
    asyncio.run(_reset(None))
    del stack


@pytest.fixture
def client(make_app: Callable[..., Any]) -> Iterator[TestClient]:
    with make_app() as c:
        yield c


def register(c: TestClient, email: str, password: str = PASSWORD) -> Any:
    return c.post(f"{API}/auth/register", json={"email": email, "password": password})


def login(c: TestClient, email: str, password: str = PASSWORD) -> Any:
    return c.post(f"{API}/auth/login", json={"email": email, "password": password})


def signed_in(c: TestClient, email: str | None = None) -> dict[str, str]:
    email = email or uniq()
    assert register(c, email).status_code == 201
    r = login(c, email)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


# ============================================================================================ accounts
def test_register_login_me_and_cookie_attributes(client: TestClient) -> None:
    email = uniq()
    r = register(client, email.upper())  # emails are case-insensitive
    assert r.status_code == 201
    user = r.json()["data"]
    assert user["email"] == email
    assert user["role"] == "user"
    assert r.headers["cache-control"] == "no-store"
    assert "password" not in r.text
    assert "$argon2" not in r.text

    r = login(client, email)
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["token_type"] == "Bearer"
    assert body["user"]["email"] == email
    assert COOKIE not in r.text  # the refresh token never appears in the body
    assert r.headers["cache-control"] == "no-store"
    cookie = r.headers["set-cookie"]
    assert cookie.startswith(f"{COOKIE}=")
    for attr in ("HttpOnly", "SameSite=lax", f"Path={API}/auth", f"Max-Age={14 * 86400}"):
        assert attr in cookie, (attr, cookie)
    assert "Secure" not in cookie  # dev/test over http://; production turns it on (see the settings test)

    me = client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["data"]["email"] == email

    (row,) = sql("SELECT password_hash, role FROM users WHERE email = :e", e=email)
    assert row[0].startswith("$argon2id$")
    assert row[1] == "user"
    secret = client.cookies.get(COOKIE)
    assert secret
    (stored,) = sql("SELECT token_hash FROM refresh_tokens")
    assert len(stored[0]) == 64
    assert stored[0] != secret  # only a hash of the refresh token is stored


def test_registration_validation_and_duplicates(client: TestClient) -> None:
    email = uniq()
    assert register(client, email).status_code == 201
    dup = register(client, email.upper())
    assert dup.status_code == 409
    assert dup.headers["content-type"] == "application/problem+json"
    assert register(client, uniq(), "short").status_code == 400
    assert register(client, "not-an-email").status_code == 400
    assert register(client, uniq(), "x" * 300).status_code == 422  # input size is bounded before hashing
    assert client.post(f"{API}/auth/register", json={"email": uniq()}).status_code == 422
    assert len(sql("SELECT 1 FROM users")) == 1


def test_concurrent_registrations_of_one_email_create_exactly_one_account(client: TestClient) -> None:
    email = uniq("race")
    with ThreadPoolExecutor(8) as pool:
        codes = sorted(pool.map(lambda _: register(client, email).status_code, range(8)))
    assert codes.count(201) == 1
    assert set(codes) <= {201, 409}
    assert len(sql("SELECT 1 FROM users WHERE email = :e", e=email)) == 1


def test_bad_credentials_are_uniformly_401(client: TestClient) -> None:
    email = uniq()
    register(client, email)
    seen = set()
    for e, p in ((email, "wrong password!!"), (uniq("ghost"), PASSWORD), ("garbage", PASSWORD)):
        r = login(client, e, p)
        assert r.status_code == 401
        assert r.headers["content-type"] == "application/problem+json"
        assert r.headers["www-authenticate"] == "Bearer"
        seen.add(r.json()["detail"])
    assert seen == {"Invalid email or password."}
    assert COOKIE not in client.cookies


def test_failed_logins_lock_the_email_out(client: TestClient) -> None:
    email = uniq("lock")
    register(client, email)
    for _ in range(5):
        assert login(client, email, "wrong password!!").status_code == 401
    locked = login(client, email, PASSWORD)  # even the correct password is refused during the lockout
    assert locked.status_code == 429
    assert 0 < int(locked.headers["retry-after"]) <= 15 * 60
    assert locked.headers["content-type"] == "application/problem+json"
    assert login(client, uniq("other"), "x").status_code == 401  # other emails are unaffected
    assert not any(email in k for k in create_keys())  # no raw email addresses in Redis keys


def create_keys() -> list[str]:
    async def go() -> list[str]:
        r = create_redis(get_settings().redis)
        try:
            return [k async for k in r.scan_iter("auth:*")]
        finally:
            await r.aclose()

    return asyncio.run(go())


def test_forged_tampered_and_expired_access_tokens_are_401(make_app: Callable[..., Any]) -> None:
    with make_app() as c:
        headers = signed_in(c)
        token = headers["Authorization"].split(" ", 1)[1]
        head, payload, sig = token.split(".")
        for bad in (f"{head}.{payload}.{sig[:-3]}abc", f"{head}.{payload}x.{sig}", "x.y.z", "none"):
            r = c.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {bad}"})
            assert r.status_code == 401, bad
        assert c.get(f"{API}/auth/me").status_code == 401
        assert c.get(f"{API}/auth/me", headers=headers).status_code == 200
    with make_app(access_token_minutes=0) as c:  # tokens are born expired
        h = signed_in(c)
        r = c.get(f"{API}/auth/me", headers=h)
        assert r.status_code == 401
        assert "expired" in r.json()["detail"]


# ======================================================================================== refresh cookie
def test_refresh_rotates_the_cookie(client: TestClient) -> None:
    email = uniq()
    register(client, email)
    login(client, email)
    first = client.cookies.get(COOKIE)
    assert first

    r = client.post(f"{API}/auth/refresh")
    assert r.status_code == 200
    second = client.cookies.get(COOKIE)
    assert second
    assert second != first  # rotated
    assert r.json()["data"]["access_token"]
    assert r.headers["cache-control"] == "no-store"


def test_a_reload_that_aborts_the_refresh_response_does_not_sign_the_user_out(client: TestClient) -> None:
    """The server rotated the cookie but the browser never received it (the page was reloaded mid-request), so
    it presents the spent token again. Within the leeway window that must still work."""
    email = uniq()
    register(client, email)
    login(client, email)
    held = client.cookies.get(COOKIE)  # what the browser will still have after the aborted response
    assert held
    assert client.post(f"{API}/auth/refresh").status_code == 200  # response "lost"

    client.cookies.clear()  # the browser's jar holds exactly one cookie: the spent one
    client.cookies.set(COOKIE, held, path=f"{API}/auth")
    again = client.post(f"{API}/auth/refresh")
    assert again.status_code == 200
    fresh = [c.value for c in client.cookies.jar if c.name == COOKIE and c.value != held]
    assert len(fresh) == 1  # the response carried a new cookie
    client.cookies.clear()
    client.cookies.set(COOKIE, fresh[0], path=f"{API}/auth")
    assert client.post(f"{API}/auth/refresh").status_code == 200
    assert sql("SELECT count(*) FROM refresh_tokens WHERE revoked_at IS NULL") == [(1,)]  # one live token


def test_two_tabs_racing_are_refused_without_losing_the_session(client: TestClient) -> None:
    email = uniq()
    register(client, email)
    login(client, email)
    first = client.cookies.get(COOKIE)
    assert first
    assert client.post(f"{API}/auth/refresh").status_code == 200
    second = client.cookies.get(COOKIE)
    assert second
    assert client.post(f"{API}/auth/refresh").status_code == 200  # tab A really used `second`

    client.cookies.set(COOKIE, first, path=f"{API}/auth")  # tab B still holds the oldest cookie
    race = client.post(f"{API}/auth/refresh")
    assert race.status_code == 401
    assert "just used" in race.json()["detail"]
    assert "set-cookie" not in race.headers  # the newer cookie tab A received must not be cleared
    assert sql("SELECT count(*) FROM refresh_tokens WHERE revoked_at IS NULL") == [
        (1,)
    ]  # the family survived


def test_replaying_a_stolen_refresh_token_kills_the_session(make_app: Callable[..., Any]) -> None:
    with make_app(refresh_reuse_grace_s=0) as c:
        email = uniq()
        register(c, email)
        login(c, email)
        stolen = c.cookies.get(COOKIE)
        assert stolen
        assert c.post(f"{API}/auth/refresh").status_code == 200  # the victim rotates normally
        newest = c.cookies.get(COOKIE)
        assert newest

        c.cookies.set(COOKIE, stolen, path=f"{API}/auth")  # the thief replays the old token
        r = c.post(f"{API}/auth/refresh")
        assert r.status_code == 401
        assert "reuse" in r.json()["detail"]

        c.cookies.set(COOKIE, newest, path=f"{API}/auth")  # …and the victim's newest token is dead as well
        assert c.post(f"{API}/auth/refresh").status_code == 401
        assert sql("SELECT count(*) FROM refresh_tokens WHERE revoked_at IS NULL") == [(0,)]


def test_refresh_without_or_with_a_bogus_cookie_is_401(client: TestClient) -> None:
    assert client.post(f"{API}/auth/refresh").status_code == 401
    client.cookies.set(COOKIE, "not-a-real-token", path=f"{API}/auth")
    r = client.post(f"{API}/auth/refresh")
    assert r.status_code == 401
    assert f"{COOKIE}=" in r.headers["set-cookie"]  # a rejected cookie is cleared


def test_logout_revokes_this_session_only(make_app: Callable[..., Any]) -> None:
    with make_app() as laptop, make_app() as phone:
        email = uniq()
        register(laptop, email)
        login(laptop, email)
        assert login(phone, email).status_code == 200  # same account, another device
        out = laptop.post(f"{API}/auth/logout")
        assert out.status_code == 204
        assert "Max-Age=0" in out.headers["set-cookie"]  # the cookie is cleared
        assert laptop.post(f"{API}/auth/refresh").status_code == 401
        assert phone.post(f"{API}/auth/refresh").status_code == 200  # the other device is unaffected
        assert laptop.post(f"{API}/auth/logout").status_code == 204  # idempotent


def test_cookie_is_secure_in_production_and_the_default_secret_is_refused() -> None:
    base = get_settings()
    assert not base.cookie_secure
    prod = base.model_copy(update={"env": "production"})
    assert prod.cookie_secure
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        prod.assert_production_safe()


# =============================================================================================== roles
@pytest.fixture
def admin_app(make_app: Callable[..., Any]) -> Iterator[TestClient]:
    from argparse import Namespace
    from unittest.mock import patch

    email = uniq("admin")
    with patch("getpass.getpass", return_value=PASSWORD):
        code = asyncio.run(
            _identity(Namespace(cmd="create-user", email=email, role="admin", password_stdin=False))
        )
    assert code == 0
    with make_app() as c:
        with gzip.open(FEATURES / "market_data/tests/fixtures/company_ORIONINFU.html.gz", "rt") as f:
            page = parse_company_page(f.read(), Symbol("ORIONINFU"), NOW)
        c.app.state.market_data = MarketDataContainer(  # type: ignore[attr-defined]
            c.app.state.db,
            FakeSource({"ORIONINFU": page}),
            SystemClock(),  # type: ignore[attr-defined]
        )
        c.admin_email = email  # type: ignore[attr-defined]
        yield c


def test_admin_endpoint_needs_the_admin_role(admin_app: TestClient) -> None:
    url = f"{API}/admin/stocks/ORIONINFU/sync"
    assert admin_app.post(url).status_code == 401
    user = signed_in(admin_app)
    forbidden = admin_app.post(url, headers=user)
    assert forbidden.status_code == 403
    assert forbidden.headers["content-type"] == "application/problem+json"

    r = login(admin_app, admin_app.admin_email)  # type: ignore[attr-defined]
    assert r.json()["data"]["user"]["role"] == "admin"
    ok = admin_app.post(url, headers={"Authorization": f"Bearer {r.json()['data']['access_token']}"})
    assert ok.status_code == 200
    assert ok.json()["data"] == {"symbol": "ORIONINFU", "bars": 260, "announcements": 44}


def test_promoting_a_user_signs_them_out_and_changes_their_role(admin_app: TestClient) -> None:
    from argparse import Namespace

    email = uniq("promoted")
    register(admin_app, email)
    login(admin_app, email)
    assert asyncio.run(_identity(Namespace(cmd="set-role", email=email, role="admin"))) == 0
    assert admin_app.post(f"{API}/auth/refresh").status_code == 401  # old sessions are revoked
    assert login(admin_app, email).json()["data"]["user"]["role"] == "admin"
    assert asyncio.run(_identity(Namespace(cmd="set-role", email="ghost@example.com", role="admin"))) == 1


# ======================================================================================== watchlists
def create_list(c: TestClient, headers: dict[str, str], name: str, symbols: list[str] | None = None) -> Any:
    return c.post(f"{API}/watchlists", headers=headers, json={"name": name, "symbols": symbols or []})


def test_watchlists_require_authentication(client: TestClient) -> None:
    for method, path in (
        ("get", "/watchlists"),
        ("post", "/watchlists"),
        ("get", f"/watchlists/{uuid4()}"),
        ("get", "/saved-scans"),
        ("post", "/saved-scans"),
    ):
        r = client.request(method, API + path)
        assert r.status_code == 401, path
        assert r.headers["content-type"] == "application/problem+json"


def test_watchlist_crud(client: TestClient) -> None:
    h = signed_in(client)
    r = create_list(client, h, "  My   Banks ", ["gp", "BATBC", "GP"])
    assert r.status_code == 201
    wl = r.json()["data"]
    assert (wl["name"], wl["symbols"]) == ("My Banks", ["GP", "BATBC"])
    wid = wl["id"]

    assert client.get(f"{API}/watchlists", headers=h).json()["meta"]["count"] == 1
    assert client.get(f"{API}/watchlists/{wid}", headers=h).json()["data"]["id"] == wid
    assert (
        client.patch(f"{API}/watchlists/{wid}", headers=h, json={"name": "Core"}).json()["data"]["name"]
        == "Core"
    )
    added = client.post(f"{API}/watchlists/{wid}/symbols", headers=h, json={"symbols": ["robi", "GP"]})
    assert added.json()["data"]["symbols"] == ["GP", "BATBC", "ROBI"]
    removed = client.delete(f"{API}/watchlists/{wid}/symbols/batbc", headers=h)
    assert removed.json()["data"]["symbols"] == ["GP", "ROBI"]
    reordered = client.put(f"{API}/watchlists/{wid}/symbols", headers=h, json={"symbols": ["ROBI", "GP"]})
    assert reordered.json()["data"]["symbols"] == ["ROBI", "GP"]

    assert client.delete(f"{API}/watchlists/{wid}", headers=h).status_code == 204
    assert client.get(f"{API}/watchlists/{wid}", headers=h).status_code == 404
    assert client.delete(f"{API}/watchlists/{wid}", headers=h).status_code == 404


def test_watchlist_validation_and_conflicts(client: TestClient, snapshot: Any) -> None:
    h = signed_in(client)
    unknown = create_list(client, h, "Bad", ["GP", "NOTADSECODE"])
    assert unknown.status_code == 400
    assert unknown.json()["unknown"] == ["NOTADSECODE"]
    assert create_list(client, h, "Bad", ["bad symbol!"]).status_code == 400
    assert create_list(client, h, "   ").status_code == 400
    assert create_list(client, h, "x" * 61).status_code == 400
    assert client.get(f"{API}/watchlists", headers=h).json()["meta"]["count"] == 0  # nothing half-created

    assert create_list(client, h, "Core").status_code == 201
    dup = create_list(client, h, "CORE")
    assert dup.status_code == 409
    assert dup.headers["content-type"] == "application/problem+json"

    assert client.get(f"{API}/watchlists/not-a-uuid", headers=h).status_code == 422

    symbols = sorted(snapshot.quotes)[:101]
    full = create_list(client, h, "Full", symbols[:100])
    assert full.status_code == 201
    over = client.post(
        f"{API}/watchlists/{full.json()['data']['id']}/symbols", headers=h, json={"symbols": [symbols[100]]}
    )
    assert over.status_code == 409
    assert "at most 100" in over.json()["detail"]


def test_users_cannot_see_or_touch_each_others_data(make_app: Callable[..., Any]) -> None:
    with make_app() as alice_c, make_app() as bob_c:
        alice, bob = signed_in(alice_c), signed_in(bob_c)
        wid = create_list(alice_c, alice, "Private", ["GP"]).json()["data"]["id"]
        sid = alice_c.post(
            f"{API}/saved-scans",
            headers=alice,
            json={"name": "Mine", "definition": {"rules": [{"field": "rsi14", "op": "<", "value": 30}]}},
        ).json()["data"]["id"]

        assert bob_c.get(f"{API}/watchlists", headers=bob).json()["data"] == []
        assert bob_c.get(f"{API}/saved-scans", headers=bob).json()["data"] == []
        for method, path, body in (
            ("get", f"/watchlists/{wid}", None),
            ("patch", f"/watchlists/{wid}", {"name": "Hijacked"}),
            ("post", f"/watchlists/{wid}/symbols", {"symbols": ["ROBI"]}),
            ("put", f"/watchlists/{wid}/symbols", {"symbols": []}),
            ("delete", f"/watchlists/{wid}/symbols/GP", None),
            ("delete", f"/watchlists/{wid}", None),
            ("get", f"/saved-scans/{sid}", None),
            ("patch", f"/saved-scans/{sid}", {"name": "Hijacked"}),
            ("delete", f"/saved-scans/{sid}", None),
        ):
            r = bob_c.request(method, API + path, headers=bob, json=body)
            assert r.status_code == 404, (method, path)  # not 403: the id's existence is not revealed
        assert create_list(bob_c, bob, "Private").status_code == 201  # the same name is free for Bob

        untouched = alice_c.get(f"{API}/watchlists/{wid}", headers=alice).json()["data"]
        assert (untouched["name"], untouched["symbols"]) == ("Private", ["GP"])
        assert alice_c.get(f"{API}/saved-scans/{sid}", headers=alice).json()["data"]["name"] == "Mine"


def test_saved_scans_are_validated_by_the_scanner_rules(client: TestClient) -> None:
    h = signed_in(client)
    good = {"rules": [{"field": "rsi14", "op": "between", "value": [40, 70]}], "match": "all", "limit": 50}
    r = client.post(f"{API}/saved-scans", headers=h, json={"name": "Momentum", "definition": good})
    assert r.status_code == 201
    sid = r.json()["data"]["id"]
    assert r.json()["data"]["definition"] == good

    for bad in (
        {"rules": []},
        {"rules": [{"field": "a", "op": "nope", "value": 1}]},
        {"rules": [{"field": "a", "op": "<", "value": 1}], "evil": 1},
        {},
    ):
        resp = client.post(f"{API}/saved-scans", headers=h, json={"name": "Bad", "definition": bad})
        assert resp.status_code == 400, bad
        assert resp.headers["content-type"] == "application/problem+json"
    assert (
        client.post(
            f"{API}/saved-scans", headers=h, json={"name": "Huge", "definition": {"rules": ["x" * 9000]}}
        ).status_code
        == 400
    )
    assert (
        client.post(
            f"{API}/saved-scans", headers=h, json={"name": "momentum", "definition": good}
        ).status_code
        == 409
    )

    patched = client.patch(f"{API}/saved-scans/{sid}", headers=h, json={"name": "Momentum v2"})
    assert patched.json()["data"]["name"] == "Momentum v2"
    assert patched.json()["data"]["definition"] == good
    assert (
        client.patch(f"{API}/saved-scans/{sid}", headers=h, json={"definition": {"rules": []}}).status_code
        == 400
    )
    assert client.get(f"{API}/saved-scans", headers=h).json()["meta"]["count"] == 1
    assert client.delete(f"{API}/saved-scans/{sid}", headers=h).status_code == 204
    assert client.get(f"{API}/saved-scans/{sid}", headers=h).status_code == 404


def test_deleting_a_user_cascades_to_their_data_and_sessions(client: TestClient) -> None:
    email = uniq("gone")
    h = signed_in(client, email)
    create_list(client, h, "Doomed", ["GP"])
    client.post(
        f"{API}/saved-scans",
        headers=h,
        json={"name": "S", "definition": {"rules": [{"field": "a", "op": "<", "value": 1}]}},
    )
    assert sql("SELECT count(*) FROM watchlists") == [(1,)]
    sql("DELETE FROM users WHERE email = :e", e=email)
    for table in ("watchlists", "saved_scans", "refresh_tokens"):
        assert sql(f"SELECT count(*) FROM {table}") == [(0,)], table
    assert (
        client.get(f"{API}/auth/me", headers=h).status_code == 401
    )  # a still-valid token for a deleted account


def test_openapi_lists_the_new_routes(client: TestClient) -> None:
    paths = client.get(f"{API}/openapi.json").json()["paths"]
    for p in (
        f"{API}/auth/login",
        f"{API}/auth/refresh",
        f"{API}/watchlists/{{watchlist_id}}/symbols",
        f"{API}/saved-scans",
        f"{API}/admin/stocks/{{symbol}}/sync",
    ):
        assert p in paths, p
