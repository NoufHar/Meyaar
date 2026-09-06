"use client";

import { useState } from "react";
import { login, register } from "@/lib/api";
import type { AuthUser } from "@/types/analysis";

export default function AuthScreen({ onAuthenticated }: { onAuthenticated: (user: AuthUser) => void }) {
  const openedFromInvite = typeof window !== "undefined" && new URLSearchParams(window.location.search).has("invite");
  const [mode, setMode] = useState<"login" | "register">(openedFromInvite ? "register" : "login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: React.FormEvent) {
    event.preventDefault(); setLoading(true); setError("");
    try {
      const response = mode === "login" ? await login(email, password) : await register(name, email, password);
      onAuthenticated(response.user);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Authentication failed."); }
    finally { setLoading(false); }
  }

  return <main className="flex min-h-screen items-center justify-center bg-[#eef5ff] p-5">
    <section className="w-full max-w-md rounded-3xl border border-blue-100 bg-white p-8 shadow-xl">
      <p className="text-sm font-extrabold uppercase tracking-[.2em] text-blue-600">Meyaar</p>
      <h1 className="mt-3 text-3xl font-extrabold text-[#071c33]">{mode === "login" ? "Sign in" : "Create account"}</h1>
      <p className="mt-2 text-sm text-slate-500">Access your analyses and saved geospatial results.</p>
      <form onSubmit={submit} className="mt-7 space-y-4">
        {mode === "register" && <label className="block text-sm font-semibold text-slate-700">Name<input required minLength={2} value={name} onChange={(e) => setName(e.target.value)} className="mt-2 w-full rounded-xl border border-slate-300 px-4 py-3 outline-none focus:border-blue-500" /></label>}
        <label className="block text-sm font-semibold text-slate-700">{mode === "login" ? "Email or username" : "Email"}<input required type={mode === "login" ? "text" : "email"} value={email} onChange={(e) => setEmail(e.target.value)} className="mt-2 w-full rounded-xl border border-slate-300 px-4 py-3 outline-none focus:border-blue-500" /></label>
        <label className="block text-sm font-semibold text-slate-700">Password<input required minLength={mode === "register" ? 8 : 1} type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="mt-2 w-full rounded-xl border border-slate-300 px-4 py-3 outline-none focus:border-blue-500" /></label>
        {error && <p className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p>}
        <button disabled={loading} className="w-full rounded-xl bg-blue-600 py-3 font-bold text-white disabled:bg-slate-400">{loading ? "Please wait..." : mode === "login" ? "Sign in" : "Create account"}</button>
      </form>
      <button type="button" onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }} className="mt-5 w-full text-sm font-bold text-blue-700">{mode === "login" ? "New? Create an account" : "Already have an account? Sign in"}</button>
    </section>
  </main>;
}
