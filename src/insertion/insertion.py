from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely import wkt


SUPPORTED_FORMATS = {
    ".geojson",
    ".json",
    ".shp",
    ".gpkg",
    ".parquet",
    ".csv",
}


def load_vector_file(file_path):
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    extension = file_path.suffix.lower()

    if extension not in SUPPORTED_FORMATS:
        supported = ", ".join(sorted(SUPPORTED_FORMATS))

        raise ValueError(
            f"Unsupported file format: {extension or 'no extension'}. "
            f"Supported formats are: {supported}"
        )

    if extension in {".geojson", ".json", ".shp", ".gpkg"}:
        gdf = gpd.read_file(file_path)

    elif extension == ".parquet":
        gdf = gpd.read_parquet(file_path)

    elif extension == ".csv":
        df = pd.read_csv(file_path)

        if "geometry" in df.columns:
            df["geometry"] = df["geometry"].apply(
                lambda value: (
                    wkt.loads(value)
                    if pd.notna(value)
                    else None
                )
            )

            gdf = gpd.GeoDataFrame(
                df,
                geometry="geometry",
                crs="EPSG:4326",
            )

        elif {"longitude", "latitude"}.issubset(df.columns):
            geometry = gpd.points_from_xy(
                df["longitude"],
                df["latitude"],
            )

            gdf = gpd.GeoDataFrame(
                df,
                geometry=geometry,
                crs="EPSG:4326",
            )

        else:
            raise ValueError(
                "CSV must contain either a 'geometry' column "
                "or longitude and latitude columns."
            )

    if "geometry" not in gdf.columns:
        raise ValueError(
            "The file does not contain a geometry column."
        )

    if gdf.empty:
        raise ValueError(
            "The file contains no features."
        )

    return gdf

def detect_layer_type(gdf):
    geometry_types = set(gdf.geom_type.dropna().unique())
    columns = [col.lower() for col in gdf.columns]

    # Roads
    road_types = {"LineString", "MultiLineString"}

    if geometry_types and geometry_types.issubset(road_types):
        return {
            "status": "success",
            "layer_type": "roads"
        }

    # Buildings
    building_types = {"Polygon", "MultiPolygon"}

    if geometry_types and geometry_types.issubset(building_types):
        building_keywords = {
            "building",
            "building_type",
            "height",
            "levels"
        }

        if any(keyword in columns for keyword in building_keywords):
            return {
                "status": "success",
                "layer_type": "buildings"
            }

        return {
            "status": "needs_confirmation",
            "layer_type": "unknown",
            "message": "Polygon layer detected. Please confirm if it is buildings."
        }

    return {
        "status": "needs_confirmation",
        "layer_type": "unknown",
        "message": "Could not detect layer type automatically."
    }

def add_feature_id(gdf):
    """
    Make sure every feature has one standard identifier
    that all validation rules can use.
    """

    gdf = gdf.copy()

    if "feature_id" in gdf.columns:
        gdf["feature_id"] = gdf["feature_id"].astype(str)

    elif "id" in gdf.columns:
        gdf["feature_id"] = gdf["id"].astype(str)

    elif "ogc_fid" in gdf.columns:
        gdf["feature_id"] = gdf["ogc_fid"].astype(str)

    else:
        gdf["feature_id"] = [
            str(i)
            for i in range(1, len(gdf) + 1)
        ]

    return gdf


def insert_vector_data(
    engine,
    file_path,
    table_name,
):
    try:
        print("Reading file...")

        gdf = load_vector_file(file_path)

        # Add one standard ID for the validation rules
        gdf = add_feature_id(gdf)

        print("File loaded successfully")
        print("Rows:", len(gdf))
        print("CRS:", gdf.crs)
        print(
            "Geometry types:",
            gdf.geom_type.dropna().unique(),
        )

        print("Inserting into PostGIS...")

        gdf.to_postgis(
            name=table_name,
            con=engine,
            schema="public",
            if_exists="replace",
            index=False,
        )

        return {
            "status": "success",
            "message": (
                "File inserted into PostGIS successfully."
            ),
            "table_name": table_name,
            "inserted_rows": len(gdf),
            "crs": (
                str(gdf.crs)
                if gdf.crs
                else None
            ),
            "geometry_types": (
                gdf.geom_type
                .dropna()
                .unique()
                .tolist()
            ),
        }

    except (ValueError, FileNotFoundError) as e:
        return {
            "status": "failed",
            "message": str(e),
        }

    except Exception as e:
        return {
            "status": "failed",
            "message": (
                f"Error while processing file: {e}"
            ),
        }