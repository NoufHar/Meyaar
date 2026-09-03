-- ============================================================
-- MEYAAR - BUILDINGS RULES
-- BLD001-BLD004
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_buildings_geometry
    ON public.buildings USING GIST (geometry);

ANALYZE public.buildings;


-- BLD004 — Missing Geometry
INSERT INTO public.validation_results
(
    run_id, layer_name, feature_id,
    rule_id, error_type, severity, details
)
SELECT
    r.run_id,
    'buildings',
    b.feature_id::text,
    'BLD004',
    'Missing Geometry',
    'critical',
    'Building geometry is NULL or empty.'
FROM public.buildings b
CROSS JOIN _meyaar_run r
WHERE b.geometry IS NULL
   OR ST_IsEmpty(b.geometry);


-- BLD003 — Invalid Geometry
INSERT INTO public.validation_results
(
    run_id, layer_name, feature_id,
    rule_id, error_type, severity, details
)
SELECT
    r.run_id,
    'buildings',
    b.feature_id::text,
    'BLD003',
    'Invalid Geometry',
    'high',
    ST_IsValidReason(b.geometry)
FROM public.buildings b
CROSS JOIN _meyaar_run r
WHERE b.geometry IS NOT NULL
  AND NOT ST_IsEmpty(b.geometry)
  AND NOT ST_IsValid(b.geometry);


-- BLD002 — Duplicate Buildings
WITH duplicate_groups AS (
    SELECT
        ST_AsEWKB(geometry) AS geom_key,
        COUNT(*) AS duplicate_count
    FROM public.buildings
    WHERE geometry IS NOT NULL
      AND NOT ST_IsEmpty(geometry)
    GROUP BY ST_AsEWKB(geometry)
    HAVING COUNT(*) > 1
)

INSERT INTO public.validation_results
(
    run_id, layer_name, feature_id,
    rule_id, error_type, severity, details
)

SELECT
    r.run_id,
    'buildings',
    b.feature_id::text,
    'BLD002',
    'Duplicate Buildings',
    'medium',
    'Exact duplicate building geometry. Duplicate group size = '
        || d.duplicate_count::text

FROM public.buildings b

JOIN duplicate_groups d
    ON ST_AsEWKB(b.geometry) = d.geom_key

CROSS JOIN _meyaar_run r;


-- BLD001 — Building Overlap
WITH overlap_pairs AS (
    SELECT
        a.feature_id::text AS feature_a,
        b.feature_id::text AS feature_b,

        ST_Area(
            ST_Intersection(
                ST_Transform(a.geometry, 32638),
                ST_Transform(b.geometry, 32638)
            )
        ) AS overlap_area_m2

    FROM public.buildings a

    JOIN public.buildings b
      ON a.feature_id::text < b.feature_id::text
     AND a.geometry && b.geometry
     AND ST_Intersects(
            a.geometry,
            b.geometry
         )

    WHERE a.geometry IS NOT NULL
      AND b.geometry IS NOT NULL

      AND NOT ST_IsEmpty(a.geometry)
      AND NOT ST_IsEmpty(b.geometry)

      AND ST_IsValid(a.geometry)
      AND ST_IsValid(b.geometry)

      AND ST_SRID(a.geometry) = 4326
      AND ST_SRID(b.geometry) = 4326

      AND NOT ST_Touches(
            a.geometry,
            b.geometry
          )

      AND NOT ST_Equals(
            a.geometry,
            b.geometry
          )
)

INSERT INTO public.validation_results
(
    run_id, layer_name, feature_id,
    rule_id, error_type, severity, details
)

SELECT
    r.run_id,
    'buildings',
    o.feature_a,
    'BLD001',
    'Building Overlap',
    'high',
    'Building overlaps building '
        || o.feature_b
        || '. Overlap area = '
        || ROUND(
            o.overlap_area_m2::numeric,
            2
        )::text
        || ' m².'

FROM overlap_pairs o
CROSS JOIN _meyaar_run r

WHERE o.overlap_area_m2 > 0;