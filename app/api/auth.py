import os
from typing import Optional
from fastapi import Header, HTTPException, status


def require_api_key(x_api_key: Optional[str] = Header(default=None)):
    expected = os.environ.get("API_KEY", "")
    if not x_api_key or not expected or x_api_key != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")
