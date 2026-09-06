"""Map data endpoint for the Meyaar frontend.

Returns GeoJSON for a processed validation run so the browser can draw the
source layer on a Leaflet map. Only the two pipeline tables are allowed.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import create_engine, text

from agent.core.config import settings

router = APIRouter(tags=["map"])

ALLOWED_LAYERS = {"roads", "buildings"}


def _engine():
    return create_engine(
        settings.database_url,
        connect_args={"options": settings.db_read_only_options},
        pool_pre_ping=True,
    )


@router.get("/vectors/{run_id}/geojson", summary="Get map features for a validation run")
def get_run_geojson(
    run_id: str,
    layer: str = Query(..., pattern="^(roads|buildings)$"),
    limit: int = Query(5000, ge=1, le=20000),
):
    """Return the processed GIS layer as GeoJSON.

    The API deliberately exposes only a whitelisted table name. Geometry is
    transformed to EPSG:4326 when a source SRID is present so Leaflet can draw
    it directly. Feature IDs are returned so the UI can join them to the
    validation/agent results from /api/validation/{run_id}/analysis.
    """
    layer = layer.lower().strip()
    if layer not in ALLOWED_LAYERS:
        raise HTTPException(status_code=400, detail="Unsupported layer.")

    sql = f"""
        SELECT
            feature_id::text AS feature_id,
            ST_AsGeoJSON(
                CASE
                    WHEN geometry IS NULL OR ST_IsEmpty(geometry) THEN NULL
                    WHEN ST_SRID(geometry) = 4326 THEN geometry
                    WHEN ST_SRID(geometry) > 0 THEN ST_Transform(geometry, 4326)
                    ELSE ST_SetSRID(geometry, 4326)
                END
            ) AS geometry
        FROM public.{layer}
        ORDER BY feature_id::text
        LIMIT :limit
    """

    try:
        with _engine().connect() as conn:
            rows = conn.execute(text(sql), {"limit": limit}).mappings().all()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Map data fetch failed: {exc}") from exc

    features = []
    for row in rows:
        geometry = json.loads(row["geometry"]) if row["geometry"] else None
        features.append({
            "type": "Feature",
            "id": str(row["feature_id"]),
            "properties": {
                "feature_id": str(row["feature_id"]),
                "layer_name": layer,
            },
            "geometry": geometry,
        })

    return {
        "type": "FeatureCollection",
        "run_id": run_id,
        "layer_name": layer,
        "feature_count": len(features),
        "features": features,
    }
