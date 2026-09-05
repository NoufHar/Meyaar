-- Inject deliberate road errors into public.roads (sample table already there).
-- Duplicate (RD003): exact copy of one existing geometry, new feature_id.
INSERT INTO public.roads (feature_id, id, class, geometry)
SELECT 'RD_INJ_DUP', 999001, class, geometry
FROM public.roads LIMIT 1
ON CONFLICT DO NOTHING;

-- Invalid geometry (RD004): self-intersecting "bowtie" linestring.
INSERT INTO public.roads (feature_id, id, class, geometry)
SELECT 'RD_INJ_INVALID', 999002, 'residential',
       ST_GeomFromText(
         'LINESTRING(46.70000 24.70000, 46.70010 24.70010, 46.70010 24.70000, 46.70000 24.70010)',
         4326)
WHERE NOT EXISTS (SELECT 1 FROM public.roads WHERE feature_id='RD_INJ_INVALID');

-- Missing geometry (RD005).
INSERT INTO public.roads (feature_id, id, class, geometry)
SELECT 'RD_INJ_NULL', 999003, 'residential', NULL
WHERE NOT EXISTS (SELECT 1 FROM public.roads WHERE feature_id='RD_INJ_NULL');

-- Overshoot candidate (RD001): road A continues ~4 m past its crossing with road B.
INSERT INTO public.roads (feature_id, id, class, geometry)
SELECT 'RD_INJ_OVER', 999004, 'residential',
       ST_GeomFromText(
         'LINESTRING(46.698040 24.70000, 46.700040 24.70000)', 4326)
WHERE NOT EXISTS (SELECT 1 FROM public.roads WHERE feature_id='RD_INJ_OVER');

INSERT INTO public.roads (feature_id, id, class, geometry)
SELECT 'RD_INJ_OVER_B', 999005, 'residential',
       ST_GeomFromText(
         'LINESTRING(46.700036 24.69950, 46.700036 24.70050)', 4326)
WHERE NOT EXISTS (SELECT 1 FROM public.roads WHERE feature_id='RD_INJ_OVER_B');

-- Undershoot candidate (RD002): road C endpoint ~4 m short of road D, not touching.
INSERT INTO public.roads (feature_id, id, class, geometry)
SELECT 'RD_INJ_UNDER', 999006, 'residential',
       ST_GeomFromText(
         'LINESTRING(46.702040 24.70100, 46.704040 24.70100)', 4326)
WHERE NOT EXISTS (SELECT 1 FROM public.roads WHERE feature_id='RD_INJ_UNDER');

INSERT INTO public.roads (feature_id, id, class, geometry)
SELECT 'RD_INJ_UNDER_D', 999007, 'residential',
       ST_GeomFromText(
         'LINESTRING(46.704000 24.70050, 46.704000 24.70150)', 4326)
WHERE NOT EXISTS (SELECT 1 FROM public.roads WHERE feature_id='RD_INJ_UNDER_D');
