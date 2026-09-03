-- ============================================================
-- MEYAAR - ROADS RULES
-- RD001-RD005
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_roads_geometry
    ON public.roads USING GIST (geometry);

ANALYZE public.roads;


-- RD005 — Missing Geometry
INSERT INTO public.validation_results
(
    run_id, layer_name, feature_id,
    rule_id, error_type, severity, details
)
SELECT
    r.run_id,
    'roads',
    rd.feature_id::text,
    'RD005',
    'Missing Geometry',
    'critical',
    'Road geometry is NULL or empty.'
FROM public.roads rd
CROSS JOIN _meyaar_run r
WHERE rd.geometry IS NULL
   OR ST_IsEmpty(rd.geometry);


-- RD004 — Invalid Geometry
INSERT INTO public.validation_results
(
    run_id, layer_name, feature_id,
    rule_id, error_type, severity, details
)
SELECT
    r.run_id,
    'roads',
    rd.feature_id::text,
    'RD004',
    'Invalid Geometry',
    'high',
    ST_IsValidReason(rd.geometry)
FROM public.roads rd
CROSS JOIN _meyaar_run r
WHERE rd.geometry IS NOT NULL
  AND NOT ST_IsEmpty(rd.geometry)
  AND NOT ST_IsValid(rd.geometry);


-- RD003 — Duplicate Roads
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
    run_id, layer_name, feature_id,
    rule_id, error_type, severity, details
)
SELECT
    r.run_id,
    'roads',
    rd.feature_id::text,
    'RD003',
    'Duplicate Roads',
    'medium',
    'Exact duplicate road geometry. Duplicate group size = '
        || d.duplicate_count::text
FROM public.roads rd
JOIN duplicate_groups d
    ON ST_AsEWKB(rd.geometry) = d.geom_key
CROSS JOIN _meyaar_run r;


-- Prepare road parts in meters
DROP TABLE IF EXISTS _road_parts_metric;

CREATE TEMP TABLE _road_parts_metric AS
SELECT
    rd.feature_id::text AS road_id,
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


-- Road endpoints
DROP TABLE IF EXISTS _road_endpoints;

CREATE TEMP TABLE _road_endpoints AS
SELECT
    road_id,
    part_no,
    'start' AS endpoint_type,
    ST_StartPoint(geometry)::geometry(Point, 32638) AS geometry
FROM _road_parts_metric
WHERE ST_Length(geometry) > 0

UNION ALL

SELECT
    road_id,
    part_no,
    'end' AS endpoint_type,
    ST_EndPoint(geometry)::geometry(Point, 32638)
FROM _road_parts_metric
WHERE ST_Length(geometry) > 0;

CREATE INDEX idx_road_endpoints_geom
    ON _road_endpoints
    USING GIST (geometry);


-- RD002 — Undershoot
WITH undershoot_candidates AS (
    SELECT
        e.road_id,
        e.part_no,
        e.endpoint_type,
        n.nearby_road_id,
        n.distance_m
    FROM _road_endpoints e

    CROSS JOIN LATERAL (
        SELECT
            r2.road_id AS nearby_road_id,
            ST_Distance(
                e.geometry,
                r2.geometry
            ) AS distance_m

        FROM _road_parts_metric r2

        WHERE r2.road_id <> e.road_id
          AND ST_DWithin(
                e.geometry,
                r2.geometry,
                5.0
              )
          AND ST_Distance(
                e.geometry,
                r2.geometry
              ) > 0.05

        ORDER BY ST_Distance(
            e.geometry,
            r2.geometry
        )

        LIMIT 1
    ) n
)

INSERT INTO public.validation_results
(
    run_id, layer_name, feature_id,
    rule_id, error_type, severity, details
)

SELECT
    r.run_id,
    'roads',
    u.road_id,
    'RD002',
    'Road Undershoot',
    'high',
    'Road '
        || u.endpoint_type
        || ' endpoint stops '
        || ROUND(u.distance_m::numeric, 2)::text
        || ' m before nearby road '
        || u.nearby_road_id
        || '.'

FROM undershoot_candidates u
CROSS JOIN _meyaar_run r;


-- RD001 — Overshoot
WITH road_intersections AS (
    SELECT
        a.road_id,
        a.part_no,

        b.road_id AS crossing_road_id,

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
      ON a.road_id <> b.road_id
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
        road_id,
        part_no,
        crossing_road_id,

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
        road_id,
        part_no,
        endpoint_type
    )
        road_id,
        part_no,
        crossing_road_id,
        endpoint_type,
        tail_m

    FROM tails

    WHERE tail_m > 0.05
      AND tail_m <= 5.0

    ORDER BY
        road_id,
        part_no,
        endpoint_type,
        tail_m
)

INSERT INTO public.validation_results
(
    run_id, layer_name, feature_id,
    rule_id, error_type, severity, details
)

SELECT
    r.run_id,
    'roads',
    o.road_id,
    'RD001',
    'Road Overshoot',
    'high',
    'Road continues '
        || ROUND(o.tail_m::numeric, 2)::text
        || ' m past intersection with road '
        || o.crossing_road_id
        || '.'

FROM best_candidates o
CROSS JOIN _meyaar_run r;