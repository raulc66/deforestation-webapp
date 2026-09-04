"""Auth routes - /api/auth/*"""
from fastapi import APIRouter, Depends, Response, Request
from app.api.deps import auth_service_dep, get_current_user
from app.core.config import get_settings
from app.core.errors import AuthError
from app.models.user import LoginRequest, RegisterRequest, UserPublic
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _auth_cookie_scope() -> dict:
    """Flags must match on set and clear so cross-site browsers drop the cookie.

    Login, register, and the demonstration session set ``Secure; SameSite=None``.
    Starlette's ``delete_cookie`` defaults to ``Secure=False; SameSite=Lax``, which
    does not overwrite the hosted Netlify → Render cookie.
    """
    return {"httponly": True, "secure": True, "samesite": "none", "path": "/"}


def _set_auth_cookies(resp: Response, access: str, refresh: str) -> None:
    s = get_settings()
    scope = _auth_cookie_scope()
    resp.set_cookie(
        "access_token", access, max_age=s.access_token_minutes * 60, **scope
    )
    resp.set_cookie(
        "refresh_token", refresh, max_age=s.refresh_token_days * 86400, **scope
    )


def _clear_auth_cookies(response: Response) -> None:
    expired = {**_auth_cookie_scope(), "max_age": 0}
    response.set_cookie("access_token", "", expires=0, **expired)
    response.set_cookie("refresh_token", "", expires=0, **expired)


@router.post("/register", response_model=UserPublic)
async def register(
    payload: RegisterRequest,
    response: Response,
    svc: AuthService = Depends(auth_service_dep),
):
    user, access, refresh = await svc.register(payload)
    _set_auth_cookies(response, access, refresh)
    return user


@router.post("/login")
async def login(
    payload: LoginRequest,
    response: Response,
    svc: AuthService = Depends(auth_service_dep),
):
    user, access, refresh = await svc.login(payload)
    _set_auth_cookies(response, access, refresh)
    # access_token is included in the body so Swagger users can copy it into
    # the Authorize dialog.  All UserPublic fields remain at the top level so
    # the browser frontend (setUser(data)) is unaffected.
    return {**user.model_dump(), "access_token": access, "token_type": "bearer"}


@router.post("/logout")
async def logout(response: Response):
    _clear_auth_cookies(response)
    return {"ok": True}


@router.get("/me", response_model=UserPublic)
async def me(user: UserPublic = Depends(get_current_user)):
    return user


@router.post("/refresh")
async def refresh_token(
    request: Request,
    response: Response,
    svc: AuthService = Depends(auth_service_dep),
):
    token = request.cookies.get("refresh_token")
    if not token:
        raise AuthError("Missing refresh token")
    new_access = await svc.refresh_access(token)
    s = get_settings()
    response.set_cookie(
        "access_token",
        new_access,
        max_age=s.access_token_minutes * 60,
        **_auth_cookie_scope(),
    )
    return {"ok": True}
