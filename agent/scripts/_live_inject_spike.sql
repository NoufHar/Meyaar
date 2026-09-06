-- Insert an invalid "spike" building footprint for the remediation demo.
-- ST_MakeValid can repair this WITHIN the Polygon column type -> the agent
-- auto-fix should record status=applied and leave ST_IsValid = true.
INSERT INTO public.buildings (feature_id, geometry)
SELECT 'BLD_INJ_SPK',
       ST_SetSRID(ST_GeomFromText(
         'POLYGON((46.7000 24.6000, 46.7004 24.6000, 46.7004 24.6004, 46.7004 24.6002, 46.7004 24.6004, 46.7000 24.6004, 46.7000 24.6000))'
       ), 4326)
WHERE NOT EXISTS (SELECT 1 FROM public.buildings WHERE feature_id = 'BLD_INJ_SPK');
