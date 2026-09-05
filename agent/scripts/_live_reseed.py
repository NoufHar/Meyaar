"""Reseed a layer table through partner helpers, sampled for speed."""
import sys

from sqlalchemy import create_engine

from src.insertion.insertion import add_feature_id, load_vector_file

layer = sys.argv[1]           # buildings | roads
src_file = sys.argv[2]
n = int(sys.argv[3])

gdf = load_vector_file(src_file)
gdf = add_feature_id(gdf)
sample = gdf.sample(n=n, random_state=42)

engine = create_engine("postgresql+psycopg2://postgres@localhost:5432/meyaar_db")
sample.to_postgis(layer, con=engine, schema="public", if_exists="replace", index=False)
print(f"{layer} reseeded:", len(sample), "| crs:", sample.crs)
