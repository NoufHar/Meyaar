from src.insertion.database import create_db_engine
from src.validation.validation_tools import run_rules_for_layer

engine = create_db_engine()

# Change this to "buildings" when testing a buildings layer.
result = run_rules_for_layer(engine, "buildings")

print("Status:", result["status"])

if result["status"] == "success":
    print("Layer:", result["layer_name"])
    print("Run ID:", result["run_id"])
    print("Total errors:", result["total_errors"])
    print("Summary:")
    for row in result["summary"]:
        print(row)
else:
    print("Error:", result["message"])
