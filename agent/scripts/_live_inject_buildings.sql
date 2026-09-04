-- Inject deliberate building errors into public.buildings (only real columns).
-- BLD001 overlap: two polygons with positive-area intersection (~11 m boxes).
INSERT INTO public.buildings (feature_id, geometry)
SELECT 'BLD_INJ_A',
       ST_GeomFromText('POLYGON((46.70000 24.60000, 46.70010 24.60000, 46.70010 24.60010, 46.70000 24.60010, 46.70000 24.60000))', 4326)
WHERE NOT EXISTS (SELECT 1 FROM public.buildings WHERE feature_id='BLD_INJ_A');

INSERT INTO public.buildings (feature_id, geometry)
SELECT 'BLD_INJ_B',
       ST_GeomFromText('POLYGON((46.70005 24.60005, 46.70015 24.60005, 46.70015 24.60015, 46.70005 24.60015, 46.70005 24.60005))', 4326)
WHERE NOT EXISTS (SELECT 1 FROM public.buildings WHERE feature_id='BLD_INJ_B');

-- BLD002 duplicate: exact copy of an existing row.
INSERT INTO public.buildings (feature_id, geometry)
SELECT 'BLD_INJ_DUP', geometry FROM public.buildings
WHERE feature_id NOT LIKE 'BLD_INJ%' LIMIT 1
ON CONFLICT DO NOTHING;

-- BLD003 invalid geometry: self-intersecting bowtie polygon.
INSERT INTO public.buildings (feature_id, geometry)
SELECT 'BLD_INJ_BOW',
       ST_GeomFromText('POLYGON((46.70020 24.60000, 46.70030 24.60010, 46.70030 24.60000, 46.70020 24.60010, 46.70020 24.60000))', 4326)
WHERE NOT EXISTS (SELECT 1 FROM public.buildings WHERE feature_id='BLD_INJ_BOW');

-- BLD004 missing geometry.
INSERT INTO public.buildings (feature_id, geometry)
SELECT 'BLD_INJ_NULL', NULL
WHERE NOT EXISTS (SELECT 1 FROM public.buildings WHERE feature_id='BLD_INJ_NULL');
