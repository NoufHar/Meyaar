from src.insertion.database import create_db_engine
from src.insertion.insertion import (
    load_vector_file,
    detect_layer_type,
    insert_vector_data,
)
from src.validation.validation_tools import run_rules_for_layer


def process_dataset(file_path):
    engine = create_db_engine()

    # 1. Read dataset
    gdf = load_vector_file(file_path)

    # 2. Detect layer type
    detection = detect_layer_type(gdf)

    if detection["status"] != "success":
        return detection

    layer_name = detection["layer_type"]

    # 3. Insert into PostGIS
    insertion_result = insert_vector_data(
        engine=engine,
        file_path=file_path,
        table_name=layer_name
    )

    if insertion_result["status"] != "success":
        return insertion_result

    # 4. Run the correct rules
    validation_result = run_rules_for_layer(
        engine=engine,
        layer_name=layer_name
    )

    return {
    "status": validation_result["status"],
    "layer_name": layer_name,
    "insertion": insertion_result,
    "validation": validation_result
}