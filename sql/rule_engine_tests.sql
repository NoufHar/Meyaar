-- ============================================================
-- MEYAAR RULE ENGINE TEST SUITE
-- Controlled Error Injection
-- Does NOT modify production tables
-- ============================================================

CREATE EXTENSION IF NOT EXISTS postgis;

DROP SCHEMA IF EXISTS meyaar_test CASCADE;
CREATE SCHEMA meyaar_test;

CREATE TABLE meyaar_test.results (
    rule_id TEXT,
    test_name TEXT,
    status TEXT,
    details TEXT
);

-- ============================================================
-- BUILDING TEST DATA
-- ============================================================

CREATE TABLE meyaar_test.buildings (
    id SERIAL PRIMARY KEY,
    feature_id TEXT,
    name TEXT,
    geometry geometry(Polygon, 4326)
);

-- BLD001: two overlapping buildings
INSERT INTO meyaar_test.buildings (feature_id, name, geometry)
VALUES
(
    'TEST_BLD001_A',
    'Overlap A',
    ST_GeomFromText(
        'POLYGON((46.7000 24.6000,
                  46.7010 24.6000,
                  46.7010 24.6010,
                  46.7000 24.6010,
                  46.7000 24.6000))',
        4326
    )
),
(
    'TEST_BLD001_B',
    'Overlap B',
    ST_GeomFromText(
        'POLYGON((46.7005 24.6005,
                  46.7015 24.6005,
                  46.7015 24.6015,
                  46.7005 24.6015,
                  46.7005 24.6005))',
        4326
    )
);

-- BLD002: exact duplicate buildings
INSERT INTO meyaar_test.buildings (feature_id, name, geometry)
VALUES
(
    'TEST_BLD002_A',
    'Duplicate A',
    ST_GeomFromText(
        'POLYGON((46.7100 24.6000,
                  46.7110 24.6000,
                  46.7110 24.6010,
                  46.7100 24.6010,
                  46.7100 24.6000))',
        4326
    )
),
(
    'TEST_BLD002_B',
    'Duplicate B',
    ST_GeomFromText(
        'POLYGON((46.7100 24.6000,
                  46.7110 24.6000,
                  46.7110 24.6010,
                  46.7100 24.6010,
                  46.7100 24.6000))',
        4326
    )
);

-- BLD003: self-intersection
INSERT INTO meyaar_test.buildings
(feature_id, name, geometry)
VALUES
(
    'TEST_BLD003',
    'Invalid Geometry',
    ST_GeomFromText(
        'POLYGON((46.7200 24.6000,
                  46.7210 24.6010,
                  46.7200 24.6010,
                  46.7210 24.6000,
                  46.7200 24.6000))',
        4326
    )
);

-- BLD004: missing geometry
INSERT INTO meyaar_test.buildings
(feature_id, name, geometry)
VALUES
(
    'TEST_BLD004',
    'Missing Geometry',
    NULL
);


-- ============================================================
-- BLD001 TEST
-- ============================================================

INSERT INTO meyaar_test.results
SELECT
    'BLD001',
    'Building Overlap',
    CASE
        WHEN EXISTS (
            SELECT 1
            FROM meyaar_test.buildings a
            JOIN meyaar_test.buildings b
              ON a.id < b.id
             AND ST_Intersects(a.geometry, b.geometry)
            WHERE a.feature_id = 'TEST_BLD001_A'
              AND b.feature_id = 'TEST_BLD001_B'
              AND NOT ST_Touches(a.geometry, b.geometry)
              AND ST_Area(
                    ST_Intersection(
                        ST_Transform(a.geometry, 32638),
                        ST_Transform(b.geometry, 32638)
                    )
                  ) > 0
        )
        THEN 'PASS'
        ELSE 'FAIL'
    END,
    'Two buildings intentionally overlap.';


-- ============================================================
-- BLD002 TEST
-- ============================================================

INSERT INTO meyaar_test.results
SELECT
    'BLD002',
    'Duplicate Buildings',
    CASE
        WHEN (
            SELECT COUNT(*)
            FROM meyaar_test.buildings
            WHERE ST_AsEWKB(geometry) =
            (
                SELECT ST_AsEWKB(geometry)
                FROM meyaar_test.buildings
                WHERE feature_id = 'TEST_BLD002_A'
            )
        ) >= 2
        THEN 'PASS'
        ELSE 'FAIL'
    END,
    'Two buildings have exactly the same geometry.';


-- ============================================================
-- BLD003 TEST
-- ============================================================

INSERT INTO meyaar_test.results
SELECT
    'BLD003',
    'Invalid Geometry',
    CASE
        WHEN NOT ST_IsValid(geometry)
        THEN 'PASS'
        ELSE 'FAIL'
    END,
    ST_IsValidReason(geometry)
FROM meyaar_test.buildings
WHERE feature_id = 'TEST_BLD003';


-- ============================================================
-- BLD004 TEST
-- ============================================================

INSERT INTO meyaar_test.results
SELECT
    'BLD004',
    'Missing Geometry',
    CASE
        WHEN geometry IS NULL OR ST_IsEmpty(geometry)
        THEN 'PASS'
        ELSE 'FAIL'
    END,
    'Geometry intentionally set to NULL.'
FROM meyaar_test.buildings
WHERE feature_id = 'TEST_BLD004';


-- ============================================================
-- ROAD TEST TABLE - Metric CRS for topology tests
-- ============================================================

CREATE TABLE meyaar_test.roads_metric (
    id SERIAL PRIMARY KEY,
    feature_id TEXT,
    geometry geometry(LineString, 32638)
);


-- RD001 Overshoot:
-- Road A crosses Road B and continues 3 meters beyond it.

INSERT INTO meyaar_test.roads_metric
(feature_id, geometry)
VALUES
(
    'TEST_RD001_A',
    ST_GeomFromText(
        'LINESTRING(500000 2700000, 500103 2700000)',
        32638
    )
),
(
    'TEST_RD001_B',
    ST_GeomFromText(
        'LINESTRING(500100 2699950, 500100 2700050)',
        32638
    )
);


-- RD002 Undershoot:
-- Road A stops 3 meters before Road B.

INSERT INTO meyaar_test.roads_metric
(feature_id, geometry)
VALUES
(
    'TEST_RD002_A',
    ST_GeomFromText(
        'LINESTRING(500200 2700000, 500297 2700000)',
        32638
    )
),
(
    'TEST_RD002_B',
    ST_GeomFromText(
        'LINESTRING(500300 2699950, 500300 2700050)',
        32638
    )
);


-- RD003 Duplicate Roads

INSERT INTO meyaar_test.roads_metric
(feature_id, geometry)
VALUES
(
    'TEST_RD003_A',
    ST_GeomFromText(
        'LINESTRING(500400 2700000, 500500 2700000)',
        32638
    )
),
(
    'TEST_RD003_B',
    ST_GeomFromText(
        'LINESTRING(500400 2700000, 500500 2700000)',
        32638
    )
);


-- RD005 Missing Geometry

INSERT INTO meyaar_test.roads_metric
(feature_id, geometry)
VALUES
(
    'TEST_RD005',
    NULL
);


-- ============================================================
-- RD001 TEST — Overshoot
-- ============================================================

INSERT INTO meyaar_test.results
SELECT
    'RD001',
    'Road Overshoot',

    CASE
        WHEN EXISTS (

            SELECT 1

            FROM meyaar_test.roads_metric a
            JOIN meyaar_test.roads_metric b
              ON a.feature_id = 'TEST_RD001_A'
             AND b.feature_id = 'TEST_RD001_B'
             AND ST_Intersects(a.geometry, b.geometry)

            CROSS JOIN LATERAL (
                SELECT
                    ST_LineLocatePoint(
                        a.geometry,
                        ST_Intersection(a.geometry, b.geometry)
                    ) AS fraction
            ) x

            WHERE LEAST(
                x.fraction * ST_Length(a.geometry),
                (1 - x.fraction) * ST_Length(a.geometry)
            ) BETWEEN 0.05 AND 5.0

        )
        THEN 'PASS'
        ELSE 'FAIL'
    END,

    'Road intentionally continues 3 m past intersection.';


-- ============================================================
-- RD002 TEST — Undershoot
-- ============================================================

INSERT INTO meyaar_test.results
SELECT
    'RD002',
    'Road Undershoot',

    CASE
        WHEN EXISTS (

            SELECT 1

            FROM meyaar_test.roads_metric a
            JOIN meyaar_test.roads_metric b
              ON a.feature_id = 'TEST_RD002_A'
             AND b.feature_id = 'TEST_RD002_B'

            WHERE ST_DWithin(
                ST_EndPoint(a.geometry),
                b.geometry,
                5
            )

            AND ST_Distance(
                ST_EndPoint(a.geometry),
                b.geometry
            ) > 0.05

        )
        THEN 'PASS'
        ELSE 'FAIL'
    END,

    'Road intentionally stops 3 m before nearby road.';


-- ============================================================
-- RD003 TEST
-- ============================================================

INSERT INTO meyaar_test.results
SELECT
    'RD003',
    'Duplicate Roads',

    CASE
        WHEN (
            SELECT COUNT(*)

            FROM meyaar_test.roads_metric

            WHERE ST_AsEWKB(geometry) =
            (
                SELECT ST_AsEWKB(geometry)

                FROM meyaar_test.roads_metric

                WHERE feature_id = 'TEST_RD003_A'
            )
        ) >= 2
        THEN 'PASS'
        ELSE 'FAIL'
    END,

    'Two roads have exactly identical geometry.';


-- ============================================================
-- RD004 TEST — Invalid Road Geometry
--
-- IMPORTANT:
-- ST_IsValid has limited usefulness for LineStrings.
-- This test records whether PostGIS considers the test line invalid.
-- ============================================================

CREATE TABLE meyaar_test.road_invalid_test (
    feature_id TEXT,
    geometry geometry(LineString, 4326)
);

INSERT INTO meyaar_test.road_invalid_test
VALUES
(
    'TEST_RD004',
    ST_GeomFromText(
        'LINESTRING(46.7 24.6, 46.7 24.6)',
        4326
    )
);

INSERT INTO meyaar_test.results
SELECT
    'RD004',
    'Invalid Road Geometry',

    CASE
        WHEN NOT ST_IsValid(geometry)
        THEN 'PASS'
        ELSE 'FAIL'
    END,

    ST_IsValidReason(geometry)

FROM meyaar_test.road_invalid_test;


-- ============================================================
-- RD005 TEST
-- ============================================================

INSERT INTO meyaar_test.results
SELECT
    'RD005',
    'Missing Road Geometry',

    CASE
        WHEN geometry IS NULL OR ST_IsEmpty(geometry)
        THEN 'PASS'
        ELSE 'FAIL'
    END,

    'Road geometry intentionally set to NULL.'

FROM meyaar_test.roads_metric

WHERE feature_id = 'TEST_RD005';


-- ============================================================
-- GIS001 — Wrong CRS
-- ============================================================

CREATE TABLE meyaar_test.wrong_crs (
    id SERIAL,
    geometry geometry(Point, 3857)
);

INSERT INTO meyaar_test.wrong_crs (geometry)
VALUES (
    ST_SetSRID(
        ST_MakePoint(500000, 2700000),
        3857
    )
);

INSERT INTO meyaar_test.results
SELECT
    'GIS001',
    'Missing/Wrong CRS',

    CASE
        WHEN Find_SRID(
            'meyaar_test',
            'wrong_crs',
            'geometry'
        ) <> 4326
        THEN 'PASS'
        ELSE 'FAIL'
    END,

    'Expected EPSG:4326; test layer uses EPSG:3857.';


-- ============================================================
-- GIS002 — Invalid Coordinates
-- ============================================================

CREATE TABLE meyaar_test.invalid_coordinates (
    id SERIAL,
    geometry geometry(Point, 4326)
);

INSERT INTO meyaar_test.invalid_coordinates (geometry)
VALUES (
    ST_SetSRID(
        ST_MakePoint(200, 95),
        4326
    )
);

INSERT INTO meyaar_test.results
SELECT
    'GIS002',
    'Invalid Coordinates',

    CASE
        WHEN ST_X(geometry) < -180
          OR ST_X(geometry) > 180
          OR ST_Y(geometry) < -90
          OR ST_Y(geometry) > 90
        THEN 'PASS'
        ELSE 'FAIL'
    END,

    'Injected coordinate = longitude 200, latitude 95.'

FROM meyaar_test.invalid_coordinates;


-- ============================================================
-- GIS003 — Missing Required Attribute
-- ============================================================

CREATE TABLE meyaar_test.attributes (
    id SERIAL,
    required_name TEXT,
    road_class TEXT,
    status TEXT
);

INSERT INTO meyaar_test.attributes
(required_name, road_class, status)
VALUES
(
    NULL,
    '123',
    'INVALID_VALUE'
);

INSERT INTO meyaar_test.results
SELECT
    'GIS003',
    'Missing Required Attributes',

    CASE
        WHEN required_name IS NULL
          OR btrim(required_name) = ''
        THEN 'PASS'
        ELSE 'FAIL'
    END,

    'Required attribute intentionally set to NULL.'

FROM meyaar_test.attributes
LIMIT 1;


-- ============================================================
-- GIS004 — Wrong Data Type
--
-- road_class is TEXT.
-- Test expects INTEGER.
-- ============================================================

INSERT INTO meyaar_test.results

SELECT
    'GIS004',
    'Wrong Data Type',

    CASE
        WHEN lower(data_type) <> 'integer'
        THEN 'PASS'
        ELSE 'FAIL'
    END,

    'Expected integer, actual type = ' || data_type

FROM information_schema.columns

WHERE table_schema = 'meyaar_test'
  AND table_name = 'attributes'
  AND column_name = 'road_class';


-- ============================================================
-- GIS005 — Invalid Attribute Value
--
-- Only ACTIVE and INACTIVE are allowed.
-- Test contains INVALID_VALUE.
-- ============================================================

CREATE TABLE meyaar_test.allowed_values (
    allowed_value TEXT PRIMARY KEY
);

INSERT INTO meyaar_test.allowed_values
VALUES
('ACTIVE'),
('INACTIVE');

INSERT INTO meyaar_test.results

SELECT
    'GIS005',
    'Invalid Attribute Values',

    CASE
        WHEN NOT EXISTS (

            SELECT 1

            FROM meyaar_test.allowed_values a

            WHERE a.allowed_value = t.status

        )
        THEN 'PASS'
        ELSE 'FAIL'
    END,

    'Injected value = ' || status ||
    '; allowed values = ACTIVE, INACTIVE.'

FROM meyaar_test.attributes t
LIMIT 1;


-- ============================================================
-- FINAL RESULTS
-- ============================================================

SELECT
    rule_id,
    test_name,
    status,
    details

FROM meyaar_test.results

ORDER BY
    CASE
        WHEN rule_id LIKE 'BLD%' THEN 1
        WHEN rule_id LIKE 'RD%'  THEN 2
        WHEN rule_id LIKE 'GIS%' THEN 3
    END,
    rule_id;


-- ============================================================
-- FINAL SCORE
-- ============================================================

SELECT
    COUNT(*) FILTER (WHERE status = 'PASS') AS passed,
    COUNT(*) FILTER (WHERE status = 'FAIL') AS failed,
    COUNT(*) AS total_tests

FROM meyaar_test.results;