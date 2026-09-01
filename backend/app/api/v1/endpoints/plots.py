import json
import uuid
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from geoalchemy2.elements import WKBElement
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, get_db
from app.models.farm import Farm
from app.models.plot import Plot
from app.models.producer import Producer
from app.models.user import User
from app.schemas.plot import (
    GeoJSONPolygon,
    PlotCreate,
    PlotFeatureCollectionGeoJSON,
    PlotFeatureGeoJSON,
    PlotFeatureProperties,
    PlotOut,
    PlotUpdate,
)
from app.services.gis_service import (
    calculate_geodesic_area_hectares,
    create_plot_feature_geojson,
    wkb_to_geojson_dict,
)

router = APIRouter()


@router.post(
    "",
    response_model=PlotOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una parcela georreferenciada con polígono PostGIS",
    description="Registra una nueva parcela (tablón), calcula automáticamente el área geodésica en hectáreas mediante PostGIS y almacena el polígono WGS84 (EPSG:4326).",
)
async def create_plot(
    plot_in: PlotCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Create a new spatial plot and compute its surface area in hectares using PostGIS.
    """
    # Verify farm existence and producer ownership
    stmt = (
        select(Farm, Producer)
        .join(Producer, Farm.producer_id == Producer.id)
        .where(Farm.id == plot_in.farm_id)
    )
    result = await db.execute(stmt)
    row = result.first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Finca no encontrada.",
        )

    farm: Farm = row[0]
    producer: Producer = row[1]

    if producer.user_id != current_user.id and current_user.role not in ["ADMIN", "TECNICO"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes autorización para agregar parcelas a esta finca.",
        )

    geojson_dict = plot_in.geojson.model_dump()
    geojson_str = json.dumps(geojson_dict)

    # 1. Calculate geodesic area in hectares using PostGIS
    try:
        area_query = text(
            "SELECT ST_Area(ST_SetSRID(ST_GeomFromGeoJSON(:geom_json), 4326)::geography) / 10000.0 AS area_ha"
        )
        area_res = await db.execute(area_query, {"geom_json": geojson_str})
        area_val = area_res.scalar()
        if area_val is not None:
            area_hectares = round(float(area_val), 4)
        else:
            area_hectares = calculate_geodesic_area_hectares(geojson_dict)
    except Exception:
        # Fallback to Python spherical geodesic calculation
        area_hectares = calculate_geodesic_area_hectares(geojson_dict)

    # 2. Persist plot entity with PostGIS geometry
    new_plot = Plot(
        farm_id=plot_in.farm_id,
        name=plot_in.name,
        coffee_variety=plot_in.coffee_variety,
        area_hectares=area_hectares,
        geometry=func.ST_SetSRID(func.ST_GeomFromGeoJSON(geojson_str), 4326),
    )

    db.add(new_plot)
    await db.flush()
    await db.refresh(new_plot)

    return PlotOut(
        id=new_plot.id,
        farm_id=new_plot.farm_id,
        name=new_plot.name,
        coffee_variety=new_plot.coffee_variety,
        area_hectares=float(new_plot.area_hectares),
        geojson=GeoJSONPolygon.model_validate(geojson_dict),
        created_at=new_plot.created_at,
    )


@router.get(
    "/farm/{farm_id}",
    response_model=List[PlotOut],
    status_code=status.HTTP_200_OK,
    summary="Listar parcelas de una finca",
    description="Retorna todas las parcelas asociadas a una finca con su geometría GeoJSON serializada.",
)
async def list_plots_by_farm(
    farm_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    List all plots for a specific farm with GeoJSON polygon data.
    """
    stmt = (
        select(
            Plot.id,
            Plot.farm_id,
            Plot.name,
            Plot.coffee_variety,
            Plot.area_hectares,
            func.ST_AsGeoJSON(Plot.geometry).label("geojson_str"),
            Plot.created_at,
        )
        .where(Plot.farm_id == farm_id)
        .order_by(Plot.name)
    )

    result = await db.execute(stmt)
    plots = []

    for row in result.all():
        plot_id, farm_id_val, name, variety, area_ha, geojson_raw, created_at = row
        geojson_data = json.loads(geojson_raw) if isinstance(geojson_raw, str) else geojson_raw

        plots.append(
            PlotOut(
                id=plot_id,
                farm_id=farm_id_val,
                name=name,
                coffee_variety=variety,
                area_hectares=float(area_ha),
                geojson=GeoJSONPolygon.model_validate(geojson_data),
                created_at=created_at,
            )
        )

    return plots


@router.get(
    "/{plot_id}",
    response_model=PlotOut,
    status_code=status.HTTP_200_OK,
    summary="Obtener detalle de una parcela",
    description="Retorna los datos de una parcela específica incluyendo su geometría GeoJSON.",
)
async def get_plot(
    plot_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Get a single plot by ID.
    """
    stmt = select(
        Plot.id,
        Plot.farm_id,
        Plot.name,
        Plot.coffee_variety,
        Plot.area_hectares,
        func.ST_AsGeoJSON(Plot.geometry).label("geojson_str"),
        Plot.created_at,
    ).where(Plot.id == plot_id)

    result = await db.execute(stmt)
    row = result.first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parcela no encontrada.",
        )

    p_id, f_id, name, variety, area_ha, geojson_raw, created_at = row
    geojson_data = json.loads(geojson_raw) if isinstance(geojson_raw, str) else geojson_raw

    return PlotOut(
        id=p_id,
        farm_id=f_id,
        name=name,
        coffee_variety=variety,
        area_hectares=float(area_ha),
        geojson=GeoJSONPolygon.model_validate(geojson_data),
        created_at=created_at,
    )


@router.get(
    "/{plot_id}/geojson",
    response_model=PlotFeatureGeoJSON,
    status_code=status.HTTP_200_OK,
    summary="Obtener Feature GeoJSON de una parcela (MapLibre GL)",
    description="Retorna la parcela en formato GeoJSON Feature estándar (RFC 7946) para renderizado cartográfico directo en el visor.",
)
async def get_plot_geojson_feature(
    plot_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Get a single plot as an RFC 7946 GeoJSON Feature for MapLibre GL.
    """
    stmt = (
        select(
            Plot.id,
            Plot.farm_id,
            Plot.name,
            Plot.coffee_variety,
            Plot.area_hectares,
            func.ST_AsGeoJSON(Plot.geometry).label("geojson_str"),
            Plot.created_at,
            Farm.name.label("farm_name"),
            User.full_name.label("producer_name"),
        )
        .join(Farm, Plot.farm_id == Farm.id)
        .join(Producer, Farm.producer_id == Producer.id)
        .join(User, Producer.user_id == User.id)
        .where(Plot.id == plot_id)
    )

    result = await db.execute(stmt)
    row = result.first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parcela no encontrada.",
        )

    p_id, f_id, name, variety, area_ha, geojson_raw, created_at, farm_name, producer_name = row
    geojson_data = json.loads(geojson_raw) if isinstance(geojson_raw, str) else geojson_raw

    feature_dict = create_plot_feature_geojson(
        plot_id=p_id,
        farm_id=f_id,
        farm_name=farm_name,
        producer_name=producer_name,
        variety=variety,
        area_hectares=float(area_ha),
        created_at=created_at,
        geojson_polygon=geojson_data,
    )

    return PlotFeatureGeoJSON.model_validate(feature_dict)


@router.get(
    "/farm/{farm_id}/geojson",
    response_model=PlotFeatureCollectionGeoJSON,
    status_code=status.HTTP_200_OK,
    summary="Obtener FeatureCollection GeoJSON de una finca",
    description="Retorna todas las parcelas de una finca en un GeoJSON FeatureCollection para visualización en capas de mapas.",
)
async def get_farm_plots_geojson_collection(
    farm_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Get all plots belonging to a farm as an RFC 7946 FeatureCollection.
    """
    stmt = (
        select(
            Plot.id,
            Plot.farm_id,
            Plot.name,
            Plot.coffee_variety,
            Plot.area_hectares,
            func.ST_AsGeoJSON(Plot.geometry).label("geojson_str"),
            Plot.created_at,
            Farm.name.label("farm_name"),
            User.full_name.label("producer_name"),
        )
        .join(Farm, Plot.farm_id == Farm.id)
        .join(Producer, Farm.producer_id == Producer.id)
        .join(User, Producer.user_id == User.id)
        .where(Plot.farm_id == farm_id)
        .order_by(Plot.name)
    )

    result = await db.execute(stmt)
    features = []

    for row in result.all():
        p_id, f_id, name, variety, area_ha, geojson_raw, created_at, farm_name, producer_name = row
        geojson_data = json.loads(geojson_raw) if isinstance(geojson_raw, str) else geojson_raw

        feature_dict = create_plot_feature_geojson(
            plot_id=p_id,
            farm_id=f_id,
            farm_name=farm_name,
            producer_name=producer_name,
            variety=variety,
            area_hectares=float(area_ha),
            created_at=created_at,
            geojson_polygon=geojson_data,
        )
        features.append(PlotFeatureGeoJSON.model_validate(feature_dict))

    return PlotFeatureCollectionGeoJSON(
        type="FeatureCollection",
        features=features,
    )


@router.delete(
    "/{plot_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar una parcela",
    description="Elimina una parcela y su geometría asociada.",
)
async def delete_plot(
    plot_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a plot by ID.
    """
    stmt = (
        select(Plot, Producer)
        .join(Farm, Plot.farm_id == Farm.id)
        .join(Producer, Farm.producer_id == Producer.id)
        .where(Plot.id == plot_id)
    )
    result = await db.execute(stmt)
    row = result.first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parcela no encontrada.",
        )

    plot: Plot = row[0]
    producer: Producer = row[1]

    if producer.user_id != current_user.id and current_user.role not in ["ADMIN", "TECNICO"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para eliminar esta parcela.",
        )

    await db.delete(plot)
    await db.flush()
