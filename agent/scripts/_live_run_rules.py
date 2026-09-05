"""Run the partner rule engine against the already-inserted roads table and
print the run_id + summary (no re-insertion)."""
from src.insertion.database import create_db_engine
from src.validation.validation_tools import run_rules_for_layer

engine = create_db_engine()
r = run_rules_for_layer(engine, "roads")
print("status:", r.get("status"))
if r.get("status") != "success":
    print("message:", r.get("message"))
else:
    print("run_id:", r["run_id"])
    print("total_errors:", r["total_errors"])
    for s in r["summary"]:
        print("summary:", s)
