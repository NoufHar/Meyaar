import Image from "next/image";
import { useLanguage } from "@/components/LanguageProvider";

import type { VisionAnalysisResponse } from "@/types/analysis";

interface VisionPreviewProps { result: VisionAnalysisResponse; imageUrl: string | null; }

export default function VisionPreview({ result, imageUrl }: VisionPreviewProps) {
  const { t } = useLanguage();
  return (
    <section className="grid overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm lg:grid-cols-2">
      <div className="flex min-h-80 items-center justify-center bg-slate-100 p-5">
        {imageUrl ? <Image src={imageUrl} alt={`Uploaded map ${result.filename}`} width={1200} height={800} unoptimized className="max-h-[520px] h-auto max-w-full rounded-xl object-contain shadow" /> : <p className="text-sm text-slate-500">Image preview unavailable.</p>}
      </div>
      <div className="p-6">
        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-blue-600">{t("Vision analysis")}</p>
        <h2 className="mt-2 text-2xl font-bold">{t("Map elements")}</h2>
        <div className="mt-5 grid grid-cols-2 gap-2">
          {Object.entries(result.quality_checks ?? {}).map(([key, value]) => <div key={key} className="rounded-xl bg-slate-50 p-3"><p className="text-xs capitalize text-slate-500">{key.replaceAll('_', ' ')}</p><p className="mt-1 font-bold text-slate-900">{value}</p></div>)}
        </div>
        {result.geotiff && <div className="mt-4 rounded-2xl border border-blue-100 bg-blue-50 p-4"><h3 className="font-bold text-blue-950">GeoTIFF</h3>{result.geotiff.available ? <dl className="mt-2 space-y-1 text-xs text-blue-900"><div>CRS: <strong>{result.geotiff.crs ?? 'Missing'}</strong></div><div>Size: <strong>{result.geotiff.width} × {result.geotiff.height}</strong></div><div>Pixel size: <strong>{result.geotiff.pixel_size?.join(' × ')}</strong></div><div>NoData: <strong>{result.geotiff.nodata_ratio ?? 0}%</strong></div><div className="break-all">Bounds: <strong>{result.geotiff.bounds?.join(', ')}</strong></div></dl> : <p className="mt-2 text-xs text-red-700">{result.geotiff.message}</p>}</div>}
        <div className="mt-5 space-y-3">
          {result.elements.map((element) => (
            <div key={element.element} className="flex items-center justify-between rounded-xl border border-slate-200 px-4 py-3">
              <span className="font-semibold capitalize">{element.element.replaceAll('_', ' ')}</span>
              <span className={`rounded-full px-3 py-1 text-xs font-bold ${element.present ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-800'}`}>
                {element.present ? t('Present') : t('Missing')}
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
