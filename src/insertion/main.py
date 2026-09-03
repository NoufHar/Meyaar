from database import create_db_engine, connect_to_db
from insertion import insert_vector_data


engine = create_db_engine()

connection_result = connect_to_db(engine)

print(connection_result)


result = insert_vector_data(
    engine=engine,
    file_path="data/riyadh_roads_clean.geojson",
    table_name="roads"
)

print(result)