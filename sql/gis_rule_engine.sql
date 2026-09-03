-- ============================================================
-- MEYAAR GIS RULE ENGINE
-- PostgreSQL + PostGIS
--
-- Buildings:
-- BLD001 Building Overlap
-- BLD002 Duplicate Buildings
-- BLD003 Invalid Geometry
-- BLD004 Missing Geometry
--
-- Roads:
-- RD001 Road Overshoot
-- RD002 Road Undershoot
-- RD003 Duplicate Roads
-- RD004 Invalid Geometry
-- RD005 Missing Geometry
--
-- General GIS:
-- GIS001 Missing/Wrong CRS
-- GIS002 Invalid Coordinates
-- GIS003 Missing Required Attributes
-- GIS004 Wrong Data Type
-- GIS005 Invalid Attribute Values
--
-- NOTE:
-- RD001 and RD002 are spatial heuristic checks using a 5-meter
-- tolerance. Their results should be interpreted as topology
-- violation candidates and reviewed when needed.
-- ============================================================


-- ============================================================
-- 0) EXTENSIONS
-- ============================================================

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgcrypto;


-- ============================================================
-- 1) RESULTS TABLE
-- ============================================================

CREATE TABLE IF NOT EXISTS public.validation_results (
    result_id      BIGSERIAL PRIMARY KEY,
    run_id         UUID NOT NULL,
    layer_name     TEXT NOT NULL,
    feature_id     TEXT,
    rule_id        TEXT NOT NULL,
    error_type     TEXT NOT NULL,
    severity       TEXT NOT NULL,
    details        TEXT,
    detected_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_validation_results_run
    ON public.validation_results(run_id);

CREATE INDEX IF NOT EXISTS idx_validation_results_rule
    ON public.validation_results(rule_id, layer_name);


-- ============================================================
-- 2) CONFIGURATION TABLES FOR ATTRIBUTE RULES
-- ============================================================

CREATE TABLE IF NOT EXISTS public.meyaar_required_attributes (
    layer_name   TEXT NOT NULL,
    column_name  TEXT NOT NULL,
    PRIMARY KEY (layer_name, column_name)
);

CREATE TABLE IF NOT EXISTS public.meyaar_expected_types (
    layer_name    TEXT NOT NULL,
    column_name   TEXT NOT NULL,
    expected_type TEXT NOT NULL,
    PRIMARY KEY (layer_name, column_name)
);

CREATE TABLE IF NOT EXISTS public.meyaar_allowed_values (
    layer_name    TEXT NOT NULL,
    column_name   TEXT NOT NULL,
    allowed_value TEXT NOT NULL,
    PRIMARY KEY (layer_name, column_name, allowed_value)
);

-- IMPORTANT:
-- Leave these tables empty until requirements are verified
-- from the selected GeoSA standard/guideline.


-- ============================================================
-- 3) PERFORMANCE INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_roads_geometry
    ON public.roads USING GIST (geometry);

CREATE INDEX IF NOT EXISTS idx_buildings_geometry
    ON public.buildings USING GIST (geometry);

CREATE INDEX IF NOT EXISTS idx_connectors_geometry
    ON public.connectors USING GIST (geometry);

ANALYZE public.roads;
ANALYZE public.buildings;
ANALYZE public.connectors;


-- ============================================================
-- 4) START NEW VALIDATION RUN
-- ============================================================

DROP TABLE IF EXISTS _meyaar_run;

CREATE TEMP TABLE _meyaar_run AS
SELECT gen_random_uuid() AS run_id;

SELECT run_id AS current_validation_run
FROM _meyaar_run;


-- ============================================================
-- BUILDINGS
-- ============================================================


-- ============================================================
-- BLD004 — Missing Geometry
-- ============================================================

INSERT INTO public.validation_results
(
    run_id,
    layer_name,
    feature_id,
    rule_id,
    error_type,
    severity,
    details
)

SELECT
    r.run_id,
    'buildings',
    COALESCE(b.feature_id, b.id::text),
    'BLD004',
    'Missing Geometry',
    'critical',
    'Building geometry is NULL or empty.'

FROM public.buildings b
CROSS JOIN _meyaar_run r

WHERE b.geometry IS NULL
   OR ST_IsEmpty(b.geometry);


-- ============================================================
-- BLD003 — Invalid Geometry
-- ============================================================

INSERT INTO public.validation_results
(
    run_id,
    layer_name,
    feature_id,
    rule_id,
    error_type,
    severity,
    details
)

SELECT
    r.run_id,
    'buildings',
    COALESCE(b.feature_id, b.id::text),
    'BLD003',
    'Invalid Geometry',
    'high',
    ST_IsValidReason(b.geometry)

FROM public.buildings b
CROSS JOIN _meyaar_run r

WHERE b.geometry IS NOT NULL
  AND NOT ST_IsEmpty(b.geometry)
  AND NOT ST_IsValid(b.geometry);


-- ============================================================
-- BLD002 — Duplicate Buildings
-- Exact geometry duplicates only
-- ============================================================

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
    run_id,
    layer_name,
    feature_id,
    rule_id,
    error_type,
    severity,
    details
)

SELECT
    r.run_id,
    'buildings',
    COALESCE(b.feature_id, b.id::text),
    'BLD002',
    'Duplicate Buildings',
    'medium',
    'Exact duplicate building geometry. Duplicate group size = '
        || d.duplicate_count::text

FROM public.buildings b

JOIN duplicate_groups d
    ON ST_AsEWKB(b.geometry) = d.geom_key

CROSS JOIN _meyaar_run r;


-- ============================================================
-- BLD001 — Building Overlap
-- Detects positive-area overlap between valid buildings.
-- Touching boundaries are NOT considered overlap.
-- ============================================================

WITH overlap_pairs AS (

    SELECT
        a.id AS internal_id_a,
        b.id AS internal_id_b,

        COALESCE(a.feature_id, a.id::text) AS feature_a,
        COALESCE(b.feature_id, b.id::text) AS feature_b,

        ST_Area(
            ST_Intersection(
                ST_Transform(a.geometry, 32638),
                ST_Transform(b.geometry, 32638)
            )
        ) AS overlap_area_m2

    FROM public.buildings a

    JOIN public.buildings b
      ON a.id < b.id
     AND a.geometry && b.geometry
     AND ST_Intersects(a.geometry, b.geometry)

    WHERE a.geometry IS NOT NULL
      AND b.geometry IS NOT NULL

      AND NOT ST_IsEmpty(a.geometry)
      AND NOT ST_IsEmpty(b.geometry)

      AND ST_IsValid(a.geometry)
      AND ST_IsValid(b.geometry)

      AND ST_SRID(a.geometry) = 4326
      AND ST_SRID(b.geometry) = 4326

      AND NOT ST_Touches(a.geometry, b.geometry)
      AND NOT ST_Equals(a.geometry, b.geometry)
)

INSERT INTO public.validation_results
(
    run_id,
    layer_name,
    feature_id,
    rule_id,
    error_type,
    severity,
    details
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
        || ROUND(o.overlap_area_m2::numeric, 2)::text
        || ' m².'

FROM overlap_pairs o

CROSS JOIN _meyaar_run r

WHERE o.overlap_area_m2 > 0;


-- ============================================================
-- ROADS
-- ============================================================


-- ============================================================
-- RD005 — Missing Geometry
-- ============================================================

INSERT INTO public.validation_results
(
    run_id,
    layer_name,
    feature_id,
    rule_id,
    error_type,
    severity,
    details
)

SELECT
    r.run_id,
    'roads',
    COALESCE(rd.id, rd.ogc_fid::text),
    'RD005',
    'Missing Geometry',
    'critical',
    'Road geometry is NULL or empty.'

FROM public.roads rd
CROSS JOIN _meyaar_run r

WHERE rd.geometry IS NULL
   OR ST_IsEmpty(rd.geometry);


-- ============================================================
-- RD004 — Invalid Geometry
-- ============================================================

INSERT INTO public.validation_results
(
    run_id,
    layer_name,
    feature_id,
    rule_id,
    error_type,
    severity,
    details
)

SELECT
    r.run_id,
    'roads',
    COALESCE(rd.id, rd.ogc_fid::text),
    'RD004',
    'Invalid Geometry',
    'high',
    ST_IsValidReason(rd.geometry)

FROM public.roads rd
CROSS JOIN _meyaar_run r

WHERE rd.geometry IS NOT NULL
  AND NOT ST_IsEmpty(rd.geometry)
  AND NOT ST_IsValid(rd.geometry);


-- ============================================================
-- RD003 — Duplicate Roads
-- Exact geometry duplicates only
-- ============================================================

WITH duplicate_groups AS (

    SELECT
        ST_AsEWKB(geometry) AS geom_key,
        COUNT(*) AS duplicate_count

    FROM public.roads

    WHERE geometry IS NOT NULL
      AND NOT ST_IsEmpty(geometry)

    GROUP BY ST_AsEWKB(geometry)

    HAVING COUNT(*) > 1
)

INSERT INTO public.validation_results
(
    run_id,
    layer_name,
    feature_id,
    rule_id,
    error_type,
    severity,
    details
)

SELECT
    r.run_id,
    'roads',
    COALESCE(rd.id, rd.ogc_fid::text),
    'RD003',
    'Duplicate Roads',
    'medium',

    'Exact duplicate road geometry. Duplicate group size = '
        || d.duplicate_count::text

FROM public.roads rd

JOIN duplicate_groups d
    ON ST_AsEWKB(rd.geometry) = d.geom_key

CROSS JOIN _meyaar_run r;


-- ============================================================
-- ROAD TOPOLOGY PREPARATION
--
-- Convert each road part from EPSG:4326 to EPSG:32638
-- so distances can be measured in meters.
-- ============================================================

DROP TABLE IF EXISTS _road_parts_metric;

CREATE TEMP TABLE _road_parts_metric AS

SELECT
    rd.ogc_fid,

    rd.id AS source_id,

    d.path[1] AS part_no,

    d.geom::geometry(LineString, 32638) AS geometry

FROM public.roads rd

CROSS JOIN LATERAL
    ST_Dump(
        ST_Transform(rd.geometry, 32638)
    ) AS d

WHERE rd.geometry IS NOT NULL
  AND NOT ST_IsEmpty(rd.geometry)
  AND ST_SRID(rd.geometry) = 4326;


CREATE INDEX idx_road_parts_metric_geom
    ON _road_parts_metric
    USING GIST (geometry);

ANALYZE _road_parts_metric;


-- ============================================================
-- Extract start/end points of every road part
-- ============================================================

DROP TABLE IF EXISTS _road_endpoints;

CREATE TEMP TABLE _road_endpoints AS

SELECT
    ogc_fid,
    source_id,
    part_no,
    'start'::text AS endpoint_type,
    ST_StartPoint(geometry)::geometry(Point, 32638) AS geometry

FROM _road_parts_metric

WHERE ST_Length(geometry) > 0


UNION ALL


SELECT
    ogc_fid,
    source_id,
    part_no,
    'end'::text AS endpoint_type,
    ST_EndPoint(geometry)::geometry(Point, 32638)

FROM _road_parts_metric

WHERE ST_Length(geometry) > 0;


CREATE INDEX idx_road_endpoints_geom
    ON _road_endpoints
    USING GIST (geometry);

ANALYZE _road_endpoints;


-- ============================================================
-- RD002 — Road Undershoot
--
-- A road endpoint stops within 5 meters of another road
-- without actually touching it.
--
-- NOTE:
-- This is a spatial heuristic candidate rule.
-- ============================================================

WITH undershoot_candidates AS (

    SELECT
        e.ogc_fid,
        e.source_id,
        e.part_no,
        e.endpoint_type,

        n.nearby_road_fid,
        n.nearby_source_id,
        n.distance_m

    FROM _road_endpoints e

    CROSS JOIN LATERAL (

        SELECT
            r2.ogc_fid AS nearby_road_fid,
            r2.source_id AS nearby_source_id,

            ST_Distance(
                e.geometry,
                r2.geometry
            ) AS distance_m

        FROM _road_parts_metric r2

        WHERE r2.ogc_fid <> e.ogc_fid

          AND ST_DWithin(
                e.geometry,
                r2.geometry,
                5.0
              )

          -- Endpoint must NOT already touch the road.
          AND ST_Distance(
                e.geometry,
                r2.geometry
              ) > 0.05

        ORDER BY
            ST_Distance(
                e.geometry,
                r2.geometry
            )

        LIMIT 1

    ) n
)

INSERT INTO public.validation_results
(
    run_id,
    layer_name,
    feature_id,
    rule_id,
    error_type,
    severity,
    details
)

SELECT
    r.run_id,

    'roads',

    COALESCE(
        u.source_id,
        u.ogc_fid::text
    ),

    'RD002',

    'Road Undershoot',

    'high',

    'Road '
        || u.endpoint_type
        || ' endpoint stops '
        || ROUND(u.distance_m::numeric, 2)::text
        || ' m before nearby road '
        || COALESCE(
               u.nearby_source_id,
               u.nearby_road_fid::text
           )
        || '.'

FROM undershoot_candidates u

CROSS JOIN _meyaar_run r;


-- ============================================================
-- RD001 — Road Overshoot
--
-- Detects a road whose endpoint continues a short distance
-- beyond an intersection with another road.
--
-- Maximum tail length = 5 meters.
--
-- NOTE:
-- This is a spatial heuristic candidate rule.
-- ============================================================

WITH road_intersections AS (

    SELECT
        a.ogc_fid AS road_fid,
        a.source_id,

        a.part_no,

        b.ogc_fid AS crossing_road_fid,
        b.source_id AS crossing_source_id,

        (p).geom::geometry(Point, 32638)
            AS intersection_point,

        ST_LineLocatePoint(
            a.geometry,
            (p).geom
        ) AS fraction,

        ST_Length(a.geometry)
            AS road_length_m

    FROM _road_parts_metric a

    JOIN _road_parts_metric b

      ON a.ogc_fid <> b.ogc_fid

     AND a.geometry && b.geometry

     AND ST_Intersects(
            a.geometry,
            b.geometry
         )

    CROSS JOIN LATERAL

        ST_Dump(

            ST_CollectionExtract(

                ST_Intersection(
                    a.geometry,
                    b.geometry
                ),

                1
            )

        ) AS p

    WHERE ST_Length(a.geometry) > 0
),

tails AS (

    SELECT
        road_fid,
        source_id,
        part_no,

        crossing_road_fid,
        crossing_source_id,

        CASE
            WHEN fraction <= 0.5
                THEN 'start'
            ELSE 'end'
        END AS endpoint_type,

        LEAST(
            fraction * road_length_m,
            (1.0 - fraction) * road_length_m
        ) AS tail_m

    FROM road_intersections

    WHERE fraction > 0
      AND fraction < 1
),

best_candidates AS (

    SELECT DISTINCT ON
    (
        road_fid,
        part_no,
        endpoint_type
    )

        road_fid,
        source_id,
        part_no,

        crossing_road_fid,
        crossing_source_id,

        endpoint_type,
        tail_m

    FROM tails

    WHERE tail_m > 0.05
      AND tail_m <= 5.0

    ORDER BY
        road_fid,
        part_no,
        endpoint_type,
        tail_m
)

INSERT INTO public.validation_results
(
    run_id,
    layer_name,
    feature_id,
    rule_id,
    error_type,
    severity,
    details
)

SELECT
    r.run_id,

    'roads',

    COALESCE(
        o.source_id,
        o.road_fid::text
    ),

    'RD001',

    'Road Overshoot',

    'high',

    'Road continues '
        || ROUND(o.tail_m::numeric, 2)::text
        || ' m past intersection with road '
        || COALESCE(
               o.crossing_source_id,
               o.crossing_road_fid::text
           )
        || '.'

FROM best_candidates o

CROSS JOIN _meyaar_run r;


-- ============================================================
-- GENERAL GIS RULES
-- ============================================================


-- ============================================================
-- GIS001 — Missing/Wrong CRS
-- Expected CRS = EPSG:4326
-- ============================================================

DO $$

DECLARE

    v_run UUID;

    v_roads_srid INTEGER;
    v_buildings_srid INTEGER;

    expected_srid CONSTANT INTEGER := 4326;

BEGIN

    SELECT run_id
    INTO v_run
    FROM _meyaar_run
    LIMIT 1;


    SELECT Find_SRID(
        'public',
        'roads',
        'geometry'
    )
    INTO v_roads_srid;


    SELECT Find_SRID(
        'public',
        'buildings',
        'geometry'
    )
    INTO v_buildings_srid;


    IF COALESCE(v_roads_srid, 0) <> expected_srid THEN

        INSERT INTO public.validation_results
        (
            run_id,
            layer_name,
            feature_id,
            rule_id,
            error_type,
            severity,
            details
        )

        VALUES
        (
            v_run,
            'roads',
            NULL,
            'GIS001',
            'Missing/Wrong CRS',
            'critical',

            'Expected EPSG:'
                || expected_srid::text
                || ', found SRID '
                || COALESCE(
                       v_roads_srid::text,
                       'missing/unknown'
                   )
                || '.'
        );

    END IF;


    IF COALESCE(v_buildings_srid, 0) <> expected_srid THEN

        INSERT INTO public.validation_results
        (
            run_id,
            layer_name,
            feature_id,
            rule_id,
            error_type,
            severity,
            details
        )

        VALUES
        (
            v_run,
            'buildings',
            NULL,
            'GIS001',
            'Missing/Wrong CRS',
            'critical',

            'Expected EPSG:'
                || expected_srid::text
                || ', found SRID '
                || COALESCE(
                       v_buildings_srid::text,
                       'missing/unknown'
                   )
                || '.'
        );

    END IF;

END $$;


-- ============================================================
-- GIS002 — Invalid Coordinates
-- EPSG:4326 valid:
-- Longitude -180 to 180
-- Latitude  -90 to 90
-- ============================================================


-- ROADS

INSERT INTO public.validation_results
(
    run_id,
    layer_name,
    feature_id,
    rule_id,
    error_type,
    severity,
    details
)

SELECT
    r.run_id,

    'roads',

    COALESCE(
        rd.id,
        rd.ogc_fid::text
    ),

    'GIS002',

    'Invalid Coordinates',

    'critical',

    'Coordinates fall outside valid EPSG:4326 longitude/latitude ranges.'

FROM public.roads rd

CROSS JOIN _meyaar_run r

WHERE rd.geometry IS NOT NULL
  AND NOT ST_IsEmpty(rd.geometry)

  AND
  (
       ST_XMin(ST_Envelope(rd.geometry)) < -180

    OR ST_XMax(ST_Envelope(rd.geometry)) > 180

    OR ST_YMin(ST_Envelope(rd.geometry)) < -90

    OR ST_YMax(ST_Envelope(rd.geometry)) > 90
  );


-- BUILDINGS

INSERT INTO public.validation_results
(
    run_id,
    layer_name,
    feature_id,
    rule_id,
    error_type,
    severity,
    details
)

SELECT
    r.run_id,

    'buildings',

    COALESCE(
        b.feature_id,
        b.id::text
    ),

    'GIS002',

    'Invalid Coordinates',

    'critical',

    'Coordinates fall outside valid EPSG:4326 longitude/latitude ranges.'

FROM public.buildings b

CROSS JOIN _meyaar_run r

WHERE b.geometry IS NOT NULL
  AND NOT ST_IsEmpty(b.geometry)

  AND
  (
       ST_XMin(ST_Envelope(b.geometry)) < -180

    OR ST_XMax(ST_Envelope(b.geometry)) > 180

    OR ST_YMin(ST_Envelope(b.geometry)) < -90

    OR ST_YMax(ST_Envelope(b.geometry)) > 90
  );


-- ============================================================
-- GIS003 — Missing Required Attributes
-- ============================================================

DO $$

DECLARE

    cfg RECORD;

    v_run UUID;

    column_exists BOOLEAN;

    id_column TEXT;

    sql_text TEXT;

BEGIN

    SELECT run_id
    INTO v_run
    FROM _meyaar_run
    LIMIT 1;


    FOR cfg IN

        SELECT
            layer_name,
            column_name

        FROM public.meyaar_required_attributes

        WHERE layer_name IN (
            'roads',
            'buildings'
        )

    LOOP


        id_column :=
            CASE cfg.layer_name

                WHEN 'roads'
                    THEN 'id'

                WHEN 'buildings'
                    THEN 'feature_id'

            END;


        SELECT EXISTS (

            SELECT 1

            FROM information_schema.columns

            WHERE table_schema = 'public'

              AND table_name =
                    cfg.layer_name

              AND column_name =
                    cfg.column_name

        )
        INTO column_exists;


        IF NOT column_exists THEN


            INSERT INTO public.validation_results
            (
                run_id,
                layer_name,
                feature_id,
                rule_id,
                error_type,
                severity,
                details
            )

            VALUES
            (
                v_run,

                cfg.layer_name,

                NULL,

                'GIS003',

                'Missing Required Attributes',

                'high',

                'Required column "'
                    || cfg.column_name
                    || '" does not exist.'
            );


        ELSE


            sql_text := format(

                'INSERT INTO public.validation_results

                 (
                    run_id,
                    layer_name,
                    feature_id,
                    rule_id,
                    error_type,
                    severity,
                    details
                 )

                 SELECT

                    %L::uuid,

                    %L,

                    %I::text,

                    ''GIS003'',

                    ''Missing Required Attributes'',

                    ''high'',

                    ''Required attribute "%s" is NULL or blank.''

                 FROM public.%I

                 WHERE %I IS NULL

                    OR btrim(%I::text) = ''''',

                v_run::text,

                cfg.layer_name,

                id_column,

                cfg.column_name,

                cfg.layer_name,

                cfg.column_name,

                cfg.column_name
            );


            EXECUTE sql_text;


        END IF;


    END LOOP;

END $$;


-- ============================================================
-- GIS004 — Wrong Data Type
-- ============================================================

INSERT INTO public.validation_results
(
    run_id,
    layer_name,
    feature_id,
    rule_id,
    error_type,
    severity,
    details
)

SELECT
    r.run_id,

    cfg.layer_name,

    NULL,

    'GIS004',

    'Wrong Data Type',

    'medium',

    'Column "'
        || cfg.column_name
        || '" expected type "'
        || cfg.expected_type
        || '" but found "'
        || COALESCE(
               c.data_type,
               'missing column'
           )
        || '".'

FROM public.meyaar_expected_types cfg

CROSS JOIN _meyaar_run r

LEFT JOIN information_schema.columns c

  ON c.table_schema = 'public'

 AND c.table_name =
        cfg.layer_name

 AND c.column_name =
        cfg.column_name

WHERE cfg.layer_name IN (
        'roads',
        'buildings'
      )

AND
(
       c.column_name IS NULL

    OR lower(c.data_type)
       <> lower(cfg.expected_type)
);


-- ============================================================
-- GIS005 — Invalid Attribute Values
-- ============================================================

DO $$

DECLARE

    cfg RECORD;

    v_run UUID;

    column_exists BOOLEAN;

    id_column TEXT;

    sql_text TEXT;

BEGIN


    SELECT run_id
    INTO v_run
    FROM _meyaar_run
    LIMIT 1;


    FOR cfg IN

        SELECT DISTINCT
            layer_name,
            column_name

        FROM public.meyaar_allowed_values

        WHERE layer_name IN (
            'roads',
            'buildings'
        )

    LOOP


        id_column :=
            CASE cfg.layer_name

                WHEN 'roads'
                    THEN 'id'

                WHEN 'buildings'
                    THEN 'feature_id'

            END;


        SELECT EXISTS (

            SELECT 1

            FROM information_schema.columns

            WHERE table_schema = 'public'

              AND table_name =
                    cfg.layer_name

              AND column_name =
                    cfg.column_name

        )
        INTO column_exists;


        IF column_exists THEN


            sql_text := format(

                'INSERT INTO public.validation_results

                 (
                    run_id,
                    layer_name,
                    feature_id,
                    rule_id,
                    error_type,
                    severity,
                    details
                 )

                 SELECT

                    %L::uuid,

                    %L,

                    %I::text,

                    ''GIS005'',

                    ''Invalid Attribute Values'',

                    ''medium'',

                    ''Invalid value "''
                        || %I::text
                        || ''" in attribute "%s".''

                 FROM public.%I

                 WHERE %I IS NOT NULL

                   AND NOT EXISTS
                   (
                       SELECT 1

                       FROM public.meyaar_allowed_values av

                       WHERE av.layer_name = %L

                         AND av.column_name = %L

                         AND av.allowed_value =
                             %I::text
                   )',

                v_run::text,

                cfg.layer_name,

                id_column,

                cfg.column_name,

                cfg.column_name,

                cfg.layer_name,

                cfg.column_name,

                cfg.layer_name,

                cfg.column_name,

                cfg.column_name
            );


            EXECUTE sql_text;


        END IF;


    END LOOP;

END $$;


-- ============================================================
-- 5) SUMMARY REPORT FOR CURRENT RUN
-- ============================================================

SELECT

    rule_id,

    layer_name,

    error_type,

    severity,

    COUNT(*) AS errors_found

FROM public.validation_results

WHERE run_id = (
    SELECT run_id
    FROM _meyaar_run
    LIMIT 1
)

GROUP BY

    rule_id,
    layer_name,
    error_type,
    severity

ORDER BY

    rule_id,
    layer_name;


-- ============================================================
-- 6) SAMPLE ERROR REPORT
-- Shows only 500 rows.
-- Full results remain in validation_results.
-- ============================================================

SELECT

    result_id,

    run_id,

    layer_name,

    feature_id,

    rule_id,

    error_type,

    severity,

    details,

    detected_at

FROM public.validation_results

WHERE run_id = (
    SELECT run_id
    FROM _meyaar_run
    LIMIT 1
)

ORDER BY
    rule_id,
    layer_name,
    feature_id

LIMIT 500;