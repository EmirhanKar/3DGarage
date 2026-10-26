# app/api/deps.py
import os
from fastapi import Depends, HTTPException, status, Security
from fastapi.security import OAuth2PasswordBearer, APIKeyHeader
import jwt
from jwt.exceptions import PyJWTError as JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database.db import get_session
from app.database.models import User
from app.core.security import TOKEN

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="users/login")

# Admin endpoint'leri için API Key header
api_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)
worker_key_header = APIKeyHeader(name="X-Worker-Key", auto_error=False)

ADMIN_API_KEY = os.getenv("ADMIN_API_KEY")
WORKER_API_KEY = os.getenv("WORKER_API_KEY") or ADMIN_API_KEY


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_session)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Kimlik bilgileri doğrulanamadı",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, TOKEN, algorithms=["HS256"])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.user_id == int(user_id)))
    user = result.scalars().first()

    if user is None:
        raise credentials_exception

    return user


async def get_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Sadece is_admin=True olan kullanıcılar geçebilir."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu işlem için admin yetkisi gerekiyor."
        )
    return current_user


async def get_admin_api_key(
    api_key: str = Security(api_key_header)
) -> str:
    """
    Admin seviyesindeki dış sistemler için API Key doğrulama.
    Header: X-Admin-Key: <key>
    """
    if not api_key or api_key != ADMIN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Geçersiz veya eksik Admin API Key."
        )
    return api_key


async def get_worker_api_key(
    worker_key: str = Security(worker_key_header),
    admin_key: str = Security(api_key_header),
) -> str:
    """
    3D/AI işçi servisleri için API Key doğrulama.
    Header: X-Worker-Key veya X-Admin-Key kabul eder.
    """
    valid_key = worker_key or admin_key
    expected_keys = {k for k in (WORKER_API_KEY, ADMIN_API_KEY) if k}
    if not valid_key or valid_key not in expected_keys:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Geçersiz veya eksik Worker/Admin API Key."
        )
    return valid_key
