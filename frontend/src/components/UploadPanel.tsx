"use client";

import { useEffect, useRef, useState } from "react";

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

  const [files, setFiles] = useState<File[]>([]);
  const folderInputRef = useRef<HTMLInputElement>(null);
  const [progress, setProgress] = useState(0);
  const [currentFile, setCurrentFile] = useState(0);

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

  useEffect(() => { folderInputRef.current?.setAttribute("webkitdirectory", ""); }, []);


  const acceptedFormats =
    mode === "vector"
      ? ".geojson,.json,.gpkg,.csv,.parquet,.zip"
      : ".png,.jpg,.jpeg,.tif,.tiff";


  async function handleSubmit(
    event: React.FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    if (!files.length) {
      setError("Select a file or folder before starting the analysis.");
      return;
    }

    const sizeLimit = mode === "vector" ? 500 * 1024 * 1024 : 100 * 1024 * 1024;
    const oversized = files.find((item) => item.size > sizeLimit);
    if (oversized) {
      setError(`${oversized.name} exceeds the ${mode === "vector" ? 500 : 100} MB limit.`);
      return;
    }

    setElapsedSeconds(0);
    setIsLoading(true);
    setProgress(0);
    setCurrentFile(0);
    setError(null);

    try {
      let finalResult: ProcessingResult | null = null;
      for (let index = 0; index < files.length; index += 1) {
        const selectedFile = files[index];
        setCurrentFile(index);
        const updateProgress = (filePercent: number) => setProgress(Math.round(((index + filePercent / 100) / files.length) * 100));
        finalResult = mode === "vector"
          ? await processVectorFile(selectedFile, layerType, updateProgress)
          : await analyzeMapImage(selectedFile, updateProgress);
      }
      if (finalResult) onResult(finalResult, files[files.length - 1], mode);
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
    setFiles([]);
    setProgress(0);
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
              {files.length
                ? files.length === 1 ? files[0].name : `${files.length} files selected`
                : t("Choose a file to upload")}
            </span>

            <span className="mt-1 text-xs text-slate-500">
              {mode === "vector"
                ? "GeoJSON, GeoPackage, CSV, GeoParquet, or zipped Shapefile"
                : "PNG, JPG, JPEG, TIFF, or TIF"}
            </span>

            {files.length > 0 && (
              <span className="mt-2 rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate-600 shadow-sm">
                {(files.reduce((total, item) => total + item.size, 0) / 1024 / 1024).toFixed(2)} MB total
              </span>
            )}
          </label>

          <input
            id="dataset-file"
            type="file"
            accept={acceptedFormats}
            onChange={(event) => {
              setFiles(Array.from(event.target.files ?? []));
              setError(null);
            }}
            className="sr-only"
          />
          <div className="mt-3 flex items-center justify-center gap-2"><span className="text-xs text-slate-400">or</span><label htmlFor="dataset-folder" className="cursor-pointer rounded-lg border border-blue-200 bg-blue-50 px-4 py-2 text-xs font-bold text-blue-700 hover:bg-blue-100">Choose a folder</label></div>
          <input ref={folderInputRef} id="dataset-folder" type="file" multiple accept={acceptedFormats} onChange={(event) => { const supported = Array.from(event.target.files ?? []).filter((item) => acceptedFormats.split(",").some((extension) => item.name.toLowerCase().endsWith(extension))); setFiles(supported); setError(supported.length ? null : "The folder does not contain supported files for this analysis type."); }} className="sr-only" />
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
            <div className="mb-2 flex justify-between font-bold"><span>{files[currentFile]?.name}</span><span>{progress}%</span></div><div className="mb-2 h-2 overflow-hidden rounded-full bg-blue-100"><div className="h-full rounded-full bg-blue-600 transition-[width]" style={{ width: `${progress}%` }} /></div>
            {files.length > 1 && <p className="mb-1 font-semibold">File {currentFile + 1} of {files.length}</p>}
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
