import type {
  ProcessingResult,
  VectorProcessingResponse,
  VisionAnalysisResponse,
} from "@/types/analysis";
import { useLanguage } from "@/components/LanguageProvider";


interface StatsCardsProps {
  result: ProcessingResult;
}


interface StatCard {
  label: string;
  value: number | string;
  description: string;
  color: string;
}


function isVectorResult(
  result: ProcessingResult,
): result is VectorProcessingResponse {
  return "validation" in result;
}


function buildVectorStats(
  result: VectorProcessingResponse,
): StatCard[] {
  const summary = result.analysis.summary;

  return [
    {
      label: "Compliance score",
      value: `${result.compliance_score ?? 100}%`,
      description: "Internal data quality score",
      color: "text-blue-600",
    },
    {
      label: "Total errors",
      value: result.validation.total_errors,
      description: "Errors detected by PostGIS rules",
      color: "text-slate-950",
    },
    {
      label: "High priority",
      value:
        summary.critical_errors +
        summary.high_errors,
      description: "Critical and high-severity errors",
      color: "text-red-600",
    },
    {
      label: "Medium priority",
      value: summary.medium_errors,
      description: "Errors requiring planned cleanup",
      color: "text-amber-600",
    },
    {
      label: "Human review",
      value: summary.human_review_pending,
      description: "Items awaiting manual confirmation",
      color: "text-blue-600",
    },
  ];
}


function buildVisionStats(
  result: VisionAnalysisResponse,
): StatCard[] {
  const presentElements =
    result.elements.filter(
      (element) => element.present,
    ).length;

  return [
    {
      label: "Compliance score",
      value: `${result.compliance_score ?? 100}%`,
      description: "Internal image quality score",
      color: "text-blue-600",
    },
    {
      label: "Elements checked",
      value: result.elements.length,
      description: "Required map elements analyzed",
      color: "text-slate-950",
    },
    {
      label: "Elements present",
      value: presentElements,
      description: "Elements detected in the image",
      color: "text-emerald-600",
    },
    {
      label: "Missing elements",
      value: result.issues.length,
      description: "Map elements not detected",
      color: "text-amber-600",
    },
    {
      label: "Completion",
      value: `${Math.round(
        (presentElements /
          Math.max(result.elements.length, 1)) *
          100,
      )}%`,
      description: "Required element completion rate",
      color: "text-blue-600",
    },
  ];
}


export default function StatsCards({
  result,
}: StatsCardsProps) {
  const { t } = useLanguage();
  const stats = isVectorResult(result)
    ? buildVectorStats(result)
    : buildVisionStats(result);

  return (
    <section>
      <div className="mb-3">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-blue-600">
          {t("Analysis overview")}
        </p>

        <h2 className="mt-1 text-xl font-bold text-slate-950">
          {t("Result summary")}
        </h2>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {stats.map((stat) => (
          <article
            key={stat.label}
            className="min-h-[132px] rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
          >
            <p className="text-xs font-medium text-slate-500">
              {t(stat.label)}
            </p>

            <p
              className={`mt-2 text-2xl font-bold ${stat.color}`}
            >
              {stat.value}
            </p>

            <p className="mt-1.5 text-[11px] leading-4 text-slate-500">
              {t(stat.description)}
            </p>
          </article>
        ))}
      </div>
    </section>
  );
}
