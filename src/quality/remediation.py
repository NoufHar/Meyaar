from sqlalchemy import text

from src.quality.db import get_engine
from src.quality.fix_registry import get_fix_definition

SUPPORTED_LAYERS={"roads","buildings"}

def _validate_layer(layer_name:str)->None:
    if layer_name not in SUPPORTED_LAYERS:
        raise ValueError("Unsupported layer.")

def get_finding_details(run_id:str,rule_id:str,feature_id:str)->dict|None:
    query=text("""
        SELECT result_id,run_id::text,layer_name,feature_id,rule_id,
               error_type,severity,details
        FROM public.validation_results
        WHERE run_id=:run_id AND rule_id=:rule_id AND feature_id=:feature_id
        ORDER BY result_id
        LIMIT 1
    """)
    with get_engine().connect() as conn:
        row=conn.execute(query,{"run_id":run_id,"rule_id":rule_id,"feature_id":feature_id}).mappings().first()
    return dict(row) if row else None

def get_fix_options(run_id:str,rule_id:str,feature_id:str)->dict:
    finding=get_finding_details(run_id,rule_id,feature_id)
    if not finding:
        return {"status":"not_found","fix_available":False}

    fix=get_fix_definition(rule_id)
    if not fix or not fix["fix_type"]:
        return {
            "status":"success","finding":finding,"fix_available":False,
            "reason":"No deterministic fix is defined.","fix":fix
        }

    return {
        "status":"success",
        "finding":finding,
        "fix_available":bool(fix["implemented"]),
        "fix":dict(fix)
    }

def _geometry_column_type(conn,layer_name:str)->str:
    row=conn.execute(text("""
        SELECT type
        FROM public.geometry_columns
        WHERE f_table_schema='public'
          AND f_table_name=:layer_name
          AND f_geometry_column='geometry'
        LIMIT 1
    """),{"layer_name":layer_name}).first()
    return str(row[0]).upper() if row and row[0] else "GEOMETRY"

def _make_valid(layer_name:str,feature_id:str)->dict:
    _validate_layer(layer_name)
    engine=get_engine()

    with engine.begin() as conn:
        current=conn.execute(text(f"""
            SELECT ST_IsValid(geometry) AS is_valid,
                   ST_IsEmpty(geometry) AS is_empty,
                   GeometryType(geometry) AS geometry_type,
                   ST_SRID(geometry) AS srid
            FROM public.{layer_name}
            WHERE feature_id::text=:feature_id
              AND geometry IS NOT NULL
            LIMIT 1
        """),{"feature_id":feature_id}).mappings().first()

        if not current:
            return {"applied":False,"feature_id":feature_id,"reason":"Feature or geometry was not found."}
        if current["is_empty"]:
            return {"applied":False,"feature_id":feature_id,"reason":"Empty geometry cannot be repaired automatically."}
        if current["is_valid"]:
            return {"applied":False,"feature_id":feature_id,"reason":"Geometry is already valid."}

        expected_type=_geometry_column_type(conn,layer_name)
        candidate=conn.execute(text(f"""
            SELECT GeometryType(ST_MakeValid(geometry)) AS geometry_type,
                   ST_IsValid(ST_MakeValid(geometry)) AS is_valid,
                   ST_IsEmpty(ST_MakeValid(geometry)) AS is_empty,
                   ST_SRID(ST_MakeValid(geometry)) AS srid
            FROM public.{layer_name}
            WHERE feature_id::text=:feature_id
            LIMIT 1
        """),{"feature_id":feature_id}).mappings().first()

        if not candidate or not candidate["is_valid"] or candidate["is_empty"]:
            return {"applied":False,"feature_id":feature_id,"reason":"ST_MakeValid did not produce a safe valid geometry."}

        candidate_type=str(candidate["geometry_type"] or "").upper()
        if expected_type not in {"GEOMETRY",candidate_type}:
            return {
                "applied":False,"feature_id":feature_id,
                "reason":f"Safe fix blocked because geometry type would change from {expected_type} to {candidate_type}."
            }
        if int(candidate["srid"] or 0)!=int(current["srid"] or 0):
            return {"applied":False,"feature_id":feature_id,"reason":"Safe fix blocked because SRID would change."}

        row=conn.execute(text(f"""
            UPDATE public.{layer_name}
            SET geometry=ST_MakeValid(geometry)
            WHERE feature_id::text=:feature_id
              AND geometry IS NOT NULL
              AND NOT ST_IsEmpty(geometry)
              AND NOT ST_IsValid(geometry)
            RETURNING feature_id::text
        """),{"feature_id":feature_id}).first()

    return {
        "applied":bool(row),"feature_id":feature_id,
        "before_geometry_type":current["geometry_type"],
        "after_geometry_type":candidate["geometry_type"]
    }

def _remove_duplicate(layer_name:str,feature_id:str)->dict:
    _validate_layer(layer_name)
    find_duplicate=text(f"""
        SELECT other.feature_id::text
        FROM public.{layer_name} target
        JOIN public.{layer_name} other
          ON ST_AsEWKB(other.geometry)=ST_AsEWKB(target.geometry)
         AND other.feature_id::text<>target.feature_id::text
        WHERE target.feature_id::text=:feature_id
          AND target.geometry IS NOT NULL
        ORDER BY other.feature_id::text
        LIMIT 1
    """)
    delete_query=text(f"""
        DELETE FROM public.{layer_name}
        WHERE feature_id::text=:feature_id
        RETURNING feature_id::text
    """)

    with get_engine().begin() as conn:
        duplicate=conn.execute(find_duplicate,{"feature_id":feature_id}).first()
        if not duplicate:
            return {"applied":False,"feature_id":feature_id,"reason":"No exact geometry duplicate found."}
        deleted=conn.execute(delete_query,{"feature_id":feature_id}).first()

    return {
        "applied":bool(deleted),"feature_id":feature_id,
        "kept_duplicate_feature_id":duplicate[0]
    }

def apply_fix(run_id:str,rule_id:str,feature_id:str,approved:bool=False)->dict:
    option=get_fix_options(run_id,rule_id,feature_id)
    if option["status"]!="success":
        return option
    if not option["fix_available"]:
        return {
            "status":"not_applied","run_id":run_id,"rule_id":rule_id,
            "feature_id":feature_id,"reason":"No implemented deterministic fix."
        }

    fix=option["fix"]
    if fix["requires_approval"] and not approved:
        return {
            "status":"approval_required","run_id":run_id,"rule_id":rule_id,
            "feature_id":feature_id,"fix":fix
        }

    finding=option["finding"]
    layer_name=finding["layer_name"]
    fix_type=fix["fix_type"]

    if fix_type=="make_valid":
        result=_make_valid(layer_name,feature_id)
    elif fix_type=="remove_duplicate":
        result=_remove_duplicate(layer_name,feature_id)
    else:
        return {
            "status":"not_applied","run_id":run_id,"rule_id":rule_id,
            "feature_id":feature_id,"reason":"Fix is not implemented."
        }

    return {
        "status":"applied" if result.get("applied") else "not_applied",
        "run_id":run_id,"rule_id":rule_id,"layer_name":layer_name,
        "feature_id":feature_id,"fix_type":fix_type,"result":result
    }
