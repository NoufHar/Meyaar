import os

from dotenv import load_dotenv
from sqlalchemy import create_engine

import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from agent.graph.builder import run_analysis
from src.insertion.insertion import (
    detect_layer_type,
    insert_vector_data,
    load_vector_file,
)
from src.validation.validation_tools import (
    run_rules_for_layer,
)

load_dotenv()

SUPPORTED_VECTOR_EXTENSIONS = {
    ".geojson",
    ".json",
    ".gpkg",
    ".csv",
    ".parquet",
    ".zip",
}


class InvalidVectorFileError(ValueError):
    pass


class VectorProcessingError(RuntimeError):
    pass


def _safe_extract_shapefile(
    zip_path: Path,
    destination: Path,
) -> Path:
    try:
        with zipfile.ZipFile(zip_path) as archive:
            destination_root = destination.resolve()

            for member in archive.infolist():
                member_path = (
                    destination / member.filename
                ).resolve()

                if (
                    destination_root
                    not in member_path.parents
                    and member_path != destination_root
                ):
                    raise InvalidVectorFileError(
                        "The ZIP file contains "
                        "an unsafe path."
                    )

            archive.extractall(destination)

    except zipfile.BadZipFile as error:
        raise InvalidVectorFileError(
            "The uploaded ZIP file is invalid."
        ) from error

    shapefiles = list(
        destination.rglob("*.shp")
    )

    if len(shapefiles) != 1:
        raise InvalidVectorFileError(
            "The ZIP file must contain exactly "
            "one Shapefile."
        )

    shapefile = shapefiles[0]

    required_files = {
        ".shp",
        ".shx",
        ".dbf",
    }

    available_files = {
        file.suffix.lower()
        for file in shapefile.parent.iterdir()
        if file.stem.lower()
        == shapefile.stem.lower()
    }

    missing_files = (
        required_files - available_files
    )

    if missing_files:
        raise InvalidVectorFileError(
            "The Shapefile is missing: "
            + ", ".join(sorted(missing_files))
        )

    return shapefile


def process_vector_upload(
    filename: str,
    content: bytes,
    requested_layer: str | None = None,
) -> dict:
    extension = Path(filename).suffix.lower()

    if extension not in SUPPORTED_VECTOR_EXTENSIONS:
        raise InvalidVectorFileError(
            "Supported vector formats are "
            "GeoJSON, JSON, GeoPackage, CSV, "
            "GeoParquet, and zipped Shapefile."
        )

    if not content:
        raise InvalidVectorFileError(
            "The uploaded file is empty."
        )

    if requested_layer is not None:
        requested_layer = (
            requested_layer.lower().strip()
        )

        if requested_layer not in {
            "roads",
            "buildings",
        }:
            raise InvalidVectorFileError(
                "Layer type must be roads "
                "or buildings."
            )

    with TemporaryDirectory() as temporary:
        temporary_path = Path(temporary)
        uploaded_path = (
            temporary_path / Path(filename).name
        )

        uploaded_path.write_bytes(content)

        if extension == ".zip":
            vector_path = _safe_extract_shapefile(
                uploaded_path,
                temporary_path / "shapefile",
            )
        else:
            vector_path = uploaded_path

        try:
            gdf = load_vector_file(vector_path)
        except Exception as error:
            raise InvalidVectorFileError(
                str(error)
            ) from error

        detection = detect_layer_type(gdf)

        if requested_layer:
            layer_name = requested_layer
        elif detection["status"] == "success":
            layer_name = detection["layer_type"]
        else:
            raise InvalidVectorFileError(
                detection.get(
                    "message",
                    "Could not detect layer type.",
                )
            )

        database_url = os.getenv(
    "MEYAAR_DATABASE_URL"
)
        if not database_url:
            raise VectorProcessingError(
                "MEYAAR_DATABASE_URL is not configured."
    )
        engine = create_engine(
            database_url,
            pool_pre_ping=True,)

        insertion = insert_vector_data(
            engine=engine,
            file_path=vector_path,
            table_name=layer_name,
        )

        if insertion["status"] != "success":
            raise VectorProcessingError(
                insertion.get(
                    "message",
                    "Vector insertion failed.",
                )
            )

        validation = run_rules_for_layer(
            engine=engine,
            layer_name=layer_name,
        )

        if validation["status"] != "success":
            raise VectorProcessingError(
                validation.get(
                    "message",
                    "Vector validation failed.",
                )
            )

        run_id = validation["run_id"]

        analysis = run_analysis(run_id)

        return {
            "filename": filename,
            "status": "completed",
            "layer_name": layer_name,
            "run_id": run_id,
            "insertion": insertion,
            "validation": validation,
            "analysis": analysis,
        }