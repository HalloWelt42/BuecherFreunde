"""Bearer Token Authentifizierung fuer die API."""

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.app.core.config import settings

security = HTTPBearer()


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """Validiert den Bearer Token gegen den konfigurierten API-Token.

    Gibt den Token zurueck wenn gueltig, wirft 401 wenn ungueltig.
    """
    if credentials.credentials != settings.api_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ungueltiger API-Token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


async def verify_token_query(
    token: str = Query(..., description="API-Token als Query-Parameter (fuer SSE/EventSource)"),
) -> str:
    """Validiert den Token als Query-Parameter.

    EventSource kann keine HTTP-Header setzen, daher wird der Token
    als Query-Parameter uebergeben.
    """
    if token != settings.api_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ungueltiger API-Token",
        )
    return token
