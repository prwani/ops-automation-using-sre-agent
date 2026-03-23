"""Microsoft Entra ID JWT authentication for FastAPI."""

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from config import settings

security = HTTPBearer()

_jwks_cache: dict | None = None


async def _get_jwks() -> dict:
    global _jwks_cache
    if _jwks_cache is None:
        jwks_url = f"https://login.microsoftonline.com/{settings.azure_tenant_id}/discovery/v2.0/keys"
        async with httpx.AsyncClient() as client:
            resp = await client.get(jwks_url)
            resp.raise_for_status()
            _jwks_cache = resp.json()
    return _jwks_cache


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Validate JWT and return user claims."""
    token = credentials.credentials
    try:
        jwks = await _get_jwks()
        header = jwt.get_unverified_header(token)
        key = next(
            (k for k in jwks["keys"] if k["kid"] == header.get("kid")), None
        )
        if not key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unable to find matching signing key",
            )
        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=f"api://{settings.azure_client_id}",
        )
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
        ) from exc


def require_role(minimum_role: str):
    """Dependency factory: require at least this role."""
    role_order = {"Viewer": 0, "Operator": 1, "Admin": 2}

    async def checker(user: dict = Depends(get_current_user)) -> dict:
        roles = user.get("roles", [])
        user_level = max(
            (role_order.get(r, -1) for r in roles), default=-1
        )
        required_level = role_order.get(minimum_role, 0)
        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{minimum_role}' or higher required",
            )
        return user

    return checker
