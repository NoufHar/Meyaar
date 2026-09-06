"use client";

import Image from "next/image";
import { useLanguage } from "@/components/LanguageProvider";

type LandingPageProps = { onStart: () => void };

const capabilities = [
  { title: "Change Detection", subtitle: "Identify real-world changes", icon: "layers" },
  { title: "Spatial Validation", subtitle: "Ensure map accuracy", icon: "shield" },
  { title: "AI Recommendations", subtitle: "Generate actionable insights", icon: "spark" },
];

function CapabilityIcon({ type }: { type: string }) {
  if (type === "layers") return <svg viewBox="0 0 24 24" className="size-6" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="m3 8 9-5 9 5-9 5-9-5Z"/><path d="m3 12 9 5 9-5M3 16l9 5 9-5"/></svg>;
  if (type === "shield") return <svg viewBox="0 0 24 24" className="size-6" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M12 22s8-3.8 8-10V5l-8-3-8 3v7c0 6.2 8 10 8 10Z"/><path d="m8.5 12 2.2 2.2 4.8-5"/></svg>;
  return <svg viewBox="0 0 24 24" className="size-6" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="m12 3 1.25 3.75L17 8l-3.75 1.25L12 13l-1.25-3.75L7 8l3.75-1.25L12 3ZM5 14l.9 2.6L8.5 17.5l-2.6.9L5 21l-.9-2.6-2.6-.9 2.6-.9L5 14ZM19 13l.7 2.3 2.3.7-2.3.7L19 19l-.7-2.3-2.3-.7 2.3-.7L19 13Z"/></svg>;
}

export default function LandingPage({ onStart }: LandingPageProps) {
  const { language, toggleLanguage, t } = useLanguage();

  return (
    <main className="min-h-screen bg-[#f4f9ff] text-[#071c33]">
      <header className="mx-auto flex h-[54px] max-w-[1280px] items-center justify-between gap-6 px-6 sm:px-10 lg:px-16 xl:px-20">
        <a href="#platform" className="flex items-center gap-3" aria-label="Meyaar home">
          <span className="relative size-9 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm"><Image src="/branding/meyaar-logo.png" alt="Meyaar" fill sizes="36px" className="object-cover" /></span>
          <span className="text-lg font-black tracking-[0.08em] text-blue-600">MEYAAR</span>
        </a>
        <nav className="hidden items-center gap-9 text-sm font-semibold text-slate-600 md:flex">
          <a href="#platform" className="transition hover:text-blue-600">{t("Platform")}</a>
          <a href="#capabilities" className="transition hover:text-blue-600">{t("How it Works")}</a>
          <a href="#about" className="transition hover:text-blue-600">{t("About")}</a>
        </nav>
        <button type="button" onClick={toggleLanguage} className="rounded-lg border border-slate-200 bg-white/90 px-4 py-2 text-xs font-bold text-[#071c33] shadow-sm transition hover:border-blue-200 hover:text-blue-600">{language === "en" ? "العربية" : "English"}</button>
      </header>

      <section id="platform" className="relative mx-auto h-[calc(100vh-54px)] min-h-[500px] max-h-[586px] max-w-[1280px] overflow-hidden bg-[#dfeeff]">
        <Image src={language === "ar" ? "/branding/riyadh-hero-rtl-hq.png" : "/branding/riyadh-hero-en-premium.png"} alt="Riyadh skyline" fill priority sizes="100vw" unoptimized className="object-cover object-center" />
        <div className="absolute inset-0 bg-[linear-gradient(90deg,rgba(247,251,255,0.98)_0%,rgba(229,242,254,0.90)_32%,rgba(211,232,250,0.42)_52%,rgba(12,43,73,0.03)_72%)] rtl:bg-[linear-gradient(270deg,rgba(247,251,255,0.98)_0%,rgba(229,242,254,0.90)_32%,rgba(211,232,250,0.42)_52%,rgba(12,43,73,0.03)_72%)]" />

        <div className="relative z-10 grid h-full items-center px-7 pb-20 pt-5 sm:px-12 lg:px-16 xl:px-20">
          <div id="about" className="max-w-[520px] py-3">
            <div className="mb-4 flex items-center gap-3 text-[9px] font-extrabold uppercase tracking-[0.28em] text-[#31577f]"><span>{t("Geospatial AI Platform")}</span><span className="h-px w-10 bg-blue-500/60" /></div>
            <h1 className="text-[2.15rem] font-black leading-[1.05] tracking-[-0.04em] sm:text-[2.35rem] xl:text-[2.5rem]">
              <span className="block">{t("Validate Geospatial Data.")}</span>
              <span className="mt-2 block text-blue-600">{t("Make Reliable Decisions.")}</span>
            </h1>
            <p className="mt-4 max-w-[460px] text-[13px] leading-[1.55] text-slate-600">{t("Detect spatial changes, validate map accuracy, identify inconsistencies, and generate AI-powered recommendations across satellite, aerial, and vector data.")}</p>
            <div className="mt-5 flex flex-wrap gap-2.5">
              <button type="button" onClick={onStart} className="rounded-lg bg-blue-600 px-4 py-2.5 text-[11px] font-extrabold text-white shadow-[0_8px_20px_rgba(37,99,235,.24)] transition hover:-translate-y-0.5 hover:bg-blue-700">{t("Start Validation")} <span aria-hidden="true">→</span></button>
            </div>
          </div>
        </div>

        <div id="capabilities" className="relative z-20 mx-7 mb-4 grid gap-3 sm:absolute sm:bottom-5 sm:left-12 sm:mx-0 sm:mb-0 sm:w-[560px] sm:grid-cols-3 lg:left-16 xl:left-20 rtl:sm:left-auto rtl:sm:right-12 rtl:lg:right-16 rtl:xl:right-20">
          {capabilities.map((item, index) => <div key={item.title} className={`flex min-h-[58px] items-center gap-2.5 px-3 py-1 ${index > 0 ? "sm:border-s sm:border-slate-400/40" : ""}`}><span className="flex size-8 shrink-0 items-center justify-center text-blue-600"><CapabilityIcon type={item.icon} /></span><div><p className="text-xs font-extrabold text-[#071c33]">{t(item.title)}</p><p className="mt-0.5 text-[10px] text-slate-600">{t(item.subtitle)}</p></div></div>)}
        </div>
      </section>
    </main>
  );
}
