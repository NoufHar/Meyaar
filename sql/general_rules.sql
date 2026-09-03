-- ============================================================
-- MEYAAR - GENERAL GIS RULES
-- GIS001-GIS005
-- Runs only on the selected layer.
-- Supported layers: roads, buildings
-- ============================================================


-- ============================================================
-- GIS001 — Missing / Wrong CRS
-- Expected CRS: EPSG:4326
-- ============================================================

DO $$
DECLARE
    v_run UUID;
    v_layer TEXT;
    v_srid INTEGER;
    expected_srid CONSTANT INTEGER := 4326;
BEGIN

    SELECT run_id
    INTO v_run
    FROM _meyaar_run
    LIMIT 1;

    SELECT layer_name
    INTO v_layer
    FROM _meyaar_context
    LIMIT 1;


    SELECT Find_SRID(
        'public',
        v_layer,
        'geometry'
    )
    INTO v_srid;


    IF COALESCE(v_srid, 0) <> expected_srid THEN

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
            v_layer,
            NULL,
            'GIS001',
            'Missing/Wrong CRS',
            'critical',

            'Expected EPSG:'
                || expected_srid::text
                || ', found SRID '
                || COALESCE(
                    v_srid::text,
                    'missing/unknown'
                )
                || '.'
        );

    END IF;

END $$;


-- ============================================================
-- GIS002 — Invalid Coordinates
--
-- Checks coordinates against valid EPSG:4326 ranges:
-- Longitude: -180 to 180
-- Latitude:  -90 to 90
-- ============================================================

DO $$
DECLARE
    v_run UUID;
    v_layer TEXT;
BEGIN

    SELECT run_id
    INTO v_run
    FROM _meyaar_run
    LIMIT 1;

    SELECT layer_name
    INTO v_layer
    FROM _meyaar_context
    LIMIT 1;


    -- --------------------------------------------------------
    -- Roads
    -- --------------------------------------------------------

    IF v_layer = 'roads' THEN

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
            v_run,
            'roads',
            rd.feature_id::text,
            'GIS002',
            'Invalid Coordinates',
            'critical',

            'Coordinates fall outside valid '
            || 'EPSG:4326 longitude/latitude ranges.'

        FROM public.roads rd

        WHERE rd.geometry IS NOT NULL
          AND NOT ST_IsEmpty(rd.geometry)

          AND
          (
               ST_XMin(
                   ST_Envelope(rd.geometry)
               ) < -180

            OR ST_XMax(
                   ST_Envelope(rd.geometry)
               ) > 180

            OR ST_YMin(
                   ST_Envelope(rd.geometry)
               ) < -90

            OR ST_YMax(
                   ST_Envelope(rd.geometry)
               ) > 90
          );


    -- --------------------------------------------------------
    -- Buildings
    -- --------------------------------------------------------

    ELSIF v_layer = 'buildings' THEN

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
            v_run,
            'buildings',
            b.feature_id::text,
            'GIS002',
            'Invalid Coordinates',
            'critical',

            'Coordinates fall outside valid '
            || 'EPSG:4326 longitude/latitude ranges.'

        FROM public.buildings b

        WHERE b.geometry IS NOT NULL
          AND NOT ST_IsEmpty(b.geometry)

          AND
          (
               ST_XMin(
                   ST_Envelope(b.geometry)
               ) < -180

            OR ST_XMax(
                   ST_Envelope(b.geometry)
               ) > 180

            OR ST_YMin(
                   ST_Envelope(b.geometry)
               ) < -90

            OR ST_YMax(
                   ST_Envelope(b.geometry)
               ) > 90
          );

    END IF;

END $$;


-- ============================================================
-- GIS003 — Missing Required Attributes
--
-- Requirements are read from:
-- public.meyaar_required_attributes
-- ============================================================

DO $$
DECLARE
    cfg RECORD;

    v_run UUID;
    v_layer TEXT;

    column_exists BOOLEAN;

    id_column TEXT;

    sql_text TEXT;

BEGIN

    SELECT run_id
    INTO v_run
    FROM _meyaar_run
    LIMIT 1;


    SELECT layer_name
    INTO v_layer
    FROM _meyaar_context
    LIMIT 1;


    -- Every Meyaar layer now uses the same ID column.
    id_column := 'feature_id';


    FOR cfg IN

        SELECT
            layer_name,
            column_name

        FROM public.meyaar_required_attributes

        WHERE layer_name = v_layer

    LOOP

        SELECT EXISTS
        (
            SELECT 1

            FROM information_schema.columns

            WHERE table_schema = 'public'

              AND table_name =
                  cfg.layer_name

              AND column_name =
                  cfg.column_name
        )

        INTO column_exists;


        -- ----------------------------------------------------
        -- Required column does not exist
        -- ----------------------------------------------------

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


        -- ----------------------------------------------------
        -- Column exists:
        -- find NULL / blank values
        -- ----------------------------------------------------

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

                    ''Required attribute "%s" '
                    || 'is NULL or blank.''

                 FROM public.%I

                 WHERE %I IS NULL

                    OR btrim(
                        %I::text
                    ) = ''''',

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
--
-- Expected types are read from:
-- public.meyaar_expected_types
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

CROSS JOIN _meyaar_context ctx

LEFT JOIN information_schema.columns c

    ON c.table_schema = 'public'

   AND c.table_name =
       cfg.layer_name

   AND c.column_name =
       cfg.column_name


WHERE cfg.layer_name =
      ctx.layer_name

  AND
  (
       c.column_name IS NULL

    OR lower(c.data_type)
       <> lower(cfg.expected_type)
  );


-- ============================================================
-- GIS005 — Invalid Attribute Values
--
-- Allowed values are read from:
-- public.meyaar_allowed_values
-- ============================================================

DO $$
DECLARE
    cfg RECORD;

    v_run UUID;
    v_layer TEXT;

    column_exists BOOLEAN;

    id_column TEXT;

    sql_text TEXT;

BEGIN

    SELECT run_id
    INTO v_run
    FROM _meyaar_run
    LIMIT 1;


    SELECT layer_name
    INTO v_layer
    FROM _meyaar_context
    LIMIT 1;


    -- Every layer uses feature_id.
    id_column := 'feature_id';


    FOR cfg IN

        SELECT DISTINCT
            layer_name,
            column_name

        FROM public.meyaar_allowed_values

        WHERE layer_name = v_layer

    LOOP

        SELECT EXISTS
        (
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