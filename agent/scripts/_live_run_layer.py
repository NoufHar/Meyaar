"""Run the rule engine for a layer and print status + run_id + summary."""
import sys

from src.insertion.database import create_db_engine
from src.validation.validation_tools import run_rules_for_layer

layer = sys.argv[1]
r = run_rules_for_layer(create_db_engine(), layer)
print("status:", r.get("status"))
if r.get("status") != "success":
    print("message:", r.get("message"))
else:
    print("run_id:", r["run_id"])
    print("total_errors:", r["total_errors"])
    for s in r["summary"]:
        print("summary:", s)
