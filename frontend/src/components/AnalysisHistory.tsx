"use client";

import { useEffect, useState } from "react";
import { listAnalyses, loadAnalysis } from "@/lib/api";
import type { ProcessingResult, SavedAnalysisSummary } from "@/types/analysis";

export default function AnalysisHistory({ onOpen, showOwner = false }: { onOpen: (result: ProcessingResult) => void; showOwner?: boolean }) {
  const [items, setItems] = useState<SavedAnalysisSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => { listAnalyses().then(setItems).catch((e) => setError(e instanceof Error ? e.message : "Could not load analyses.")).finally(() => setLoading(false)); }, []);
  if (loading) return <p className="p-8 text-slate-500">Loading saved analyses...</p>;
  if (error) return <p className="rounded-xl bg-red-50 p-4 text-red-700">{error}</p>;
  return <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
    <h2 className="text-xl font-bold">Saved analyses</h2>
    <p className="mt-1 text-sm text-slate-500">Your previous validation runs are stored in PostgreSQL.</p>
    <div className="mt-5 space-y-3">{items.length === 0 ? <p className="rounded-xl bg-slate-50 p-6 text-center text-slate-500">No saved analyses yet.</p> : items.map((item) => <button key={item.analysis_id} type="button" onClick={async () => onOpen(await loadAnalysis(item.analysis_id))} className="grid w-full gap-3 rounded-xl border border-slate-200 p-4 text-start transition hover:border-blue-300 hover:bg-blue-50 sm:grid-cols-[1fr_auto_auto] sm:items-center">
      <span><span className="block break-all font-bold text-slate-900">{item.filename}</span><span className="mt-1 block text-xs text-slate-500">{new Date(item.created_at).toLocaleString()} · {item.analysis_type}{showOwner ? ` · ${item.owner_name}` : ""}</span></span>
      <span className="text-sm"><strong>{item.total_errors}</strong> errors</span>
      <span className="rounded-lg bg-blue-100 px-3 py-2 text-sm font-bold text-blue-700">{item.compliance_score ?? "-"}%</span>
    </button>)}</div>
  </section>;
}
