"use client";

import { useEffect, useMemo, useState } from "react";
import AgentChat from "@/components/AgentChat";
import AppSidebar, { type AppView } from "@/components/AppSidebar";
import ErrorTable from "@/components/ErrorTable";
import FilterBar from "@/components/FilterBar";
import LandingPage from "@/components/LandingPage";
import MapPanel from "@/components/MapPanel";
import ReportActions from "@/components/ReportActions";
import StatsCards from "@/components/StatsCards";
import UploadPanel from "@/components/UploadPanel";
import VisionPreview from "@/components/VisionPreview";
import AuthScreen from "@/components/AuthScreen";
import AnalysisHistory from "@/components/AnalysisHistory";
import TeamDashboard from "@/components/TeamDashboard";
import OverallDashboard from "@/components/OverallDashboard";
import TeamOnboarding from "@/components/TeamOnboarding";
import ProfilePanel from "@/components/ProfilePanel";
import FirstLoginPassword from "@/components/FirstLoginPassword";
import { checkBackendHealth, getAuthToken, getMe, logout, updatePresence } from "@/lib/api";
import { useLanguage } from "@/components/LanguageProvider";
import type { AuthUser, ProcessingResult, VectorProcessingResponse, VisionAnalysisResponse } from "@/types/analysis";

const viewTitles: Record<AppView, { title: string; description: string }> = {
  dashboard: { title: "Intelligence Dashboard", description: "Live overview of your latest geospatial quality analysis." },
  upload: { title: "Upload Data", description: "Start a new vector or imagery validation workflow." },
  analysis: { title: "Error Analysis", description: "Filter, inspect, and resolve detected quality issues." },
  reports: { title: "Reports", description: "Review the run summary and export audit-ready results." },
  history: { title: "Saved Analyses", description: "Open validation results saved to your account." },
  team: { title: "Team Management", description: "Monitor your team members and their validation activity." },
  profile: { title: "My Profile", description: "Review your personal information and account security." },
  assistant: { title: "Meyaar AI Assistant", description: "Ask grounded questions about the current validation run." },
};

function EmptyState({ onUpload }: { onUpload: () => void }) {
  const { t } = useLanguage();
  return <section className="flex min-h-[460px] items-center justify-center rounded-3xl border border-dashed border-slate-300 bg-white p-8 text-center shadow-sm"><div className="max-w-md"><div className="mx-auto flex size-16 items-center justify-center rounded-2xl bg-blue-100 text-3xl text-blue-700">⇧</div><h2 className="mt-5 text-2xl font-bold">{t("No analysis selected")}</h2><p className="mt-2 text-sm leading-6 text-slate-500">{t("Upload vector data or a map image to populate the dashboard with live results.")}</p><button type="button" onClick={onUpload} className="mt-6 rounded-xl bg-blue-600 px-5 py-3 text-sm font-bold text-white hover:bg-blue-700">{t("Upload data")}</button></div></section>;
}

export default function Home() {
  const { language, toggleLanguage, t } = useLanguage();
  const [entered, setEntered] = useState(false);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [checkingAuth, setCheckingAuth] = useState(true);
  const [view, setView] = useState<AppView>("dashboard");
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  const [result, setResult] = useState<ProcessingResult | null>(null);
  const [selectedErrorId, setSelectedErrorId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [severity, setSeverity] = useState("all");
  const [errorType, setErrorType] = useState("all");
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [profileMenuOpen, setProfileMenuOpen] = useState(false);

  useEffect(() => {
    checkBackendHealth().then(setBackendOnline);
    if (!getAuthToken()) { Promise.resolve().then(() => setCheckingAuth(false)); return; }
    getMe().then(setUser).catch(() => setUser(null)).finally(() => setCheckingAuth(false));
  }, []);
  useEffect(() => {
    if (!user) return;
    const ping = () => { if (document.visibilityState === "visible") void updatePresence(); };
    ping();
    const interval = window.setInterval(ping, 45_000);
    document.addEventListener("visibilitychange", ping);
    return () => { window.clearInterval(interval); document.removeEventListener("visibilitychange", ping); };
  }, [user]);
  const vectorResult = result && "validation" in result ? result as VectorProcessingResponse : null;
  const displayedResult = useMemo<ProcessingResult | null>(() => {
    if (!vectorResult) return result;
    const needle = search.trim().toLowerCase();
    const errors = vectorResult.validation.errors.filter((error) => {
      const matchesSearch = !needle || [error.error_type, error.feature_id, error.rule_id, error.details].some((value) => value.toLowerCase().includes(needle));
      return matchesSearch && (severity === "all" || error.severity.toLowerCase() === severity) && (errorType === "all" || error.error_type === errorType);
    });
    return { ...vectorResult, validation: { ...vectorResult.validation, total_errors: errors.length, errors } };
  }, [errorType, result, search, severity, vectorResult]);

  function selectError(errorId: string) {
    setSelectedErrorId(errorId);
    setView("analysis");
    window.setTimeout(() => document.getElementById("map-panel")?.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
  }

  if (!entered) return <LandingPage onStart={() => setEntered(true)} />;
  if (checkingAuth) return <main className="flex min-h-screen items-center justify-center bg-[#eef5ff] font-bold text-blue-700">Loading...</main>;
  if (!user) return <AuthScreen onAuthenticated={setUser} />;
  if (user.must_change_password) return <FirstLoginPassword user={user} onComplete={setUser} onCancel={() => setUser(null)} />;
  if (!user.team_id) return <TeamOnboarding user={user} onReady={setUser} />;
  const heading = viewTitles[view];
  const statusText = backendOnline === null ? "Checking services" : backendOnline ? "All systems online" : "Backend offline";

  const filters = vectorResult && <FilterBar result={vectorResult} search={search} severity={severity} errorType={errorType} onSearchChange={setSearch} onSeverityChange={setSeverity} onErrorTypeChange={setErrorType} onClear={() => { setSearch(""); setSeverity("all"); setErrorType("all"); }} />;

  return (
    <div className="min-h-screen bg-[#f4f7fb] text-slate-950">
      <AppSidebar activeView={view} onNavigate={setView} />
      <div className="lg:pl-56 rtl:lg:pl-0 rtl:lg:pr-56">
        <header className="sticky top-0 z-[1000] flex min-h-[72px] items-center justify-between gap-4 border-b border-slate-200/80 bg-white/95 px-5 shadow-[0_1px_12px_rgba(15,23,42,0.04)] backdrop-blur-xl lg:px-7"><div className="min-w-0"><h1 className="truncate text-xl font-extrabold tracking-tight text-[#071c33]">{t(heading.title)}</h1><p className="mt-0.5 hidden text-xs text-slate-500 sm:block">{t(heading.description)}</p></div><div className="flex shrink-0 items-center gap-2"><button type="button" onClick={toggleLanguage} aria-label={language === "en" ? "Switch to Arabic" : "Switch to English"} className="flex h-9 items-center gap-1.5 rounded-lg px-2.5 text-xs font-bold text-[#071c33] transition hover:bg-slate-100"><span>{language === "en" ? "AR" : "EN"}</span><span className="text-base" aria-hidden="true">🌐</span></button><div className="relative"><button type="button" onClick={() => setProfileMenuOpen((open) => !open)} title="My profile" aria-label="Open profile menu" aria-expanded={profileMenuOpen} className={`relative flex size-9 items-center justify-center rounded-full text-sm font-black transition ${profileMenuOpen || view === "profile" ? "bg-blue-600 text-white" : "bg-blue-50 text-blue-700 ring-1 ring-blue-200 hover:bg-blue-100"}`}>{user.name.trim().charAt(0).toUpperCase()}<span title={t(statusText)} className={`absolute bottom-0 right-0 size-2.5 rounded-full border-2 border-white ${backendOnline ? "bg-emerald-500" : backendOnline === null ? "bg-amber-400" : "bg-red-500"}`}/></button>{profileMenuOpen && <div className="absolute end-0 top-12 w-56 overflow-hidden rounded-xl border border-slate-200 bg-white p-2 text-start shadow-xl"><button type="button" onClick={() => { setView("profile"); setProfileMenuOpen(false); }} className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50"><span>◯</span>{t("Personal information")}</button><button type="button" onClick={async () => { setProfileMenuOpen(false); await logout(); setUser(null); setResult(null); }} className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-semibold text-red-600 hover:bg-red-50"><span>↪</span>{t("Sign out")}</button></div>}</div></div></header>
        <main className="mx-auto max-w-[1500px] p-4 lg:p-5">
          {view === "upload" && <div className="mx-auto max-w-2xl"><UploadPanel onResult={(newResult, file, mode) => { setResult(newResult); setSelectedErrorId(null); setSearch(""); setSeverity("all"); setErrorType("all"); setImageUrl((current) => { if (current) URL.revokeObjectURL(current); return mode === "image" ? URL.createObjectURL(file) : null; }); setView("analysis"); }} /></div>}
          {view !== "dashboard" && view !== "upload" && view !== "history" && view !== "team" && view !== "profile" && !result && <EmptyState onUpload={() => setView("upload")} />}

          {view === "dashboard" && <OverallDashboard user={user} refreshKey={result?.analysis_id} onUpload={() => setView("upload")} onTeam={() => setView("team")} onOpen={(savedResult) => { setResult(savedResult); setSelectedErrorId(null); setView("analysis"); }} />}

          {result && view === "analysis" && <div className="space-y-6">{filters}{vectorResult ? <MapPanel result={displayedResult ?? vectorResult} selectedErrorId={selectedErrorId} /> : <VisionPreview result={result as VisionAnalysisResponse} imageUrl={imageUrl} />}<ErrorTable result={displayedResult ?? result} selectedErrorId={selectedErrorId} onSelectError={vectorResult ? selectError : undefined} /></div>}
          {result && view === "reports" && <div className="space-y-6"><StatsCards result={result} /><ReportActions result={result} /><section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm"><h2 className="text-xl font-bold">Run information</h2><dl className="mt-5 grid gap-4 text-sm sm:grid-cols-2"><div className="rounded-xl bg-slate-50 p-4"><dt className="text-slate-500">File</dt><dd className="mt-1 break-all font-bold">{result.filename}</dd></div><div className="rounded-xl bg-slate-50 p-4"><dt className="text-slate-500">Status</dt><dd className="mt-1 font-bold capitalize">{result.status}</dd></div>{vectorResult && <><div className="rounded-xl bg-slate-50 p-4"><dt className="text-slate-500">Run ID</dt><dd className="mt-1 break-all font-mono text-xs">{vectorResult.run_id}</dd></div><div className="rounded-xl bg-slate-50 p-4"><dt className="text-slate-500">Layer</dt><dd className="mt-1 font-bold capitalize">{vectorResult.layer_name}</dd></div></>}</dl></section></div>}
          {view === "history" && <AnalysisHistory showOwner={user.role === "manager"} onOpen={(savedResult) => { setResult(savedResult); setSelectedErrorId(null); setView("dashboard"); }} />}
          {view === "team" && (user.role === "manager" || user.role === "leader" ? <TeamDashboard user={user} onTeamChange={(nextUser) => { setUser(nextUser); setResult(null); setView(nextUser.role === "manager" || nextUser.role === "leader" ? "team" : "dashboard"); }} /> : <TeamOnboarding embedded user={user} onReady={(nextUser) => { setUser(nextUser); setResult(null); setView("team"); }} />)}
          {view === "profile" && <ProfilePanel user={user} />}
          {view === "assistant" && (vectorResult ? <AgentChat runId={vectorResult.run_id} embedded /> : result ? <section className="rounded-3xl border border-amber-200 bg-amber-50 p-8 text-center"><h2 className="text-xl font-bold text-amber-950">Assistant requires a vector run</h2><p className="mt-2 text-sm text-amber-800">Upload vector data so the assistant can answer from stored validation results.</p></section> : null)}
        </main>
      </div>
      {vectorResult && view !== "assistant" && <AgentChat runId={vectorResult.run_id} />}
    </div>
  );
}
