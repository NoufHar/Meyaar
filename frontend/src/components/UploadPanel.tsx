"use client";

import { useEffect, useState } from "react";

import {
  analyzeMapImage,
  processVectorFile,
} from "@/lib/api";

import type {
  LayerType,
  ProcessingResult,
} from "@/types/analysis";
import { useLanguage } from "@/components/LanguageProvider";


interface UploadPanelProps {
  onResult: (
    result: ProcessingResult,
    file: File,
    mode: UploadMode,
  ) => void;
}


type UploadMode = "vector" | "image";


export default function UploadPanel({
  onResult,
}: UploadPanelProps) {
  const { t } = useLanguage();
  const [mode, setMode] =
    useState<UploadMode>("vector");

  const [layerType, setLayerType] =
    useState<LayerType>("roads");

  const [file, setFile] =
    useState<File | null>(null);

  const [isLoading, setIsLoading] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {
    if (!isLoading) return;
    const timer = window.setInterval(
      () => setElapsedSeconds((value) => value + 1),
      1000,
    );
    return () => window.clearInterval(timer);
  }, [isLoading]);


  const acceptedFormats =
    mode === "vector"
      ? ".geojson,.json,.gpkg,.csv,.parquet,.zip"
      : ".png,.jpg,.jpeg,.tif,.tiff";


  async function handleSubmit(
    event: React.FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    if (!file) {
      setError("Select a file before starting the analysis.");
      return;
    }

    const sizeLimit = mode === "vector" ? 100 * 1024 * 1024 : 25 * 1024 * 1024;
    if (file.size > sizeLimit) {
      setError(`The selected file exceeds the ${mode === "vector" ? 100 : 25} MB limit.`);
      return;
    }

    setElapsedSeconds(0);
    setIsLoading(true);
    setError(null);

    try {
      const result =
        mode === "vector"
          ? await processVectorFile(
              file,
              layerType,
            )
          : await analyzeMapImage(file);

      onResult(result, file, mode);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The analysis request failed.",
      );
    } finally {
      setIsLoading(false);
    }
  }


  function changeMode(nextMode: UploadMode) {
    setMode(nextMode);
    setFile(null);
    setError(null);
  }


  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="mb-6">
        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-blue-600">
          {t("New analysis")}
        </p>

        <h2 className="mt-2 text-2xl font-bold text-slate-950">
          {t("Upload geospatial data")}
        </h2>

        <p className="mt-2 text-sm leading-6 text-slate-600">
          {t("Upload vector data for PostGIS validation or a map image for visual element analysis.")}
        </p>
      </div>

      <div className="mb-6 grid grid-cols-2 gap-2 rounded-2xl bg-slate-100 p-1">
        <button
          type="button"
          onClick={() => changeMode("vector")}
          className={`rounded-xl px-4 py-3 text-sm font-semibold transition ${
            mode === "vector"
              ? "bg-white text-blue-700 shadow-sm"
              : "text-slate-600 hover:text-slate-900"
          }`}
        >
          {t("Vector data")}
        </button>

        <button
          type="button"
          onClick={() => changeMode("image")}
          className={`rounded-xl px-4 py-3 text-sm font-semibold transition ${
            mode === "image"
              ? "bg-white text-blue-700 shadow-sm"
              : "text-slate-600 hover:text-slate-900"
          }`}
        >
          {t("Map image")}
        </button>
      </div>

      <form
        onSubmit={handleSubmit}
        className="space-y-5"
      >
        {mode === "vector" && (
          <div>
            <label
              htmlFor="layer-type"
              className="mb-2 block text-sm font-semibold text-slate-800"
            >
              {t("Layer type")}
            </label>

            <select
              id="layer-type"
              value={layerType}
              onChange={(event) =>
                setLayerType(
                  event.target.value as LayerType,
                )
              }
              className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-100"
            >
              <option value="roads">{t("Roads")}</option>
              <option value="buildings">
                {t("Buildings")}
              </option>
            </select>
          </div>
        )}

        <div>
          <label
            htmlFor="dataset-file"
            className="mb-2 block text-sm font-semibold text-slate-800"
          >
            {t("Select file")}
          </label>

          <label
            htmlFor="dataset-file"
            className="flex min-h-44 cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed border-slate-300 bg-slate-50 px-5 text-center transition hover:border-blue-400 hover:bg-blue-50"
          >
            <span className="text-3xl">↑</span>

            <span className="mt-3 text-sm font-semibold text-slate-900">
              {file
                ? file.name
                : t("Choose a file to upload")}
            </span>

            <span className="mt-1 text-xs text-slate-500">
              {mode === "vector"
                ? "GeoJSON, GeoPackage, CSV, GeoParquet, or zipped Shapefile"
                : "PNG, JPG, JPEG, TIFF, or TIF"}
            </span>

            {file && (
              <span className="mt-2 rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate-600 shadow-sm">
                {(file.size / 1024 / 1024).toFixed(2)} MB
              </span>
            )}
          </label>

          <input
            id="dataset-file"
            type="file"
            accept={acceptedFormats}
            onChange={(event) => {
              setFile(
                event.target.files?.[0] ?? null,
              );
              setError(null);
            }}
            className="sr-only"
          />
        </div>

        {error && (
          <div
            role="alert"
            className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
          >
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={isLoading}
          className="w-full rounded-xl bg-blue-600 px-5 py-3.5 text-sm font-bold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-400"
        >
          {isLoading
            ? `Analyzing... ${elapsedSeconds}s`
            : t("Start analysis")}
        </button>

        {isLoading && (
          <div className="rounded-xl bg-blue-50 px-4 py-3 text-xs leading-5 text-blue-800" aria-live="polite">
            {elapsedSeconds < 5
              ? "Uploading and validating the file..."
              : elapsedSeconds < 20
                ? "Running spatial rules and preparing results..."
                : "Large datasets can take a few minutes. Keep this page open while processing continues."}
          </div>
        )}
      </form>
    </section>
  );
}
