"use client";

import Image from "next/image";
import { useLanguage } from "@/components/LanguageProvider";

export type AppView = "dashboard" | "team" | "profile" | "upload" | "analysis" | "reports" | "history" | "assistant";

interface AppSidebarProps {
  activeView: AppView;
  onNavigate: (view: AppView) => void;
}

const items: Array<{ view: AppView; label: string; icon: string }> = [
  { view: "dashboard", label: "Dashboard", icon: "⌂" },
  { view: "upload", label: "Upload Data", icon: "⇧" },
  { view: "analysis", label: "Analysis", icon: "▥" },
  { view: "reports", label: "Reports", icon: "▤" },
  { view: "history", label: "Saved Analyses", icon: "◷" },
];

export default function AppSidebar({ activeView, onNavigate }: AppSidebarProps) {
  const { t } = useLanguage();
  return (
    <aside className="flex w-full shrink-0 flex-col bg-[#071c33] text-white shadow-2xl shadow-slate-950/10 lg:fixed lg:inset-y-0 lg:left-0 lg:w-56 rtl:lg:left-auto rtl:lg:right-0">
      <div className="flex h-[72px] items-center gap-3 border-b border-white/10 px-5">
        <Image src="/branding/meyaar-logo.png" alt="Meyaar logo" width={38} height={38} className="size-9 rounded-lg bg-white object-cover shadow-md ring-1 ring-white/20" />
        <p className="text-lg font-black tracking-[0.08em] text-white">MEYAAR</p>
      </div>
      <nav className="flex gap-2 overflow-x-auto p-3 lg:flex-1 lg:flex-col lg:overflow-visible lg:p-4 lg:pt-5">
        {items.map((item) => (
          <button key={item.view} type="button" onClick={() => onNavigate(item.view)} className={`flex min-w-fit items-center gap-2.5 rounded-xl px-3.5 py-3 text-[13px] font-semibold transition lg:w-full ${activeView === item.view ? 'bg-blue-600 text-white shadow-lg shadow-blue-950/30' : 'text-slate-300 hover:bg-white/10 hover:text-white'}`}>
            <span className="w-5 text-center text-base">{item.icon}</span>{t(item.label)}
          </button>
        ))}
      </nav>
      <div className="hidden border-t border-white/10 p-4 text-[11px] text-slate-400 lg:block">Saudi geospatial quality platform</div>
    </aside>
  );
}
