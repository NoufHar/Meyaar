"use client";

import { useEffect, useState } from "react";
import { useLanguage } from "@/components/LanguageProvider";
import { getErrorReview, updateErrorReview } from "@/lib/api";
import type { ReviewStatus } from "@/types/analysis";

import type {
  ProcessingResult,
  VectorProcessingResponse,
} from "@/types/analysis";


interface ErrorTableProps {
  result: ProcessingResult;
  selectedErrorId?: string | null;
  onSelectError?: (errorId: string) => void;
}


interface DisplayError {
  id: string;
  type: string;
  featureId: string;
  severity: string;
  details: string;
  recommendation: string;
  resultId?: number;
}


function isVectorResult(
  result: ProcessingResult,
): result is VectorProcessingResponse {
  return "validation" in result;
}


function buildErrors(
  result: ProcessingResult,
): DisplayError[] {
  if (!isVectorResult(result)) {
    return result.issues.map(
      (issue, index) => ({
        id: `vision-${index}`,
        type: issue.error_type,
        featureId: result.filename,
        severity: issue.severity,
        details: issue.message,
        recommendation:
          "Add or clarify the missing map element.",
      }),
    );
  }

  return result.validation.errors.map(
    (error) => {
      const analysis =
        result.analysis.analyses.find(
          (item) =>
            item.result_id === error.result_id,
        );

      return {
        id: String(error.result_id),
        type: error.error_type,
        featureId: error.feature_id,
        severity: error.severity,
        details:
          analysis?.explanation ??
          error.details,
        recommendation:
          analysis?.recommendation ??
          "Review this feature manually.",
        resultId: error.result_id,
      };
    },
  );
}


function severityClass(
  severity: string,
): string {
  const classes: Record<string, string> = {
    critical:
      "bg-red-100 text-red-800",
    high:
      "bg-orange-100 text-orange-800",
    medium:
      "bg-amber-100 text-amber-800",
    low:
      "bg-blue-100 text-blue-800",
    warning:
      "bg-amber-100 text-amber-800",
  };

  return (
    classes[severity.toLowerCase()] ??
    "bg-slate-100 text-slate-700"
  );
}


export default function ErrorTable({
  result,
  selectedErrorId,
  onSelectError,
}: ErrorTableProps) {
  const { t } = useLanguage();
  const errors = buildErrors(result);
  const [detailError, setDetailError] =
    useState<DisplayError | null>(null);
  const [reviewStatus, setReviewStatus] = useState<ReviewStatus>("new");
  const [reviewComment, setReviewComment] = useState("");
  const [reviewMessage, setReviewMessage] = useState("");
  const [savingReview, setSavingReview] = useState(false);

  useEffect(() => {
    if (!detailError?.resultId) return;
    let active = true;
    getErrorReview(detailError.resultId).then((review) => {
      if (active) { setReviewStatus(review.status); setReviewComment(review.comment); }
    }).catch(() => { if (active) { setReviewStatus("new"); setReviewComment(""); } });
    return () => { active = false; };
  }, [detailError]);

  async function saveReview() {
    if (!detailError?.resultId) return;
    setSavingReview(true);
    setReviewMessage("");
    try {
      await updateErrorReview(detailError.resultId, reviewStatus, reviewComment);
      setReviewMessage(t("Review saved"));
    } catch (error) {
      setReviewMessage(error instanceof Error ? error.message : "Review could not be saved.");
    } finally { setSavingReview(false); }
  }

  return (
    <section className="rounded-3xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-200 px-6 py-5">
        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-blue-600">
          {t("Detected issues")}
        </p>

        <h2 className="mt-2 text-2xl font-bold text-slate-950">
          {t("Errors and recommendations")}
        </h2>

        <p className="mt-2 text-sm text-slate-500">
          {t("Review validation details and the recommended corrective actions.")}
        </p>
      </div>

      {errors.length === 0 ? (
        <div className="px-6 py-12 text-center">
          <p className="text-lg font-semibold text-emerald-700">
            {t("No errors detected")}
          </p>

          <p className="mt-2 text-sm text-slate-500">
            The uploaded file completed the available
            validation checks.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200">
            <thead className="bg-slate-50">
              <tr>
                {[
                  t("Error"),
                  t("Feature"),
                  t("Severity"),
                  t("Details"),
                  t("Recommendation"),
                ].map((heading) => (
                  <th
                    key={heading}
                    scope="col"
                    className="px-5 py-3 text-left text-xs font-bold uppercase tracking-wider text-slate-500"
                  >
                    {heading}
                  </th>
                ))}
              </tr>
            </thead>

            <tbody className="divide-y divide-slate-100">
              {errors.map((error) => (
                <tr
                  key={error.id}
                  className={`align-top transition ${
                    selectedErrorId === error.id
                      ? "bg-blue-50 shadow-[inset_4px_0_0_#2563eb]"
                      : "hover:bg-slate-50"
                  }`}
                  aria-selected={
                    selectedErrorId === error.id
                  }
                >
                  <td className="whitespace-nowrap px-5 py-4 text-sm font-semibold text-slate-900">
                    <p>
                      {error.type.replaceAll(
                        "_",
                        " ",
                      )}
                    </p>

                    {onSelectError &&
                      !error.id.startsWith("vision-") && (
                        <button
                          type="button"
                          onClick={() =>
                            onSelectError(error.id)
                          }
                          className="mt-2 text-xs font-bold text-blue-600 underline decoration-blue-200 underline-offset-4 transition hover:text-blue-800"
                        >
                          {selectedErrorId === error.id
                            ? t("Selected on map")
                            : t("View on map")}
                        </button>
                      )}

                    <button
                      type="button"
                      onClick={() => setDetailError(error)}
                      className="mt-2 block text-xs font-bold text-slate-600 underline decoration-slate-300 underline-offset-4 hover:text-slate-900"
                    >
                      {t("Full details")}
                    </button>
                  </td>

                  <td className="max-w-48 break-all px-5 py-4 text-xs text-slate-600">
                    {error.featureId}
                  </td>

                  <td className="px-5 py-4">
                    <span
                      className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold capitalize ${severityClass(
                        error.severity,
                      )}`}
                    >
                      {error.severity}
                    </span>
                  </td>

                  <td className="min-w-72 px-5 py-4 text-sm leading-6 text-slate-600">
                    {error.details}
                  </td>

                  <td className="min-w-72 px-5 py-4 text-sm leading-6 text-slate-700">
                    {error.recommendation}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {detailError && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="error-detail-title"
          className="fixed inset-0 z-[2000] flex items-center justify-center bg-slate-950/60 p-4"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setDetailError(null);
          }}
        >
          <div className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-3xl bg-white p-6 shadow-2xl">
            <div className="flex items-start justify-between gap-4">
              <div>
                <span className={`inline-flex rounded-full px-3 py-1 text-xs font-bold capitalize ${severityClass(detailError.severity)}`}>{detailError.severity}</span>
                <h3 id="error-detail-title" className="mt-3 text-2xl font-bold capitalize">{detailError.type.replaceAll('_', ' ')}</h3>
                <p className="mt-1 break-all text-sm text-slate-500">Feature {detailError.featureId}</p>
              </div>
              <button type="button" onClick={() => setDetailError(null)} aria-label="Close details" className="rounded-full bg-slate-100 px-3 py-1.5 text-lg hover:bg-slate-200">×</button>
            </div>
            <div className="mt-6 space-y-5">
              <div><h4 className="font-bold text-slate-900">{t("Analysis")}</h4><p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-slate-600">{detailError.details}</p></div>
              <div className="rounded-2xl bg-blue-50 p-4"><h4 className="font-bold text-blue-950">{t("Recommendation")}</h4><p className="mt-2 text-sm leading-7 text-blue-800">{detailError.recommendation}</p></div>
              {detailError.resultId && <div className="rounded-2xl border border-slate-200 p-4"><h4 className="font-bold text-slate-900">{t("Review status")}</h4><div className="mt-3 grid gap-3 sm:grid-cols-[190px_1fr]"><select value={reviewStatus} onChange={(event) => setReviewStatus(event.target.value as ReviewStatus)} className="rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm"><option value="new">{t("New")}</option><option value="confirmed">{t("Confirmed")}</option><option value="resolved">{t("Resolved")}</option><option value="false_positive">{t("False positive")}</option></select><textarea value={reviewComment} onChange={(event) => setReviewComment(event.target.value)} maxLength={2000} placeholder={t("Add a review comment...")} className="min-h-24 rounded-xl border border-slate-300 px-3 py-2.5 text-sm" /></div><div className="mt-3 flex items-center gap-3"><button type="button" disabled={savingReview} onClick={saveReview} className="rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-bold text-white disabled:bg-slate-400">{savingReview ? t("Saving...") : t("Save review")}</button>{reviewMessage && <p className="text-xs text-slate-600">{reviewMessage}</p>}</div></div>}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
