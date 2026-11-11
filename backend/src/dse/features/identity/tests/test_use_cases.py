"""Identity use cases on in-memory fakes: the security-relevant behaviour, case by case."""

from datetime import timedelta

import pytest

from dse.features.identity.application.use_cases import (
    GetCurrentUser,
    Login,
    Logout,
    PromoteUser,
    Refresh,
    Register,
)
from dse.features.identity.domain.entities import hash_refresh_secret
from dse.features.identity.tests.fakes import (
    FakeClock,
    FakeHasher,
    FakeThrottle,
    FakeTokens,
    FakeUow,
    Store,
)
from dse.shared_kernel.errors import (
    ConflictError,
    NotFoundError,
    TooManyRequestsError,
    UnauthorizedError,
    ValidationFailedError,
)
from dse.shared_kernel.principal import Role

EMAIL, PASSWORD = "trader@example.com", "correct horse battery staple"
TTL = timedelta(days=14)


class World:
    def __init__(self, grace_s: int = 10) -> None:
        self.store, self.clock, self.hasher = Store(), FakeClock(), FakeHasher()
        self.throttle, self.tokens = FakeThrottle(5), FakeTokens(self.clock)
        uow = lambda: FakeUow(self.store)  # noqa: E731
        self.register = Register(uow, self.hasher, self.clock, 10)
        self.login = Login(uow, self.hasher, self.throttle, self.tokens, self.clock, TTL)
        self.refresh = Refresh(uow, self.tokens, self.clock, TTL, grace_s)
        self.logout = Logout(uow, self.clock)
        self.me = GetCurrentUser(uow)
        self.promote = PromoteUser(uow, self.clock)


@pytest.fixture
def w() -> World:
    return World()


async def test_register_creates_a_user_account(w: World) -> None:
    u = await w.register("  Trader@Example.com ", PASSWORD)
    assert (u.email, u.role) == (EMAIL, "user")
    stored = next(iter(w.store.users.values()))
    assert stored.password_hash != PASSWORD  # never stored in clear
    assert stored.is_active


async def test_register_rejects_duplicates_weak_passwords_and_bad_emails(w: World) -> None:
    await w.register(EMAIL, PASSWORD)
    with pytest.raises(ConflictError):
        await w.register("TRADER@example.com", "another long password")  # same email, different case
    with pytest.raises(ValidationFailedError):
        await w.register("b@example.com", "short")
    with pytest.raises(ValidationFailedError):
        await w.register("not-an-email", PASSWORD)
    assert len(w.store.users) == 1


async def test_login_issues_access_token_and_a_fresh_refresh_family(w: World) -> None:
    await w.register(EMAIL, PASSWORD)
    s = await w.login(EMAIL, PASSWORD)
    assert s.access_token.startswith("access:")
    assert s.user.email == EMAIL
    assert s.refresh_expires_at == w.clock.now() + TTL
    [t] = w.store.tokens.values()
    assert t.token_hash == hash_refresh_secret(s.refresh_secret)
    assert s.refresh_secret not in {t.token_hash, str(t.id)}  # the secret itself is not persisted
    second = await w.login(EMAIL, PASSWORD)  # another device = another family
    assert len({t.family_id for t in w.store.tokens.values()}) == 2
    assert second.refresh_secret != s.refresh_secret


async def test_login_failures_are_indistinguishable(w: World) -> None:
    await w.register(EMAIL, PASSWORD)
    messages = set()
    for email, pw in ((EMAIL, "wrong password!!"), ("ghost@example.com", PASSWORD), ("garbage", PASSWORD)):
        with pytest.raises(UnauthorizedError) as e:
            await w.login(email, pw)
        messages.add(e.value.detail)
    assert messages == {"Invalid email or password."}


async def test_unknown_email_still_pays_for_a_hash_verification(w: World) -> None:
    """Otherwise response time reveals which emails are registered."""
    await w.register(EMAIL, PASSWORD)
    before = w.hasher.verifies
    with pytest.raises(UnauthorizedError):
        await w.login("ghost@example.com", PASSWORD)
    assert w.hasher.verifies == before + 1
    with pytest.raises(UnauthorizedError):
        await w.login("not an email", PASSWORD)
    assert w.hasher.verifies == before + 2


async def test_inactive_accounts_cannot_log_in(w: World) -> None:
    await w.register(EMAIL, PASSWORD)
    uid = next(iter(w.store.users))
    from dataclasses import replace

    w.store.users[uid] = replace(w.store.users[uid], is_active=False)
    with pytest.raises(UnauthorizedError, match="Invalid email or password"):
        await w.login(EMAIL, PASSWORD)


async def test_repeated_failures_lock_the_email_out_until_a_success_resets_it(w: World) -> None:
    await w.register(EMAIL, PASSWORD)
    for _ in range(4):
        with pytest.raises(UnauthorizedError):
            await w.login(EMAIL, "wrong password!!")
    await w.login(EMAIL, PASSWORD)  # a success before the limit clears the counter
    assert w.throttle.fails == {}
    for _ in range(5):
        with pytest.raises(UnauthorizedError):
            await w.login(EMAIL, "wrong password!!")
    with pytest.raises(TooManyRequestsError) as locked:
        await w.login(EMAIL, PASSWORD)  # even the right password is refused while locked
    assert locked.value.retry_after_s == 900


async def test_login_upgrades_an_outdated_password_hash(w: World) -> None:
    await w.register(EMAIL, PASSWORD)
    assert next(iter(w.store.users.values())).password_hash.startswith("h1$")
    w.hasher.version = 2  # parameters were strengthened after this user signed up
    await w.login(EMAIL, PASSWORD)
    upgraded = next(iter(w.store.users.values())).password_hash
    assert upgraded.startswith("h2$")
    assert w.hasher.verify(upgraded, PASSWORD)  # still the same password
    await w.login(EMAIL, PASSWORD)
    assert next(iter(w.store.users.values())).password_hash == upgraded  # and not rehashed again


# ------------------------------------------------------------------------------------- refresh rotation
async def signed_in(w: World) -> str:
    await w.register(EMAIL, PASSWORD)
    return (await w.login(EMAIL, PASSWORD)).refresh_secret


async def test_refresh_rotates_the_token_within_the_same_family(w: World) -> None:
    first = await signed_in(w)
    s = await w.refresh(first)
    assert s.refresh_secret != first
    assert s.user.email == EMAIL
    old, new = sorted(w.store.tokens.values(), key=lambda t: t.revoked_at is None)
    assert old.is_revoked()
    assert old.replaced_by == new.id
    assert new.family_id == old.family_id
    again = await w.refresh(s.refresh_secret)  # the new one works, and rotates in turn
    assert again.refresh_secret not in {first, s.refresh_secret}


async def test_replaying_a_spent_token_revokes_the_whole_family(w: World) -> None:
    w = World(grace_s=0)
    first = await signed_in(w)
    newest = (await w.refresh(first)).refresh_secret
    w.clock.advance(seconds=1)
    with pytest.raises(UnauthorizedError, match="reuse"):  # an attacker (or the victim) replays the old one
        await w.refresh(first)
    with pytest.raises(UnauthorizedError):  # …and the legitimate newest token is dead too: sign in again
        await w.refresh(newest)
    assert all(t.is_revoked() for t in w.store.tokens.values())


async def test_a_spent_token_is_exchanged_again_within_leeway_when_the_browser_never_got_the_new_one(
    w: World,
) -> None:
    """A reload aborts the response carrying the rotated cookie: the browser still holds the spent token."""
    first = await signed_in(w)
    await w.refresh(first)  # rotated, but the browser never received the new cookie
    w.clock.advance(seconds=3)
    recovered = await w.refresh(first)  # leeway: rotates the unused successor instead of failing
    assert recovered.access_token
    live = [t for t in w.store.tokens.values() if not t.is_revoked()]
    assert len(live) == 1  # the chain stays linear: exactly one usable token, in the same family
    assert (await w.refresh(recovered.refresh_secret)).access_token


async def test_leeway_does_not_cover_a_token_whose_successor_was_really_used(w: World) -> None:
    first = await signed_in(w)
    second = (await w.refresh(first)).refresh_secret
    newest = (await w.refresh(second)).refresh_secret  # the browser did get `second` and used it
    w.clock.advance(seconds=3)
    with pytest.raises(UnauthorizedError, match="just used"):  # two tabs racing: refuse, but do not punish
        await w.refresh(first)
    assert (await w.refresh(newest)).access_token  # the family survived


async def test_a_replay_after_the_leeway_is_reuse_and_kills_the_family(w: World) -> None:
    first = await signed_in(w)
    newest = (await w.refresh(first)).refresh_secret
    w.clock.advance(seconds=30)
    with pytest.raises(UnauthorizedError, match="reuse"):
        await w.refresh(first)
    with pytest.raises(UnauthorizedError):
        await w.refresh(newest)
    assert all(t.is_revoked() for t in w.store.tokens.values())


async def test_refresh_rejects_unknown_expired_and_orphaned_tokens(w: World) -> None:
    first = await signed_in(w)
    with pytest.raises(UnauthorizedError, match="Invalid refresh token"):
        await w.refresh("not-a-real-token")
    w.clock.advance(days=15)
    with pytest.raises(UnauthorizedError, match="expired"):
        await w.refresh(first)


async def test_refresh_for_a_deactivated_user_revokes_the_session(w: World) -> None:
    from dataclasses import replace

    first = await signed_in(w)
    uid = next(iter(w.store.users))
    w.store.users[uid] = replace(w.store.users[uid], is_active=False)
    with pytest.raises(UnauthorizedError, match="not active"):
        await w.refresh(first)
    assert all(t.is_revoked() for t in w.store.tokens.values())


# ------------------------------------------------------------------------------- logout / me / promote
async def test_logout_revokes_the_family_and_is_idempotent(w: World) -> None:
    first = await signed_in(w)
    second = (await w.refresh(first)).refresh_secret
    await w.logout(second)
    with pytest.raises(UnauthorizedError):
        await w.refresh(second)
    await w.logout(second)  # again: fine
    await w.logout(None)
    await w.logout("never-issued")


async def test_logout_affects_only_that_device(w: World) -> None:
    laptop = await signed_in(w)
    phone = (await w.login(EMAIL, PASSWORD)).refresh_secret
    await w.logout(laptop)
    assert (await w.refresh(phone)).access_token


async def test_current_user_and_promotion(w: World) -> None:
    u = await w.register(EMAIL, PASSWORD)
    assert (await w.me(u.id)).email == EMAIL
    first = (await w.login(EMAIL, PASSWORD)).refresh_secret
    promoted = await w.promote(EMAIL, Role.ADMIN)
    assert promoted.role == "admin"
    with pytest.raises(UnauthorizedError):  # promotion signs the user out everywhere to pick up the role
        await w.refresh(first)
    assert (await w.login(EMAIL, PASSWORD)).access_token.endswith(":admin")
    with pytest.raises(NotFoundError):
        await w.promote("ghost@example.com", Role.ADMIN)
    from uuid import uuid4

    with pytest.raises(UnauthorizedError):
        await w.me(uuid4())
