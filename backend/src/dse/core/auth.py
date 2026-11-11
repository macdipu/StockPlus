"""FastAPI dependencies that authenticate and authorise a request. Features import these, never each other."""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request

from dse.core.security import JwtCodec
from dse.shared_kernel.errors import ForbiddenError, UnauthorizedError
from dse.shared_kernel.principal import Principal, Role


def current_principal(request: Request) -> Principal:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise UnauthorizedError("Missing bearer token.")
    codec: JwtCodec = request.app.state.jwt
    return codec.decode(token.strip())


CurrentPrincipal = Annotated[Principal, Depends(current_principal)]


def require_role(role: Role) -> Callable[[Principal], Principal]:
    """Dependency factory: the caller must hold `role` (admins hold every role)."""

    def check(principal: CurrentPrincipal) -> Principal:
        if principal.role is not role and not principal.is_admin:
            raise ForbiddenError(f"This action needs the '{role.value}' role.")
        return principal

    return check


AdminOnly = Annotated[Principal, Depends(require_role(Role.ADMIN))]
