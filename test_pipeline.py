from src.pipeline import process_dataset

result = process_dataset(
    "data/riyadh_roads_clean.geojson"
)

print("Status:", result["status"])
print("Layer:", result.get("layer_name"))

if "validation" in result:
    print("Total errors:", result["validation"]["total_errors"])
    print("Summary:")

    for row in result["validation"]["summary"]:
        print(row)
else:
    print(result)