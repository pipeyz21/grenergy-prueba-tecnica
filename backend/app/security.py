from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from .config import get_settings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(key: str | None = Security(_api_key_header)) -> None:
    if key != get_settings().api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
