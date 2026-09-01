import json
import math
from datetime import datetime
from typing import Any, Dict, List, Union
from uuid import UUID
from geoalchemy2.elements import WKBElement
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Polygon, mapping, shape


def geojson_to_shape(geojson_dict: Union[Dict[str, Any], str]) -> Polygon:
    """
    Converts a GeoJSON dictionary or JSON string to a Shapely Polygon.
    """
    if isinstance(geojson_dict, str):
        geojson_dict = json.loads(geojson_dict)
    geom = shape(geojson_dict)
    if not isinstance(geom, Polygon):
        raise ValueError("Geometry must be a Polygon.")
    return geom


def shape_to_geojson(geom: Polygon) -> Dict[str, Any]:
    """
    Converts a Shapely Polygon to a GeoJSON-compatible dictionary.
    """
    return mapping(geom)  # type: ignore[no-any-return]


def wkb_to_geojson_dict(geometry_data: Union[WKBElement, Any]) -> Dict[str, Any]:
    """
    Converts a GeoAlchemy2 WKBElement or spatial DB column value into a GeoJSON dictionary.
    """
    if isinstance(geometry_data, WKBElement):
        geom_shape = to_shape(geometry_data)
        return mapping(geom_shape)  # type: ignore[no-any-return]
    elif hasattr(geometry_data, "desc"):
        # Fallback if raw WKBElement or string
        geom_shape = to_shape(geometry_data)
        return mapping(geom_shape)  # type: ignore[no-any-return]
    elif isinstance(geometry_data, dict):
        return geometry_data
    elif isinstance(geometry_data, str):
        try:
            return json.loads(geometry_data)
        except json.JSONDecodeError:
            pass
    raise ValueError(f"Unable to convert geometry data of type {type(geometry_data)} to GeoJSON.")


def calculate_geodesic_area_hectares(geojson_dict: Union[Dict[str, Any], str]) -> float:
    """
    Calculates geodesic surface area in hectares using spherical trigonometry approximation
    for WGS84 EPSG:4326 coordinates.
    This serves as a Python-level fallback/cross-check for PostGIS ST_Area(geography).
    """
    geom = geojson_to_shape(geojson_dict)
    
    # Earth radius in meters
    EARTH_RADIUS = 6378137.0
    
    def ring_area(coordinates: List[List[float]]) -> float:
        if len(coordinates) < 4:
            return 0.0
        area = 0.0
        n = len(coordinates)
        for i in range(n - 1):
            p1 = coordinates[i]
            p2 = coordinates[i + 1]
            lon1, lat1 = math.radians(p1[0]), math.radians(p1[1])
            lon2, lat2 = math.radians(p2[0]), math.radians(p2[1])
            area += (lon2 - lon1) * (2 + math.sin(lat1) + math.sin(lat2))
        area = abs(area * (EARTH_RADIUS ** 2) / 2.0)
        return area

    exterior_coords = list(geom.exterior.coords)
    total_area_sq_meters = ring_area([[c[0], c[1]] for c in exterior_coords])

    # Subtract interior holes
    for interior in geom.interiors:
        hole_coords = list(interior.coords)
        total_area_sq_meters -= ring_area([[c[0], c[1]] for c in hole_coords])

    # 1 hectare = 10,000 square meters
    area_hectares = max(0.0, total_area_sq_meters / 10000.0)
    return round(area_hectares, 4)


def create_plot_feature_geojson(
    plot_id: UUID,
    farm_id: UUID,
    farm_name: str,
    producer_name: str,
    variety: str,
    area_hectares: float,
    created_at: datetime,
    geojson_polygon: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Constructs an RFC 7946 GeoJSON Feature dictionary ready for MapLibre GL JS consumption.
    """
    return {
        "type": "Feature",
        "properties": {
            "plot_id": str(plot_id),
            "farm_id": str(farm_id),
            "farm_name": farm_name,
            "producer_name": producer_name,
            "variety": variety,
            "area_hectares": float(area_hectares),
            "created_at": created_at.isoformat(),
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": geojson_polygon.get("coordinates", []),
        },
    }
