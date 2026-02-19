"""
Auth0 JWT validation for Fulcrum AI backend.
Validates Bearer tokens using Auth0's JWKS (RS256).
"""
import os
import jwt
from jwt import PyJWKClient
from functools import wraps
from flask import g, request

AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE")
AUTH0_ISSUER_BASE_URL = os.getenv("AUTH0_ISSUER_BASE_URL") or (
    f"https://{os.getenv('AUTH0_DOMAIN')}" if os.getenv("AUTH0_DOMAIN") else None
)

# Auth0 issuer in tokens is typically base URL with trailing slash
AUTH0_ISSUER = AUTH0_ISSUER_BASE_URL.rstrip("/") + "/" if AUTH0_ISSUER_BASE_URL else None
IS_CONFIGURED = bool(AUTH0_AUDIENCE and AUTH0_ISSUER_BASE_URL)

if not IS_CONFIGURED:
    import warnings
    warnings.warn(
        "Auth0 not configured: set AUTH0_AUDIENCE and AUTH0_ISSUER_BASE_URL (or AUTH0_DOMAIN). "
        "/api/auth/me will return 503 until then.",
        UserWarning,
    )


class Auth0NotConfiguredError(Exception):
    """Raised when Auth0 env vars are not set."""
    pass


class InvalidTokenError(Exception):
    """Raised when JWT is invalid or expired."""
    def __init__(self, message="Invalid or expired token"):
        self.message = message
        super().__init__(message)


def _get_jwks_client():
    jwks_url = f"{AUTH0_ISSUER_BASE_URL.rstrip('/')}/.well-known/jwks.json"
    return PyJWKClient(jwks_url)


def _verify_token(token: str):
    if not IS_CONFIGURED:
        raise Auth0NotConfiguredError("Auth0 not configured")
    jwks_client = _get_jwks_client()
    signing_key = jwks_client.get_signing_key_from_jwt(token)
    payload = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=AUTH0_AUDIENCE,
        issuer=AUTH0_ISSUER,
    )
    return payload


def require_auth(f):
    """Decorator that validates Auth0 JWT and sets g.auth_payload."""
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not IS_CONFIGURED:
            raise Auth0NotConfiguredError("Auth0 not configured")
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise InvalidTokenError("Missing or invalid Authorization header")
        token = auth_header[7:].strip()
        try:
            g.auth_payload = _verify_token(token)
        except jwt.InvalidTokenError as e:
            raise InvalidTokenError("Invalid or expired token") from e
        return f(*args, **kwargs)
    return wrapped
