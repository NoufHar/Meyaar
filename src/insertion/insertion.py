from pathlib import Path
import geopandas as gpd
import pandas as pd
from shapely import wkt


SUPPORTED_FORMATS = [".geojson", ".json", ".shp", ".gpkg", ".parquet", ".csv"]


def load_vector_file(file_path):
    file_path = Path(file_path)
    extension = file_path.suffix.lower()

    if extension not in SUPPORTED_FORMATS:
        raise ValueError(
            f"Unsupported file format: {extension}\n"
            f"Supported formats are: {', '.join(SUPPORTED_FORMATS)}"
        )

    if extension in [".geojson", ".json", ".shp", ".gpkg"]:
        return gpd.read_file(file_path)

    elif extension == ".parquet":
        return gpd.read_parquet(file_path)

    elif extension == ".csv":
        df = pd.read_csv(file_path)

        if "geometry" in df.columns:
            df["geometry"] = df["geometry"].apply(wkt.loads)

            return gpd.GeoDataFrame(
                df,
                geometry="geometry",
                crs="EPSG:4326"
            )

        elif "longitude" in df.columns and "latitude" in df.columns:
            geometry = gpd.points_from_xy(
                df["longitude"],
                df["latitude"]
            )

            return gpd.GeoDataFrame(
                df,
                geometry=geometry,
                crs="EPSG:4326"
            )

        else:
            raise ValueError(
                "CSV file must contain either:\n"
                "- a geometry column\n"
                "or\n"
                "- longitude and latitude columns"
            )


def insert_vector_data(engine, file_path, table_name):
    try:
        print("Reading file...")

        gdf = load_vector_file(file_path)

        print("File loaded successfully")
        print("Rows:", len(gdf))
        print("CRS:", gdf.crs)
        print("Geometry types:", gdf.geom_type.unique())

        print("Inserting into PostGIS...")

        gdf.to_postgis(
            name=table_name,
            con=engine,
            schema="public",
            if_exists="replace",
            index=False
        )

        return {
            "status": "success",
            "message": "File inserted successfully",
            "table_name": table_name,
            "inserted_rows": len(gdf)
        }

    except ValueError as e:
        return {
            "status": "failed",
            "message": str(e)
        }

    except FileNotFoundError:
        return {
            "status": "failed",
            "message": f"File not found: {file_path}"
        }

    except Exception as e:
        return {
            "status": "failed",
            "message": f"Error while processing file: {str(e)}"
        }