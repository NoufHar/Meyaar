"use client";

import { useState } from "react";
import { createTeam, getMe, joinTeam } from "@/lib/api";
import type { AuthUser } from "@/types/analysis";

export default function TeamOnboarding({ user, onReady, embedded = false }: { user: AuthUser; onReady: (user: AuthUser) => void; embedded?: boolean }) {
  const initialCode = typeof window === "undefined" ? "" : new URLSearchParams(window.location.search).get("invite")?.toUpperCase() ?? "";
  const [choice, setChoice] = useState<"create" | "join">(initialCode ? "join" : "create");
  const [teamName, setTeamName] = useState("");
  const [inviteCode, setInviteCode] = useState(initialCode);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: React.FormEvent) {
    event.preventDefault(); setLoading(true); setError("");
    try { if (choice === "create") await createTeam(teamName); else await joinTeam(inviteCode); onReady(await getMe()); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not complete team setup."); }
    finally { setLoading(false); }
  }

  return <main className={`flex items-center justify-center ${embedded ? "min-h-[520px] rounded-3xl border border-slate-200 bg-white/50 p-5" : "min-h-screen bg-[#eef5ff] p-5"}`}><section className="w-full max-w-xl rounded-3xl border border-blue-100 bg-white p-7 shadow-xl"><p className="text-xs font-black tracking-[.2em] text-blue-600">MEYAAR</p><h1 className="mt-2 text-3xl font-extrabold text-[#071c33]">{embedded ? "Manage your teams" : `Welcome, ${user.name}`}</h1><p className="mt-2 text-sm text-slate-500">Create your own team or join an existing team. Your role is assigned securely inside each team.</p><div className="mt-6 grid grid-cols-2 gap-3"><button type="button" onClick={() => setChoice("create")} className={`rounded-2xl border p-4 text-start ${choice === "create" ? "border-blue-600 bg-blue-50" : "border-slate-200"}`}><span className="block font-bold">Create a team</span><span className="mt-1 block text-xs text-slate-500">You become the Manager</span></button><button type="button" onClick={() => setChoice("join")} className={`rounded-2xl border p-4 text-start ${choice === "join" ? "border-blue-600 bg-blue-50" : "border-slate-200"}`}><span className="block font-bold">Join a team</span><span className="mt-1 block text-xs text-slate-500">You join as a Member</span></button></div><form onSubmit={submit} className="mt-5 space-y-4">{choice === "create" ? <label className="block text-sm font-semibold">Team name<input required minLength={2} value={teamName} onChange={(event) => setTeamName(event.target.value)} className="mt-2 w-full rounded-xl border border-slate-300 px-4 py-3 outline-none focus:border-blue-500" placeholder="Geospatial Quality Team"/></label> : <label className="block text-sm font-semibold">Invitation code<input required value={inviteCode} onChange={(event) => setInviteCode(event.target.value.toUpperCase())} className="mt-2 w-full rounded-xl border border-slate-300 px-4 py-3 font-mono uppercase outline-none focus:border-blue-500" placeholder="A1B2C3D4"/></label>}{error && <p className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p>}<button disabled={loading} className="w-full rounded-xl bg-blue-600 py-3 font-bold text-white disabled:bg-slate-400">{loading ? "Please wait..." : choice === "create" ? "Create team" : "Join team"}</button></form><p className="mt-4 text-xs leading-5 text-slate-500">A Manager can later promote a Member to Team Leader. Users cannot grant themselves elevated permissions.</p></section></main>;
}
