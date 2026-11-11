"""In-memory doubles satisfying the identity ports."""

from dataclasses import replace
from datetime import date, datetime, timedelta
from types import TracebackType
from typing import Any, Self
from uuid import UUID

from dse.core.clock import DHAKA
from dse.features.identity.domain.entities import Email, RefreshToken, User
from dse.shared_kernel.errors import ConflictError, TooManyRequestsError
from dse.shared_kernel.principal import Role

NOW = datetime(2026, 11, 11, 12, 0, tzinfo=DHAKA)


class FakeClock:
    def __init__(self, now: datetime = NOW) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now

    def today(self) -> date:
        return self._now.date()

    def advance(self, **kw: float) -> None:
        self._now += timedelta(**kw)


class FakeHasher:
    """Deterministic and fast; verifies like a real hasher (wrong password → False). Hashes carry a version,
    so bumping `version` simulates strengthened parameters. Counts verifications so tests can prove the
    unknown-email path still does the expensive work."""

    def __init__(self) -> None:
        self.verifies = 0
        self.version = 1

    def hash(self, password: str) -> str:
        return f"h{self.version}${password[::-1]}"

    def verify(self, password_hash: str, password: str) -> bool:
        self.verifies += 1
        return password_hash.split("$", 1)[1] == password[::-1]

    def needs_rehash(self, password_hash: str) -> bool:
        return not password_hash.startswith(f"h{self.version}$")


class FakeTokens:
    def __init__(self, clock: FakeClock) -> None:
        self._clock = clock

    def encode(self, user_id: UUID, role: Role) -> tuple[str, datetime]:
        exp = self._clock.now() + timedelta(minutes=15)
        return f"access:{user_id}:{role.value}", exp


class FakeThrottle:
    def __init__(self, max_failures: int = 5) -> None:
        self.max, self.fails = max_failures, {}  # type: int, dict[str, int]

    async def check(self, email: str) -> None:
        if self.fails.get(email, 0) >= self.max:
            raise TooManyRequestsError("locked", retry_after_s=900)

    async def record_failure(self, email: str) -> None:
        self.fails[email] = self.fails.get(email, 0) + 1

    async def reset(self, email: str) -> None:
        self.fails.pop(email, None)


class Store:
    def __init__(self) -> None:
        self.users: dict[UUID, User] = {}
        self.tokens: dict[UUID, RefreshToken] = {}


class FakeUow:
    def __init__(self, store: Store) -> None:
        self._store = store
        outer = self

        class Users:
            async def get(self, user_id: UUID) -> User | None:
                return store.users.get(user_id)

            async def get_by_email(self, email: Email) -> User | None:
                return next((u for u in store.users.values() if u.email == email), None)

            async def add(self, user: User) -> None:
                if any(u.email == user.email for u in store.users.values()):
                    raise ConflictError("An account with this email already exists.")
                store.users[user.id] = user

            async def update_password_hash(self, user_id: UUID, password_hash: str) -> None:
                store.users[user_id] = replace(store.users[user_id], password_hash=password_hash)

            async def set_role(self, user_id: UUID, role: str) -> None:
                store.users[user_id] = replace(store.users[user_id], role=Role(role))

        class Tokens:
            async def add(self, token: RefreshToken) -> None:
                store.tokens[token.id] = token

            async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
                return next((t for t in store.tokens.values() if t.token_hash == token_hash), None)

            async def mark_rotated(self, token_id: UUID, at: datetime, replaced_by: UUID) -> None:
                store.tokens[token_id] = store.tokens[token_id].revoked(at, replaced_by)

            async def revoke_family(self, family_id: UUID, at: datetime) -> int:
                hit = [t for t in store.tokens.values() if t.family_id == family_id and not t.is_revoked()]
                for t in hit:
                    store.tokens[t.id] = t.revoked(at)
                return len(hit)

            async def revoke_all_for_user(self, user_id: UUID, at: datetime) -> int:
                hit = [t for t in store.tokens.values() if t.user_id == user_id and not t.is_revoked()]
                for t in hit:
                    store.tokens[t.id] = t.revoked(at)
                return len(hit)

        self.users, self.refresh_tokens = Users(), Tokens()
        self.committed: Any = outer  # keeps `outer` referenced for the closures above

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        return None

    async def commit(self) -> None:
        return None
