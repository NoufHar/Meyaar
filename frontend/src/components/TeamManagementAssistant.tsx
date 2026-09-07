"use client";

import { useState } from "react";
import { activateTeam, createTeam, createTeamUser, deleteTeam, getMe, interpretTeamCommands, removeTeamMember, updateTeamMemberRole } from "@/lib/api";
import type { AuthUser, NewUserPreview, TeamDashboardData, TeamCommandPlan } from "@/types/analysis";

// This dialog separates natural-language planning from execution: nothing changes until the manager confirms.
export default function TeamManagementAssistant({ data, onClose, onComplete }: { data: TeamDashboardData; onClose: () => void; onComplete: (user: AuthUser) => void }) {
  const [instruction, setInstruction] = useState("");
  const [plan, setPlan] = useState<TeamCommandPlan | null>(null);
  const [memberSelections, setMemberSelections] = useState<Record<number, string>>({});
  const [deleteConfirmations, setDeleteConfirmations] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [results, setResults] = useState<string[] | null>(null);

  function candidates(action: NewUserPreview) {
    const available = data.members.filter((member) => member.role !== "manager");
    const needle = (action.email || action.name || "").trim().toLowerCase();
    if (!needle) return available;
    const matches = available.filter((member) => [member.name, member.email || ""].some((value) => value.toLowerCase().includes(needle) || needle.includes(value.toLowerCase())));
    return matches.length ? matches : available;
  }

  async function review() {
    setBusy(true); setError(""); setResults(null);
    try {
      const next = await interpretTeamCommands(instruction);
      const selections: Record<number, string> = {};
      next.actions.forEach((action, index) => { const matches = candidates(action); if ((action.action === "remove" || action.action === "change_role") && matches.length === 1) selections[index] = matches[0].user_id; });
      setMemberSelections(selections); setPlan(next);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "The assistant could not understand the request."); }
    finally { setBusy(false); }
  }

  function updateAction(index: number, patch: Partial<NewUserPreview>) {
    if (!plan) return;
    setPlan({ ...plan, actions: plan.actions.map((action, actionIndex) => actionIndex === index ? { ...action, ...patch } : action) });
  }

  async function execute() {
    if (!plan) return;
    setBusy(true); setError("");
    const completed: string[] = [];
    try {
      let activeUser = await getMe();
      let activeTeamId = activeUser.team_id;
      for (let index = 0; index < plan.actions.length; index += 1) {
        const action = plan.actions[index];
        if (action.action === "create_team") {
          if (!action.team_name?.trim()) throw new Error("Enter a name for the new team.");
          await createTeam(action.team_name.trim()); activeUser = await getMe(); activeTeamId = activeUser.team_id;
          completed.push(`Created team: ${action.team_name}`);
        } else if (action.action === "add") {
          if (!action.name?.trim() || !action.email?.trim()) throw new Error(`A name and personal email are required for action ${index + 1}.`);
          const created = await createTeamUser(action);
          completed.push(`Added ${created.name} as ${created.role}. Credentials sent privately to ${created.personal_email}.`);
        } else if (action.action === "remove") {
          if (!activeTeamId || !memberSelections[index]) throw new Error(`Choose the member for action ${index + 1}.`);
          const selected = data.members.find((member) => member.user_id === memberSelections[index]);
          await removeTeamMember(activeTeamId, memberSelections[index]); completed.push(`Removed ${selected?.name ?? "member"} from the team.`);
        } else if (action.action === "change_role") {
          if (!activeTeamId || !memberSelections[index]) throw new Error(`Choose the member for action ${index + 1}.`);
          const selected = data.members.find((member) => member.user_id === memberSelections[index]);
          await updateTeamMemberRole(activeTeamId, memberSelections[index], action.role); completed.push(`Changed ${selected?.name ?? "member"} to ${action.role === "leader" ? "Team Leader" : "Member"}.`);
        } else if (action.action === "delete_team") {
          if (!activeTeamId) throw new Error("No active team to delete.");
          if ((deleteConfirmations[index] ?? "").trim() !== data.team.name) throw new Error(`Type ${data.team.name} to confirm team deletion.`);
          activeUser = await deleteTeam(activeTeamId); activeTeamId = activeUser.team_id; completed.push("Deleted the active team.");
        } else if (action.action === "list_members") completed.push(`Team has ${data.members.length} members.`);
        else if (action.action === "team_summary") completed.push(`${data.summary.analyses_count} analyses, ${data.summary.total_errors} errors, ${data.summary.average_compliance ?? "—"}% compliance.`);
      }
      if (activeTeamId) activeUser = await activateTeam(activeTeamId);
      setResults(completed); onComplete(activeUser);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "The plan could not be completed."); }
    finally { setBusy(false); }
  }

  return <div className="fixed inset-0 z-[6000] flex items-center justify-center bg-slate-950/55 p-4" role="dialog" aria-modal="true"><section className="max-h-[92vh] w-full max-w-3xl overflow-y-auto rounded-3xl bg-[#f5f8fc] p-5 shadow-2xl"><header className="flex items-start justify-between"><div><p className="text-xs font-bold tracking-widest text-blue-600">MEYAAR AI</p><h2 className="mt-1 text-2xl font-black text-[#071c33]">Team management assistant</h2><p className="mt-1 text-sm text-slate-500">Describe several tasks in one message. Review everything before execution.</p></div><button type="button" onClick={onClose} className="rounded-full bg-white px-3 py-1.5 text-lg shadow-sm">×</button></header>{results ? <div className="mt-5 rounded-2xl border border-emerald-200 bg-white p-5"><h3 className="font-bold text-emerald-700">Completed</h3><ul className="mt-3 space-y-2 text-sm text-slate-600">{results.map((result) => <li key={result} className="flex gap-2"><span className="text-emerald-500">✓</span>{result}</li>)}</ul><button type="button" onClick={onClose} className="mt-5 w-full rounded-xl bg-blue-600 py-3 font-bold text-white">Done</button></div> : !plan ? <form onSubmit={(event) => { event.preventDefault(); void review(); }} className="mt-5 rounded-2xl bg-white p-5 shadow-sm"><label className="text-sm font-semibold">What should I do?<textarea required rows={5} value={instruction} onChange={(event) => setInstruction(event.target.value)} className="mt-2 w-full resize-none rounded-xl border border-slate-300 p-4 leading-6 outline-none focus:border-blue-500" placeholder="Create a team named Maps, add Mohammed as leader using mohammed@gmail.com, and add Nouf using nouf@gmail.com"/></label>{error && <p className="mt-3 rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p>}<button disabled={busy} className="mt-4 w-full rounded-xl bg-blue-600 py-3 font-bold text-white disabled:bg-slate-400">{busy ? "Preparing plan..." : "Review plan"}</button></form> : <div className="mt-5"><div className="rounded-xl border border-blue-100 bg-blue-50 p-3 text-sm text-blue-800">{plan.summary}</div><div className="mt-3 space-y-3">{plan.actions.map((action, index) => <article key={index} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"><div className="flex items-center gap-3"><span className="flex size-7 items-center justify-center rounded-full bg-blue-50 text-xs font-black text-blue-600">{index + 1}</span><h3 className="font-bold capitalize">{action.action.replaceAll("_", " ")}</h3></div>{action.action === "create_team" && <input value={action.team_name ?? ""} onChange={(event) => updateAction(index, { team_name: event.target.value })} className="mt-3 w-full rounded-xl border border-slate-300 px-4 py-2.5" placeholder="Team name"/>}{action.action === "add" && <div className="mt-3 grid gap-2 sm:grid-cols-3"><input value={action.name ?? ""} onChange={(event) => updateAction(index, { name: event.target.value })} className="rounded-xl border border-slate-300 px-3 py-2.5" placeholder="Name"/><input type="email" value={action.email ?? ""} onChange={(event) => updateAction(index, { email: event.target.value })} className="rounded-xl border border-slate-300 px-3 py-2.5" placeholder="Personal email"/><select value={action.role} onChange={(event) => updateAction(index, { role: event.target.value as "member" | "leader" })} className="rounded-xl border border-slate-300 bg-white px-3 py-2.5"><option value="member">Member</option><option value="leader">Team Leader</option></select></div>}{(action.action === "remove" || action.action === "change_role") && <div className="mt-3 grid gap-2 sm:grid-cols-2"><select required value={memberSelections[index] ?? ""} onChange={(event) => setMemberSelections({ ...memberSelections, [index]: event.target.value })} className="rounded-xl border border-slate-300 bg-white px-3 py-2.5"><option value="">Choose member</option>{candidates(action).map((member) => <option key={member.user_id} value={member.user_id}>{member.name} — {member.email}</option>)}</select>{action.action === "change_role" && <select value={action.role} onChange={(event) => updateAction(index, { role: event.target.value as "member" | "leader" })} className="rounded-xl border border-slate-300 bg-white px-3 py-2.5"><option value="member">Member</option><option value="leader">Team Leader</option></select>}</div>}{action.action === "delete_team" && <div className="mt-3"><p className="text-sm font-semibold text-red-600">The active team and its saved analyses will be permanently deleted.</p><input value={deleteConfirmations[index] ?? ""} onChange={(event) => setDeleteConfirmations({ ...deleteConfirmations, [index]: event.target.value })} className="mt-2 w-full rounded-xl border border-red-200 px-3 py-2.5" placeholder={`Type ${data.team.name} to confirm`}/></div>}</article>)}</div>{error && <p className="mt-3 rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p>}<div className="mt-4 grid grid-cols-2 gap-3"><button type="button" onClick={() => setPlan(null)} className="rounded-xl border border-slate-300 bg-white py-3 font-bold">Edit request</button><button type="button" disabled={busy} onClick={() => void execute()} className="rounded-xl bg-blue-600 py-3 font-bold text-white disabled:bg-slate-400">{busy ? "Executing..." : `Confirm ${plan.actions.length} actions`}</button></div></div>}</section></div>;
}
