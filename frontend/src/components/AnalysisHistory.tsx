"use client";

import { useEffect, useState } from "react";
import { downloadBatchJson, downloadBatchPdf, listAnalyses, loadAnalysis } from "@/lib/api";
import type { ProcessingResult, SavedAnalysisSummary } from "@/types/analysis";

export default function AnalysisHistory({ onOpen, showOwner = false }: { onOpen: (result: ProcessingResult) => void; showOwner?: boolean }) {
  const [items, setItems] = useState<SavedAnalysisSummary[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState<"json" | "pdf" | null>(null);
  const [error, setError] = useState("");

  // Selection stays client-side; the backend re-checks access before producing a combined PDF.
  useEffect(() => { listAnalyses().then(setItems).catch((reason) => setError(reason instanceof Error ? reason.message : "Could not load analyses.")).finally(() => setLoading(false)); }, []);
  const allSelected = items.length > 0 && selected.length === items.length;
  function toggle(id: string) { setSelected((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]); }
  async function download(format: "json" | "pdf") { if (!selected.length) return; setDownloading(format); setError(""); try { if (format === "json") await downloadBatchJson(selected); else await downloadBatchPdf(selected); } catch (reason) { setError(reason instanceof Error ? reason.message : "Download failed."); } finally { setDownloading(null); } }

  if (loading) return <p className="p-8 text-slate-500">Loading saved analyses...</p>;
  if (error && !items.length) return <p className="rounded-xl bg-red-50 p-4 text-red-700">{error}</p>;
  return <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-xl font-bold">Saved analyses</h2><p className="mt-1 text-sm text-slate-500">Select files to export together.</p></div>{items.length > 0 && <label className="flex cursor-pointer items-center gap-2 text-sm font-semibold text-slate-600"><input type="checkbox" checked={allSelected} onChange={() => setSelected(allSelected ? [] : items.map((item) => item.analysis_id))} className="size-4 accent-blue-600"/>Select all</label>}</div>{selected.length > 0 && <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-blue-100 bg-blue-50 p-3"><span className="text-sm font-semibold text-blue-800">{selected.length} selected</span><div className="flex gap-2"><button type="button" disabled={downloading !== null} onClick={() => void download("json")} className="rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-bold text-white disabled:opacity-50">{downloading === "json" ? "Preparing..." : "Download JSON"}</button><button type="button" disabled={downloading !== null} onClick={() => void download("pdf")} className="rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-bold text-white disabled:opacity-50">{downloading === "pdf" ? "Preparing..." : "Download PDF"}</button></div></div>}{error && <p className="mt-3 rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p>}<div className="mt-5 space-y-3">{items.length === 0 ? <p className="rounded-xl bg-slate-50 p-6 text-center text-slate-500">No saved analyses yet.</p> : items.map((item) => <article key={item.analysis_id} className={`grid gap-3 rounded-xl border p-4 transition sm:grid-cols-[auto_1fr_auto_auto] sm:items-center ${selected.includes(item.analysis_id) ? "border-blue-300 bg-blue-50/60" : "border-slate-200 hover:border-blue-200"}`}><input type="checkbox" checked={selected.includes(item.analysis_id)} onChange={() => toggle(item.analysis_id)} aria-label={`Select ${item.filename}`} className="size-4 accent-blue-600"/><button type="button" onClick={async () => onOpen(await loadAnalysis(item.analysis_id))} className="min-w-0 text-start"><span className="block break-all font-bold text-slate-900 hover:text-blue-600">{item.filename}</span><span className="mt-1 block text-xs text-slate-500">{item.analysis_type}{showOwner ? ` · ${item.owner_name}` : ""}</span></button><span className="text-sm"><strong>{item.total_errors}</strong> errors</span><span className="rounded-lg bg-blue-100 px-3 py-2 text-sm font-bold text-blue-700">{item.compliance_score ?? "-"}%</span></article>)}</div></section>;
}
