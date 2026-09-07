from pathlib import Path

VECTOR_EXTENSIONS={".geojson",".json",".gpkg",".csv",".parquet",".zip"}
IMAGE_EXTENSIONS={".jpg",".jpeg",".png",".tif",".tiff"}

def detect_input_type(filename:str)->str:
    ext=Path(filename).suffix.lower()
    if ext in VECTOR_EXTENSIONS:
        return "vector"
    if ext in IMAGE_EXTENSIONS:
        return "image"
    return "unsupported"