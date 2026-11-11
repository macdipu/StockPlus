"""Identity use cases: register, login, refresh (rotating, with reuse detection), logout, current user."""

import logging
from collections.abc import Callable
from datetime import timedelta
from uuid import UUID, uuid4

from dse.features.identity.application.dto import IssuedSession, UserDto
from dse.features.identity.application.ports import AccessTokens, LoginThrottle, PasswordHasher
from dse.features.identity.domain.entities import (
    Email,
    RefreshToken,
    User,
    hash_refresh_secret,
    new_refresh_secret,
    validate_password,
)
from dse.features.identity.domain.ports import IdentityUnitOfWork
from dse.shared_kernel.clock import Clock
from dse.shared_kernel.errors import ConflictError, NotFoundError, UnauthorizedError
from dse.shared_kernel.principal import Role

log = logging.getLogger("dse.identity")
UowFactory = Callable[[], IdentityUnitOfWork]
INVALID_LOGIN = "Invalid email or password."


class RefreshRaceError(UnauthorizedError):
    """The presented refresh token was spent a moment ago by a concurrent request (e.g. another tab).
    The caller must NOT clear its cookie: the newer one the other request received is still good."""


def user_dto(u: User) -> UserDto:
    return UserDto(id=u.id, email=str(u.email), role=u.role.value, created_at=u.created_at)


class Register:
    def __init__(
        self, uow: UowFactory, hasher: PasswordHasher, clock: Clock, min_password_length: int
    ) -> None:
        self._uow, self._hasher, self._clock, self._min = uow, hasher, clock, min_password_length

    async def __call__(self, email: str, password: str, role: Role = Role.USER) -> UserDto:
        mail = Email(email)
        validate_password(password, mail, self._min)
        user = User(uuid4(), mail, self._hasher.hash(password), role, True, self._clock.now())
        async with self._uow() as uow:
            if await uow.users.get_by_email(mail) is not None:
                raise ConflictError("An account with this email already exists.")
            await uow.users.add(user)  # still raises ConflictError if a concurrent request won the race
            await uow.commit()
        log.info("account created", extra={"user_id": str(user.id), "role": role.value})
        return user_dto(user)


class _Sessions:
    """Shared by Login and Refresh: mint an access token and the next refresh token in a chain."""

    def __init__(self, tokens: AccessTokens, clock: Clock, refresh_ttl: timedelta) -> None:
        self._tokens, self._clock, self._ttl = tokens, clock, refresh_ttl

    def issue(self, user: User, family_id: UUID) -> tuple[IssuedSession, RefreshToken]:
        now = self._clock.now()
        secret = new_refresh_secret()
        token = RefreshToken(
            id=uuid4(),
            user_id=user.id,
            family_id=family_id,
            token_hash=hash_refresh_secret(secret),
            issued_at=now,
            expires_at=now + self._ttl,
        )
        access, access_exp = self._tokens.encode(user.id, user.role)
        return IssuedSession(access, access_exp, secret, token.expires_at, user_dto(user)), token


class Login:
    def __init__(
        self,
        uow: UowFactory,
        hasher: PasswordHasher,
        throttle: LoginThrottle,
        tokens: AccessTokens,
        clock: Clock,
        refresh_ttl: timedelta,
    ) -> None:
        self._uow, self._hasher, self._throttle = uow, hasher, throttle
        self._sessions = _Sessions(tokens, clock, refresh_ttl)
        # Verifying against a real hash when the account does not exist keeps the response time the same,
        # so the endpoint cannot be used to discover which emails are registered.
        self._dummy_hash = hasher.hash("timing-equaliser-not-a-password")

    async def __call__(self, email: str, password: str) -> IssuedSession:
        try:
            mail = Email(email)
        except Exception as e:  # a malformed email can never match; answer like any other failure
            self._hasher.verify(self._dummy_hash, password)
            raise UnauthorizedError(INVALID_LOGIN) from e
        await self._throttle.check(mail.value)
        async with self._uow() as uow:
            user = await uow.users.get_by_email(mail)
            ok = self._hasher.verify(user.password_hash if user else self._dummy_hash, password)
            if user is None or not ok or not user.is_active:
                await self._throttle.record_failure(mail.value)
                raise UnauthorizedError(INVALID_LOGIN)
            await self._throttle.reset(mail.value)
            if self._hasher.needs_rehash(user.password_hash):  # parameters were strengthened since signup
                await uow.users.update_password_hash(user.id, self._hasher.hash(password))
            session, token = self._sessions.issue(user, family_id=uuid4())
            await uow.refresh_tokens.add(token)
            await uow.commit()
        return session


class Refresh:
    """Rotate: the presented refresh token is spent and a new one issued in the same family. A spent token
    shown again means two parties hold it, so the whole family is revoked (theft detection) — unless it was
    spent a moment ago, which is just two browser tabs racing."""

    def __init__(
        self, uow: UowFactory, tokens: AccessTokens, clock: Clock, refresh_ttl: timedelta, grace_s: int
    ):
        self._uow, self._clock, self._grace = uow, clock, timedelta(seconds=grace_s)
        self._sessions = _Sessions(tokens, clock, refresh_ttl)

    async def __call__(self, refresh_secret: str) -> IssuedSession:
        now = self._clock.now()
        async with self._uow() as uow:
            token = await uow.refresh_tokens.get_by_hash(hash_refresh_secret(refresh_secret))
            if token is None:
                raise UnauthorizedError("Invalid refresh token.")
            if token.is_revoked():
                if token.recently_rotated(now, self._grace):
                    raise RefreshRaceError("Refresh token was just used; retry with the newest cookie.")
                n = await uow.refresh_tokens.revoke_family(token.family_id, now)
                await uow.commit()
                log.warning(
                    "refresh token reuse: family revoked",
                    extra={"user_id": str(token.user_id), "family_id": str(token.family_id), "revoked": n},
                )
                raise UnauthorizedError("Refresh token reuse detected; please sign in again.")
            if token.is_expired(now):
                raise UnauthorizedError("Refresh token expired; please sign in again.")
            user = await uow.users.get(token.user_id)
            if user is None or not user.is_active:
                await uow.refresh_tokens.revoke_family(token.family_id, now)
                await uow.commit()
                raise UnauthorizedError("Account is not active.")
            session, nxt = self._sessions.issue(user, token.family_id)
            await uow.refresh_tokens.add(nxt)
            await uow.refresh_tokens.mark_rotated(token.id, now, nxt.id)
            await uow.commit()
        return session


class Logout:
    """Revoke the whole rotation family behind this cookie. Idempotent: unknown tokens are not an error."""

    def __init__(self, uow: UowFactory, clock: Clock) -> None:
        self._uow, self._clock = uow, clock

    async def __call__(self, refresh_secret: str | None) -> None:
        if not refresh_secret:
            return
        async with self._uow() as uow:
            token = await uow.refresh_tokens.get_by_hash(hash_refresh_secret(refresh_secret))
            if token is not None:
                await uow.refresh_tokens.revoke_family(token.family_id, self._clock.now())
                await uow.commit()


class GetCurrentUser:
    def __init__(self, uow: UowFactory) -> None:
        self._uow = uow

    async def __call__(self, user_id: UUID) -> UserDto:
        async with self._uow() as uow:
            user = await uow.users.get(user_id)
        if user is None or not user.is_active:
            raise UnauthorizedError("Account is not active.")
        return user_dto(user)


class PromoteUser:
    """Operator action (CLI): change a user's role."""

    def __init__(self, uow: UowFactory, clock: Clock) -> None:
        self._uow, self._clock = uow, clock

    async def __call__(self, email: str, role: Role) -> UserDto:
        async with self._uow() as uow:
            user = await uow.users.get_by_email(Email(email))
            if user is None:
                raise NotFoundError(f"No account for {email}.")
            await uow.users.set_role(user.id, role.value)
            await uow.refresh_tokens.revoke_all_for_user(
                user.id, self._clock.now()
            )  # re-login picks up the role
            await uow.commit()
        return user_dto(User(user.id, user.email, user.password_hash, role, user.is_active, user.created_at))
