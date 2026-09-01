import math
from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator

# Bounding box limits for El Salvador (WGS84 EPSG:4326)
EL_SALVADOR_MIN_LON = -90.25
EL_SALVADOR_MAX_LON = -87.55
EL_SALVADOR_MIN_LAT = 13.10
EL_SALVADOR_MAX_LAT = 14.55


class GeoJSONPolygon(BaseModel):
    """
    Strict GeoJSON Polygon geometry schema adhering to RFC 7946 and El Salvador boundaries.
    Coordinates must be [[[lon, lat], [lon, lat], ...]].
    """
    type: Literal["Polygon"] = "Polygon"
    coordinates: List[List[List[float]]] = Field(
        ...,
        description="List of linear rings. First ring is the exterior boundary.",
        example=[
            [
                [-88.54321, 13.43210],
                [-88.54100, 13.43210],
                [-88.54100, 13.43000],
                [-88.54321, 13.43000],
                [-88.54321, 13.43210],
            ]
        ],
    )

    @field_validator("coordinates")
    @classmethod
    def validate_polygon_geometry(cls, v: List[List[List[float]]]) -> List[List[List[float]]]:
        if not v or len(v) == 0:
            raise ValueError("El polígono debe contener al menos un anillo exterior de coordenadas.")

        exterior_ring = v[0]

        if len(exterior_ring) < 4:
            raise ValueError(
                f"El anillo exterior del polígono debe tener al menos 4 puntos para ser una figura cerrada (recibidos: {len(exterior_ring)})."
            )

        # Validate closed ring (first coordinate equals last coordinate)
        first_pt = exterior_ring[0]
        last_pt = exterior_ring[-1]

        if len(first_pt) < 2 or len(last_pt) < 2:
            raise ValueError("Cada coordenada debe contener al menos 2 elementos: [longitud, latitud].")

        if not (math.isclose(first_pt[0], last_pt[0], abs_tol=1e-6) and math.isclose(first_pt[1], last_pt[1], abs_tol=1e-6)):
            raise ValueError(
                f"El polígono no está cerrado. El primer punto {first_pt} debe coincidir exactamente con el último punto {last_pt}."
            )

        # Validate bounding box and [lon, lat] order for each point in all rings
        for ring_idx, ring in enumerate(v):
            for pt_idx, coord in enumerate(ring):
                if len(coord) < 2:
                    raise ValueError(f"Coordenada inválida en anillo {ring_idx}, posición {pt_idx}: debe ser [longitud, latitud].")

                lon, lat = coord[0], coord[1]

                # Check if coordinates were inverted: [lat, lon] instead of [lon, lat]
                if lon > 0 and lat < 0:
                    raise ValueError(
                        f"Coordenada invertida detectada en punto {pt_idx} ({coord}): El orden estricto de GeoJSON RFC 7946 es [longitud, latitud] (X, Y)."
                    )

                if not (EL_SALVADOR_MIN_LON <= lon <= EL_SALVADOR_MAX_LON):
                    raise ValueError(
                        f"Longitud {lon} fuera de los límites de El Salvador [{EL_SALVADOR_MIN_LON}, {EL_SALVADOR_MAX_LON}]."
                    )

                if not (EL_SALVADOR_MIN_LAT <= lat <= EL_SALVADOR_MAX_LAT):
                    raise ValueError(
                        f"Latitud {lat} fuera de los límites de El Salvador [{EL_SALVADOR_MIN_LAT}, {EL_SALVADOR_MAX_LAT}]."
                    )

        return v


class PlotBase(BaseModel):
    """
    Base plot schema with agronomic attributes.
    """
    name: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Name of the plot / tablon",
        example="Tablón Los Cedros",
    )
    coffee_variety: str = Field(
        ...,
        min_length=2,
        max_length=60,
        description="Coffee variety planted",
        example="Bourbon",
    )


class PlotCreate(PlotBase):
    """
    Schema for creating a new georeferenced plot.
    """
    farm_id: UUID = Field(..., description="ID of the farm owning this plot")
    geojson: GeoJSONPolygon = Field(..., description="Spatial polygon in GeoJSON format (EPSG:4326)")


class PlotUpdate(BaseModel):
    """
    Schema for updating plot attributes or geometry.
    """
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    coffee_variety: Optional[str] = Field(None, min_length=2, max_length=60)
    geojson: Optional[GeoJSONPolygon] = None


class PlotOut(PlotBase):
    """
    Serialized plot output including calculated surface area and GeoJSON geometry.
    """
    id: UUID
    farm_id: UUID
    area_hectares: float = Field(..., description="Calculated area in hectares")
    geojson: GeoJSONPolygon = Field(..., description="GeoJSON polygon geometry")
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PlotFeatureProperties(BaseModel):
    """
    Properties payload for GeoJSON Feature representation.
    """
    plot_id: UUID
    farm_id: UUID
    farm_name: str
    producer_name: str
    variety: str
    area_hectares: float
    created_at: datetime


class PlotFeatureGeoJSON(BaseModel):
    """
    RFC 7946 compliant GeoJSON Feature for direct consumption by MapLibre GL JS.
    """
    type: Literal["Feature"] = "Feature"
    properties: PlotFeatureProperties
    geometry: GeoJSONPolygon


class PlotFeatureCollectionGeoJSON(BaseModel):
    """
    RFC 7946 compliant GeoJSON FeatureCollection.
    """
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: List[PlotFeatureGeoJSON]
