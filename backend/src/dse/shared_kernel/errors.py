"""Domain/application error vocabulary. Pure: no HTTP. `dse.core.errors` maps these to responses."""

from typing import Any


class DomainError(Exception):
    def __init__(self, detail: str | None = None, **extra: Any) -> None:
        super().__init__(detail or type(self).__name__)
        self.detail = detail
        self.extra = extra


class ValidationFailedError(DomainError):
    """The caller sent something invalid."""


class NotFoundError(DomainError):
    """The requested thing does not exist."""


class ConflictError(DomainError):
    """The request conflicts with current state."""


class UnauthorizedError(DomainError):
    """No or invalid credentials."""


class ForbiddenError(DomainError):
    """Authenticated, but not allowed."""


class UpstreamUnavailableError(DomainError):
    """An external system (www.dse.com.bd) failed or changed shape."""


class ServiceNotReadyError(DomainError):
    """A dependency or materialised view is not available yet."""
