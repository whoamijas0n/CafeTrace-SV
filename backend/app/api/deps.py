import uuid
from typing import AsyncGenerator, List
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.security import decode_access_token
from app.db.session import AsyncSessionLocal
from app.models.producer import Producer
from app.models.user import User

# OAuth2 Password Bearer flow endpoint
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    scheme_name="JWT Bearer",
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Yields an asynchronous SQLAlchemy session with automatic commit/rollback.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(oauth2_scheme),
) -> User:
    """
    Validates JWT Bearer token and returns the authenticated User entity.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales de autenticación no válidas o token expirado.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    user_id_str: str = payload.get("sub", "")
    if not user_id_str:
        raise credentials_exception

    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError:
        raise credentials_exception

    stmt = select(User).where(User.id == user_uuid)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta de usuario se encuentra inactiva.",
        )

    return user


async def get_current_producer(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Producer:
    """
    Returns the Producer profile associated with the currently authenticated user.
    """
    stmt = select(Producer).where(Producer.user_id == current_user.id)
    result = await db.execute(stmt)
    producer = result.scalar_one_or_none()

    if producer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El usuario actual no tiene un perfil de productor registrado. Por favor crea uno primero en /api/v1/producers.",
        )

    return producer


def require_role(allowed_roles: List[str]):
    """
    Dependency factory to enforce role-based access control (RBAC).
    """
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permiso denegado. Se requiere uno de los siguientes roles: {', '.join(allowed_roles)}.",
            )
        return current_user

    return role_checker
