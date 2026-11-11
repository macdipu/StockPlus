"""HTTP adapter for authentication. The refresh token only ever travels in an HttpOnly cookie scoped to
/auth; the access token is returned in the body and sent back as `Authorization: Bearer`."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from dse.core.auth import CurrentPrincipal
from dse.core.errors import problem
from dse.core.http import envelope
from dse.features.identity.application.dto import IssuedSession
from dse.features.identity.application.use_cases import RefreshRaceError
from dse.features.identity.presentation.dependencies import IdentityContainer, container
from dse.shared_kernel.errors import UnauthorizedError

router = APIRouter(prefix="/auth", tags=["auth"])
Container = Annotated[IdentityContainer, Depends(container)]


class Credentials(BaseModel):
    email: str = Field(max_length=254, examples=["trader@example.com"])
    password: str = Field(max_length=256, repr=False)  # bound input size; the domain enforces the policy


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"  # tokens must never sit in a shared cache
    response.headers["Pragma"] = "no-cache"


def _set_refresh_cookie(response: Response, c: IdentityContainer, s: IssuedSession) -> None:
    response.set_cookie(
        key=c.settings.refresh_cookie_name,
        value=s.refresh_secret,
        max_age=c.settings.refresh_token_days * 86_400,
        httponly=True,  # not readable by page scripts, so XSS cannot steal it
        secure=c.cookie_secure,
        samesite="lax",  # not sent on cross-site POSTs: the CSRF defence for this cookie
        path=c.cookie_path,  # only /auth endpoints ever see it
    )


def _session_body(s: IssuedSession) -> dict[str, Any]:
    return envelope(
        {
            "access_token": s.access_token,
            "token_type": "Bearer",
            "expires_at": s.access_expires_at.isoformat(),
            "user": s.user.model_dump(mode="json"),
        }
    )


@router.post("/register", status_code=status.HTTP_201_CREATED, summary="Create an account")
async def register(body: Credentials, c: Container, response: Response) -> dict[str, Any]:
    _no_store(response)
    user = await c.register(body.email, body.password)
    return envelope(user.model_dump(mode="json"))


@router.post("/login", summary="Sign in: access token in the body, refresh token in an HttpOnly cookie")
async def login(body: Credentials, c: Container, response: Response) -> dict[str, Any]:
    _no_store(response)
    session = await c.login(body.email, body.password)
    _set_refresh_cookie(response, c, session)
    return _session_body(session)


@router.post("/refresh", summary="Rotate the refresh cookie and get a new access token", response_model=None)
async def refresh(request: Request, c: Container, response: Response) -> dict[str, Any] | JSONResponse:
    _no_store(response)
    secret = request.cookies.get(c.settings.refresh_cookie_name)
    if not secret:
        raise UnauthorizedError("No refresh cookie.")
    try:
        session = await c.refresh(secret)
    except RefreshRaceError:
        raise  # keep the cookie: a concurrent request already rotated it
    except UnauthorizedError as e:
        # A dead token: clear the cookie. The Set-Cookie must ride on the error response itself, because
        # headers set on the injected `response` are discarded when a handler raises.
        rejected = problem(
            request,
            401,
            "Unauthorized",
            e.detail,
            {"WWW-Authenticate": "Bearer", "Cache-Control": "no-store"},
        )
        rejected.delete_cookie(c.settings.refresh_cookie_name, path=c.cookie_path)
        return rejected
    _set_refresh_cookie(response, c, session)
    return _session_body(session)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Revoke this session")
async def logout(request: Request, c: Container, response: Response) -> None:
    _no_store(response)
    await c.logout(request.cookies.get(c.settings.refresh_cookie_name))
    response.delete_cookie(c.settings.refresh_cookie_name, path=c.cookie_path)


@router.get("/me", summary="The signed-in user")
async def me(principal: CurrentPrincipal, c: Container, response: Response) -> dict[str, Any]:
    _no_store(response)
    return envelope((await c.current_user(principal.user_id)).model_dump(mode="json"))
