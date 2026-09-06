import type { VectorProcessingResponse } from "@/types/analysis";
import { useLanguage } from "@/components/LanguageProvider";

interface FilterBarProps {
  result: VectorProcessingResponse;
  search: string;
  severity: string;
  errorType: string;
  onSearchChange: (value: string) => void;
  onSeverityChange: (value: string) => void;
  onErrorTypeChange: (value: string) => void;
  onClear: () => void;
}

export default function FilterBar(props: FilterBarProps) {
  const { t } = useLanguage();
  const errorTypes = Array.from(new Set(
    props.result.validation.errors.map((error) => error.error_type),
  )).sort();

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
      <div className="grid gap-2.5 md:grid-cols-[1fr_160px_190px_auto]">
        <input
          value={props.search}
          onChange={(event) => props.onSearchChange(event.target.value)}
          placeholder={t("Search error or Feature ID")}
          aria-label="Search errors"
          className="rounded-lg border border-slate-300 px-3.5 py-2 text-xs outline-none focus:border-blue-500 focus:ring-4 focus:ring-blue-100"
        />
        <select
          value={props.severity}
          onChange={(event) => props.onSeverityChange(event.target.value)}
          aria-label="Filter by severity"
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs"
        >
          <option value="all">{t("All severities")}</option>
          {['critical', 'high', 'medium', 'low', 'warning'].map((value) => (
            <option key={value} value={value}>{value}</option>
          ))}
        </select>
        <select
          value={props.errorType}
          onChange={(event) => props.onErrorTypeChange(event.target.value)}
          aria-label="Filter by error type"
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs"
        >
          <option value="all">{t("All error types")}</option>
          {errorTypes.map((value) => (
            <option key={value} value={value}>{value.replaceAll('_', ' ')}</option>
          ))}
        </select>
        <button
          type="button"
          onClick={props.onClear}
          className="rounded-lg border border-slate-300 px-3.5 py-2 text-xs font-semibold hover:bg-slate-50"
        >
          {t("Clear")}
        </button>
      </div>
    </section>
  );
}
