"use client";

import { useState } from "react";
import type { ProcessingResult } from "@/types/analysis";
import { useLanguage } from "@/components/LanguageProvider";
import { downloadPdfReport } from "@/lib/api";

interface ReportActionsProps { result: ProcessingResult; }

function downloadJson(result: ProcessingResult) {
  const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${result.filename.replace(/\.[^.]+$/, "")}-meyaar-report.json`;
  anchor.click();
  URL.revokeObjectURL(url);
}

export default function ReportActions({ result }: ReportActionsProps) {
  const { t } = useLanguage();
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function downloadPdf() {
    setDownloading(true);
    setError(null);
    try { await downloadPdfReport(result); }
    catch (requestError) { setError(requestError instanceof Error ? requestError.message : "PDF generation failed."); }
    finally { setDownloading(false); }
  }
  return (
    <section className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div>
        <h2 className="font-bold text-slate-950">{t("Export report")}</h2>
        <p className="mt-1 text-sm text-slate-500">{t("Download structured data or save this page as PDF.")}</p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" onClick={() => downloadJson(result)} className="rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-bold text-white hover:bg-slate-700">
          {t("Download JSON")}
        </button>
        <button type="button" disabled={downloading} onClick={downloadPdf} className="rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-bold text-white hover:bg-blue-700 disabled:bg-slate-400">
          {downloading ? t("Generating PDF...") : t("Download PDF")}
        </button>
        {error && <p className="w-full text-xs text-red-600">{error}</p>}
      </div>
    </section>
  );
}
