"""Auth session cookies must set and clear with the same cross-site flags."""
from __future__ import annotations

import os

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "forestwatch_auth_cookie_test")
os.environ.setdefault("JWT_SECRET", "auth-cookie-test-secret-32-bytes-min")

from starlette.responses import Response

from app.api.auth_routes import _auth_cookie_scope, _clear_auth_cookies


def _set_cookie_headers(response: Response) -> list[str]:
    return response.headers.getlist("set-cookie")


class TestAuthCookieClearing:
    def test_clear_flags_match_cross_site_session_cookies(self):
        scope = _auth_cookie_scope()
        assert scope["secure"] is True
        assert scope["httponly"] is True
        assert scope["samesite"] == "none"
        assert scope["path"] == "/"

        response = Response()
        _clear_auth_cookies(response)
        headers = _set_cookie_headers(response)
        assert len(headers) == 2
        names = {header.split("=", 1)[0] for header in headers}
        assert names == {"access_token", "refresh_token"}
        for header in headers:
            lowered = header.lower()
            assert "secure" in lowered
            assert "httponly" in lowered
            assert "samesite=none" in lowered
            assert "max-age=0" in lowered
            assert "path=/" in lowered
