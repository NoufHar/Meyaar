import uuid

from sqlalchemy import text

from src.quality import (
    FIX_REGISTRY,
    QUALITY_REGISTRY,
    apply_fix,
    calculate_quality_results,
    evaluate_conformance,
    get_fix_definition,
    get_fix_options,
    get_quality_definition,
    get_revalidation_results,
)
from src.quality.db import get_engine

engine=get_engine()

def title(name):
    print(f"\n{'='*58}\n{name}\n{'='*58}")

def latest_run(layer_name="roads"):
    with engine.connect() as conn:
        row=conn.execute(text("""
            SELECT run_id::text
            FROM public.validation_results
            WHERE layer_name=:layer_name
            GROUP BY run_id
            ORDER BY MAX(detected_at) DESC
            LIMIT 1
        """),{"layer_name":layer_name}).first()
    if not row:
        raise RuntimeError(f"No validation run found for {layer_name}.")
    return row[0]

def test_registry():
    title("1. QUALITY + FIX REGISTRIES")
    required={
        "RD001","RD002","RD003","RD004","RD005",
        "BLD001","BLD002","BLD003","BLD004",
        "GIS001","GIS002","GIS003","GIS004","GIS005",
    }
    assert not required-set(QUALITY_REGISTRY)
    assert not required-set(FIX_REGISTRY)
    for rule_id in sorted(required):
        quality=get_quality_definition(rule_id)
        fix=get_fix_definition(rule_id)
        assert quality and fix
        print(f"PASS {rule_id}: {quality['quality_element']} | fix={fix['fix_type']}")

def test_quality(run_id,layer_name):
    title("2. QUALITY EVALUATOR")
    result=calculate_quality_results(run_id,layer_name)
    assert result["total_features"]>0
    print("Run:",run_id)
    print("Features:",result["total_features"])
    print("Findings:",result["total_findings"])
    print("Summary:",result["summary"])
    for item in result["quality_results"]:
        print(item["rule_id"],item["value"],item["status"])
    return result

def test_fix_options(run_id):
    title("3. FINDING + FIX OPTIONS + SAFETY")
    with engine.connect() as conn:
        row=conn.execute(text("""
            SELECT rule_id,feature_id
            FROM public.validation_results
            WHERE run_id=:run_id
              AND feature_id IS NOT NULL
            ORDER BY result_id
            LIMIT 1
        """),{"run_id":run_id}).mappings().first()
    if not row:
        print("SKIP: current run has no feature-level findings.")
        return

    options=get_fix_options(run_id,row["rule_id"],row["feature_id"])
    assert options["status"]=="success"
    print("Options:",options)

    if not options["fix_available"]:
        result=apply_fix(run_id,row["rule_id"],row["feature_id"],approved=False)
        assert result["status"]=="not_applied"
        print("PASS: unavailable fix blocked.")
    elif options["fix"]["requires_approval"]:
        result=apply_fix(run_id,row["rule_id"],row["feature_id"],approved=False)
        assert result["status"]=="approval_required"
        print("PASS: approval protection works.")
    else:
        print("PASS: safe implemented fix is available. Actual dataset mutation skipped.")

def test_make_valid_capability():
    title("4. POSTGIS MAKE_VALID CAPABILITY")
    table="meyaar_quality_test_geometry"
    feature_id=str(uuid.uuid4())
    try:
        with engine.begin() as conn:
            conn.execute(text(f"DROP TABLE IF EXISTS public.{table}"))
            conn.execute(text(f"""
                CREATE TABLE public.{table}(
                    feature_id text PRIMARY KEY,
                    geometry geometry(Geometry,4326)
                )
            """))
            conn.execute(text(f"""
                INSERT INTO public.{table}(feature_id,geometry)
                VALUES(:feature_id,ST_GeomFromText(
                    'POLYGON((46 24,47 25,47 24,46 25,46 24))',4326
                ))
            """),{"feature_id":feature_id})
            before=conn.execute(text(f"SELECT ST_IsValid(geometry) FROM public.{table} WHERE feature_id=:feature_id"),{"feature_id":feature_id}).scalar()
            conn.execute(text(f"UPDATE public.{table} SET geometry=ST_MakeValid(geometry) WHERE feature_id=:feature_id"),{"feature_id":feature_id})
            after=conn.execute(text(f"SELECT ST_IsValid(geometry) FROM public.{table} WHERE feature_id=:feature_id"),{"feature_id":feature_id}).scalar()
        assert before is False and after is True
        print("PASS: invalid geometry repaired on isolated test table.")
    finally:
        with engine.begin() as conn:
            conn.execute(text(f"DROP TABLE IF EXISTS public.{table}"))

def test_revalidation_comparison():
    title("5. BEFORE / AFTER REVALIDATION COMPARISON")
    before_id=str(uuid.uuid4())
    after_id=str(uuid.uuid4())
    try:
        with engine.begin() as conn:
            rows=[
                (before_id,"T-A","RD001","Road Overshoot","high","same issue A"),
                (before_id,"T-B","RD002","Road Undershoot","high","same issue B"),
                (after_id,"T-B","RD002","Road Undershoot","high","same issue B"),
                (after_id,"T-C","RD001","Road Overshoot","high","new issue C"),
            ]
            for run_id,feature_id,rule_id,error_type,severity,details in rows:
                conn.execute(text("""
                    INSERT INTO public.validation_results(
                        run_id,layer_name,feature_id,rule_id,error_type,severity,details
                    ) VALUES(CAST(:run_id AS uuid),'roads',:feature_id,:rule_id,:error_type,:severity,:details)
                """),{
                    "run_id":run_id,"feature_id":feature_id,"rule_id":rule_id,
                    "error_type":error_type,"severity":severity,"details":details
                })

        result=get_revalidation_results(before_id,after_id)
        assert result["summary"]["resolved"]==1
        assert result["summary"]["still_present"]==1
        assert result["summary"]["new_issues"]==1
        print("PASS:",result["summary"])
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM public.validation_results WHERE run_id IN (CAST(:before AS uuid),CAST(:after AS uuid))"),{"before":before_id,"after":after_id})

def test_compliance(result):
    title("6. COMPLIANCE SAFETY")
    proxy=next((item for item in result["quality_results"] if item["threshold_source"]=="geosa_proxy"),None)
    if proxy:
        assessment=evaluate_conformance(proxy)
        assert assessment["status"]=="not_determined"
        print("PASS: GeoSA proxy is not misreported as official compliance.")
        print(assessment["reason"])
    else:
        print("PASS: no GeoSA proxy metric in this run.")

def main():
    layer_name="roads"
    run_id=latest_run(layer_name)
    test_registry()
    result=test_quality(run_id,layer_name)
    test_fix_options(run_id)
    test_make_valid_capability()
    test_revalidation_comparison()
    test_compliance(result)

    title("FINAL RESULT")
    print("Quality Registry        PASS")
    print("Fix Registry            PASS")
    print("Quality Evaluator       PASS")
    print("Fix Safety              PASS")
    print("PostGIS Repair          PASS")
    print("Before/After Comparison PASS")
    print("Compliance Guard        PASS")
    print("\nMEYAAR QUALITY PIPELINE PASSED")

if __name__=="__main__":
    main()
