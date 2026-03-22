"""Bearer Token Authentifizierung für die API."""

import hmac

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.app.core.config import settings

security = HTTPBearer()


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """Validiert den Bearer Token gegen den konfigurierten API-Token.

    Gibt den Token zurück wenn gültig, wirft 401 wenn ungültig.
    """
    if not hmac.compare_digest(credentials.credentials, settings.api_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ungültiger API-Token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


async def verify_token_query(
    token: str = Query(..., description="API-Token als Query-Parameter (für SSE/EventSource)"),
) -> str:
    """Validiert den Token als Query-Parameter.

    EventSource kann keine HTTP-Header setzen, daher wird der Token
    als Query-Parameter übergeben.
    """
    if not hmac.compare_digest(token, settings.api_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ungültiger API-Token",
        )
    return token
