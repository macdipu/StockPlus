"""Password hashing (argon2id) and access-token encode/decode (JWT, HS256). No business rules here.

Expiry is checked against an injected Clock so tests are deterministic.
"""

import secrets
from datetime import datetime, timedelta
from uuid import UUID

import jwt
from argon2 import PasswordHasher as _Argon2
from argon2.exceptions import InvalidHashError, VerificationError

from dse.shared_kernel.clock import Clock
from dse.shared_kernel.errors import UnauthorizedError
from dse.shared_kernel.principal import Principal, Role

ALGORITHM = "HS256"
REQUIRED = ["sub", "exp", "iat", "iss", "role", "jti"]


class Argon2PasswordHasher:
    """argon2id with the library's current recommended parameters (RFC 9106 low-memory profile)."""

    def __init__(self) -> None:
        self._h = _Argon2()

    def hash(self, password: str) -> str:
        return self._h.hash(password)

    def verify(self, password_hash: str, password: str) -> bool:
        try:
            return self._h.verify(password_hash, password)
        except (VerificationError, InvalidHashError):
            return False

    def needs_rehash(self, password_hash: str) -> bool:
        return self._h.check_needs_rehash(password_hash)


class JwtCodec:
    def __init__(self, secret: str, issuer: str, ttl: timedelta, clock: Clock) -> None:
        self._secret, self._issuer, self._ttl, self._clock = secret, issuer, ttl, clock

    def encode(self, user_id: UUID, role: Role) -> tuple[str, datetime]:
        now = self._clock.now()
        expires = now + self._ttl
        token = jwt.encode(
            {
                "sub": str(user_id),
                "role": role.value,
                "iss": self._issuer,
                "iat": int(now.timestamp()),
                "exp": int(expires.timestamp()),
                "jti": secrets.token_hex(8),
            },
            self._secret,
            algorithm=ALGORITHM,
        )
        return token, expires

    def decode(self, token: str) -> Principal:
        """Raises UnauthorizedError for anything that is not a valid, unexpired token we issued."""
        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=[ALGORITHM],  # never trust the header's alg (blocks alg=none and key confusion)
                issuer=self._issuer,
                options={"require": REQUIRED, "verify_exp": False, "verify_iat": False},
            )
            if int(claims["exp"]) <= int(self._clock.now().timestamp()):
                raise UnauthorizedError("Access token expired.")
            return Principal(UUID(claims["sub"]), Role(claims["role"]))
        except UnauthorizedError:
            raise
        except (jwt.PyJWTError, ValueError, KeyError) as e:
            raise UnauthorizedError("Invalid access token.") from e
