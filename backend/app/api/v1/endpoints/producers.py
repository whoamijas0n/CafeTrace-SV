import uuid
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, get_db
from app.models.producer import Producer
from app.models.user import User
from app.schemas.producer import ProducerCreate, ProducerOut, ProducerUpdate

router = APIRouter()


@router.post(
    "",
    response_model=ProducerOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear perfil de productor",
    description="Asocia un perfil de productor al usuario autenticado.",
)
async def create_producer_profile(
    producer_in: ProducerCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Create a new producer profile for the authenticated user.
    """
    # Check if user already has a producer profile
    stmt = select(Producer).where(Producer.user_id == current_user.id)
    result = await db.execute(stmt)
    existing_producer = result.scalar_one_or_none()

    if existing_producer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuario ya cuenta con un perfil de productor registrado.",
        )

    producer = Producer(
        user_id=current_user.id,
        document_id=producer_in.document_id,
        phone=producer_in.phone,
        department=producer_in.department,
        municipality=producer_in.municipality,
    )

    db.add(producer)
    await db.flush()
    await db.refresh(producer)

    return producer


@router.get(
    "/me",
    response_model=ProducerOut,
    status_code=status.HTTP_200_OK,
    summary="Obtener perfil de productor del usuario actual",
    description="Retorna la información del productor vinculada al usuario autenticado.",
)
async def get_my_producer_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Get current logged in user's producer profile.
    """
    stmt = select(Producer).where(Producer.user_id == current_user.id)
    result = await db.execute(stmt)
    producer = result.scalar_one_or_none()

    if not producer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró un perfil de productor asociado a este usuario.",
        )

    return producer


@router.put(
    "/me",
    response_model=ProducerOut,
    status_code=status.HTTP_200_OK,
    summary="Actualizar perfil de productor del usuario actual",
    description="Actualiza los datos del perfil de productor del usuario autenticado.",
)
async def update_my_producer_profile(
    producer_in: ProducerUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Update current logged in user's producer profile.
    """
    stmt = select(Producer).where(Producer.user_id == current_user.id)
    result = await db.execute(stmt)
    producer = result.scalar_one_or_none()

    if not producer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró un perfil de productor asociado a este usuario.",
        )

    update_data = producer_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(producer, field, value)

    await db.flush()
    await db.refresh(producer)

    return producer


@router.get(
    "/{producer_id}",
    response_model=ProducerOut,
    status_code=status.HTTP_200_OK,
    summary="Obtener perfil de productor por ID",
    description="Retorna la información de un productor específico (para administradores y técnicos).",
)
async def get_producer_by_id(
    producer_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Get producer profile by ID.
    """
    stmt = select(Producer).where(Producer.id == producer_id)
    result = await db.execute(stmt)
    producer = result.scalar_one_or_none()

    if not producer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Productor no encontrado.",
        )

    # Permission check: own profile or ADMIN/TECNICO
    if producer.user_id != current_user.id and current_user.role not in ["ADMIN", "TECNICO"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para ver este perfil de productor.",
        )

    return producer
