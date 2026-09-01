import uuid
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_producer, get_current_user, get_db
from app.models.farm import Farm
from app.models.plot import Plot
from app.models.producer import Producer
from app.models.user import User
from app.schemas.farm import FarmCreate, FarmOut, FarmUpdate, FarmWithPlotsCountOut

router = APIRouter()


@router.post(
    "",
    response_model=FarmOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar una nueva finca",
    description="Crea una finca asociada al perfil del productor autenticado.",
)
async def create_farm(
    farm_in: FarmCreate,
    producer: Producer = Depends(get_current_producer),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Create a new farm under the authenticated producer.
    """
    new_farm = Farm(
        producer_id=producer.id,
        name=farm_in.name,
        department=farm_in.department,
        municipality=farm_in.municipality,
        canton_village=farm_in.canton_village,
        altitude_masl=farm_in.altitude_masl,
    )

    db.add(new_farm)
    await db.flush()
    await db.refresh(new_farm)

    return new_farm


@router.get(
    "",
    response_model=List[FarmWithPlotsCountOut],
    status_code=status.HTTP_200_OK,
    summary="Listar fincas del productor actual",
    description="Retorna la lista de fincas del productor con conteo de parcelas y superficie total calculada.",
)
async def list_my_farms(
    producer: Producer = Depends(get_current_producer),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    List all farms belonging to the current authenticated producer with aggregate spatial stats.
    """
    # Select farm along with plot count and sum of hectares
    stmt = (
        select(
            Farm,
            func.count(Plot.id).label("plots_count"),
            func.coalesce(func.sum(Plot.area_hectares), 0.0).label("total_area_hectares"),
        )
        .outerjoin(Plot, Farm.id == Plot.farm_id)
        .where(Farm.producer_id == producer.id)
        .group_by(Farm.id)
        .order_by(Farm.name)
    )

    result = await db.execute(stmt)
    farms_with_stats = []

    for row in result.all():
        farm: Farm = row[0]
        plots_count: int = row[1]
        total_area: float = float(row[2])

        farm_data = FarmWithPlotsCountOut(
            id=farm.id,
            producer_id=farm.producer_id,
            name=farm.name,
            department=farm.department,
            municipality=farm.municipality,
            canton_village=farm.canton_village,
            altitude_masl=farm.altitude_masl,
            created_at=farm.created_at,
            plots_count=plots_count,
            total_area_hectares=round(total_area, 4),
        )
        farms_with_stats.append(farm_data)

    return farms_with_stats


@router.get(
    "/{farm_id}",
    response_model=FarmWithPlotsCountOut,
    status_code=status.HTTP_200_OK,
    summary="Obtener detalle de una finca",
    description="Retorna la información detallada de una finca.",
)
async def get_farm(
    farm_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Get detailed farm information by ID.
    """
    stmt = (
        select(
            Farm,
            func.count(Plot.id).label("plots_count"),
            func.coalesce(func.sum(Plot.area_hectares), 0.0).label("total_area_hectares"),
        )
        .outerjoin(Plot, Farm.id == Plot.farm_id)
        .where(Farm.id == farm_id)
        .group_by(Farm.id)
    )

    result = await db.execute(stmt)
    row = result.first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Finca no encontrada.",
        )

    farm: Farm = row[0]
    plots_count: int = row[1]
    total_area: float = float(row[2])

    return FarmWithPlotsCountOut(
        id=farm.id,
        producer_id=farm.producer_id,
        name=farm.name,
        department=farm.department,
        municipality=farm.municipality,
        canton_village=farm.canton_village,
        altitude_masl=farm.altitude_masl,
        created_at=farm.created_at,
        plots_count=plots_count,
        total_area_hectares=round(total_area, 4),
    )


@router.put(
    "/{farm_id}",
    response_model=FarmOut,
    status_code=status.HTTP_200_OK,
    summary="Actualizar información de una finca",
    description="Actualiza los datos de una finca existente.",
)
async def update_farm(
    farm_id: uuid.UUID,
    farm_in: FarmUpdate,
    producer: Producer = Depends(get_current_producer),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Update farm attributes.
    """
    stmt = select(Farm).where(Farm.id == farm_id, Farm.producer_id == producer.id)
    result = await db.execute(stmt)
    farm = result.scalar_one_or_none()

    if not farm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Finca no encontrada o no pertenece al productor autenticado.",
        )

    update_data = farm_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(farm, field, value)

    await db.flush()
    await db.refresh(farm)

    return farm


@router.delete(
    "/{farm_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar una finca",
    description="Elimina la finca y todas sus parcelas asociadas.",
)
async def delete_farm(
    farm_id: uuid.UUID,
    producer: Producer = Depends(get_current_producer),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a farm and cascade deletion to associated plots.
    """
    stmt = select(Farm).where(Farm.id == farm_id, Farm.producer_id == producer.id)
    result = await db.execute(stmt)
    farm = result.scalar_one_or_none()

    if not farm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Finca no encontrada o no pertenece al productor autenticado.",
        )

    await db.delete(farm)
    await db.flush()
