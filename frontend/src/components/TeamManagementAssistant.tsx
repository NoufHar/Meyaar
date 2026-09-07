"use client";

import { useState } from "react";
import { activateTeam, createTeam, createTeamUser, deleteTeam, getMe, interpretTeamCommands, removeTeamMember, updateTeamMemberRole } from "@/lib/api";
import type { AuthUser, NewUserPreview, TeamCommandPlan, TeamDashboardData } from "@/types/analysis";

type Props = { data: TeamDashboardData; onClose: () => void; onComplete: (user: AuthUser) => void };

// Natural-language requests are converted into a reviewable plan. Nothing changes
// in the team until the manager confirms the actions displayed in the chat.
export default function TeamManagementAssistant({ data, onClose, onComplete }: Props) {
  const [instruction, setInstruction] = useState("");
  const [sentMessage, setSentMessage] = useState("");
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
    const matches = available.filter((member) =>
      [member.name, member.email || ""].some((value) => value.toLowerCase().includes(needle) || needle.includes(value.toLowerCase())),
    );
    return matches.length ? matches : available;
  }

  async function review() {
    const message = instruction.trim();
    if (!message) return;
    setBusy(true); setError(""); setResults(null); setSentMessage(message);
    try {
      const next = await interpretTeamCommands(message);
      const selections: Record<number, string> = {};
      next.actions.forEach((action, index) => {
        const matches = candidates(action);
        if ((action.action === "remove" || action.action === "change_role") && matches.length === 1) selections[index] = matches[0].user_id;
      });
      setMemberSelections(selections); setPlan(next); setInstruction("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The assistant could not understand the request.");
    } finally { setBusy(false); }
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
          completed.push(`Added ${created.name} as ${created.role}. Credentials were sent privately to ${created.personal_email}.`);
        } else if (action.action === "remove") {
          if (!activeTeamId || !memberSelections[index]) throw new Error(`Choose the member for action ${index + 1}.`);
          const selected = data.members.find((member) => member.user_id === memberSelections[index]);
          await removeTeamMember(activeTeamId, memberSelections[index]); completed.push(`Removed ${selected?.name ?? "member"} from the team.`);
        } else if (action.action === "change_role") {
          if (!activeTeamId || !memberSelections[index]) throw new Error(`Choose the member for action ${index + 1}.`);
          const selected = data.members.find((member) => member.user_id === memberSelections[index]);
          await updateTeamMemberRole(activeTeamId, memberSelections[index], action.role);
          completed.push(`Changed ${selected?.name ?? "member"} to ${action.role === "leader" ? "Team Leader" : "Member"}.`);
        } else if (action.action === "delete_team") {
          if (!activeTeamId) throw new Error("No active team to delete.");
          if ((deleteConfirmations[index] ?? "").trim() !== data.team.name) throw new Error(`Type ${data.team.name} to confirm team deletion.`);
          activeUser = await deleteTeam(activeTeamId); activeTeamId = activeUser.team_id; completed.push("Deleted the active team.");
        } else if (action.action === "list_members") completed.push(`Team has ${data.members.length} members.`);
        else if (action.action === "team_summary") completed.push(`${data.summary.analyses_count} analyses, ${data.summary.total_errors} errors, ${data.summary.average_compliance ?? "—"}% compliance.`);
      }
      if (activeTeamId) activeUser = await activateTeam(activeTeamId);
      setResults(completed); onComplete(activeUser);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The plan could not be completed.");
    } finally { setBusy(false); }
  }

  function resetChat() { setPlan(null); setResults(null); setSentMessage(""); setError(""); }

  return (
    <div className="fixed inset-0 z-[6000] flex items-center justify-center bg-slate-950/55 p-3" role="dialog" aria-modal="true">
      <section className="flex h-[min(760px,92vh)] w-full max-w-3xl flex-col overflow-hidden rounded-3xl bg-[#f4f7fb] shadow-2xl">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-5 py-4">
          <div className="flex items-center gap-3"><span className="flex size-10 items-center justify-center rounded-full bg-blue-600 font-black text-white">M</span><div><h2 className="font-black text-[#071c33]">Team management assistant</h2><p className="flex items-center gap-1.5 text-xs text-slate-500"><span className="size-2 rounded-full bg-emerald-500" />Online</p></div></div>
          <button type="button" onClick={onClose} aria-label="Close" className="flex size-9 items-center justify-center rounded-full bg-slate-100 text-xl text-slate-600">×</button>
        </header>

        <div className="flex-1 space-y-4 overflow-y-auto p-5">
          {!sentMessage && <AssistantBubble><p>Tell me what you want to do. You can create a team, add several members, assign roles, or remove members in one message.</p></AssistantBubble>}
          {sentMessage && <div className="flex justify-end"><div className="max-w-[82%] rounded-2xl rounded-tr-sm bg-blue-600 px-4 py-3 text-sm leading-6 text-white">{sentMessage}</div></div>}
          {busy && !plan && <AssistantBubble><p className="text-slate-500">Preparing your plan…</p></AssistantBubble>}

          {plan && <AssistantBubble wide><p>{plan.summary}</p><div className="mt-3 space-y-2">{plan.actions.map((action, index) => (
            <article key={index} className="rounded-xl border border-slate-200 bg-slate-50 p-3">
              <div className="flex items-center gap-2"><span className="flex size-6 items-center justify-center rounded-full bg-blue-100 text-xs font-black text-blue-700">{index + 1}</span><h3 className="text-sm font-bold capitalize">{action.action.replaceAll("_", " ")}</h3></div>
              {action.action === "create_team" && <input value={action.team_name ?? ""} onChange={(event) => updateAction(index, { team_name: event.target.value })} className="mt-2 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm" placeholder="Team name" />}
              {action.action === "add" && <div className="mt-2 grid gap-2 sm:grid-cols-3"><input value={action.name ?? ""} onChange={(event) => updateAction(index, { name: event.target.value })} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm" placeholder="Name" /><input type="email" value={action.email ?? ""} onChange={(event) => updateAction(index, { email: event.target.value })} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm" placeholder="Personal email" /><select value={action.role} onChange={(event) => updateAction(index, { role: event.target.value as "member" | "leader" })} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"><option value="member">Member</option><option value="leader">Team Leader</option></select></div>}
              {(action.action === "remove" || action.action === "change_role") && <div className="mt-2 grid gap-2 sm:grid-cols-2"><select required value={memberSelections[index] ?? ""} onChange={(event) => setMemberSelections({ ...memberSelections, [index]: event.target.value })} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"><option value="">Choose member</option>{candidates(action).map((member) => <option key={member.user_id} value={member.user_id}>{member.name} — {member.email}</option>)}</select>{action.action === "change_role" && <select value={action.role} onChange={(event) => updateAction(index, { role: event.target.value as "member" | "leader" })} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"><option value="member">Member</option><option value="leader">Team Leader</option></select>}</div>}
              {action.action === "delete_team" && <div className="mt-2"><p className="text-xs font-semibold text-red-600">This permanently deletes the active team and its analyses.</p><input value={deleteConfirmations[index] ?? ""} onChange={(event) => setDeleteConfirmations({ ...deleteConfirmations, [index]: event.target.value })} className="mt-2 w-full rounded-lg border border-red-200 bg-white px-3 py-2 text-sm" placeholder={`Type ${data.team.name} to confirm`} /></div>}
            </article>
          ))}</div>{!results && <div className="mt-3 flex justify-end gap-2"><button type="button" onClick={resetChat} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-bold text-slate-600">Edit</button><button type="button" disabled={busy} onClick={() => void execute()} className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-bold text-white disabled:bg-slate-400">{busy ? "Working…" : "Confirm"}</button></div>}</AssistantBubble>}

          {results && <AssistantBubble><p className="font-bold text-emerald-700">Completed</p><ul className="mt-2 space-y-1.5">{results.map((result, index) => <li key={`${index}-${result}`}>• {result}</li>)}</ul><button type="button" onClick={resetChat} className="mt-3 font-bold text-blue-600">Start another request</button></AssistantBubble>}
          {error && <div className="ml-11 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
        </div>

        <form onSubmit={(event) => { event.preventDefault(); void review(); }} className="border-t border-slate-200 bg-white p-4"><div className="flex items-end gap-2 rounded-2xl border border-slate-300 p-2 focus-within:border-blue-500"><textarea rows={1} disabled={Boolean(plan)} value={instruction} onChange={(event) => setInstruction(event.target.value)} className="max-h-28 min-h-10 flex-1 resize-none px-2 py-2 text-sm outline-none disabled:bg-white" placeholder={plan ? "Complete or edit the current plan" : "Message the team assistant…"} /><button type="submit" disabled={busy || Boolean(plan) || !instruction.trim()} aria-label="Send" className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-blue-600 text-lg text-white disabled:bg-slate-300">↑</button></div></form>
      </section>
    </div>
  );
}

function AssistantBubble({ children, wide = false }: { children: React.ReactNode; wide?: boolean }) {
  return <div className="flex gap-3"><span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-blue-600 text-xs font-black text-white">M</span><div className={`${wide ? "w-full max-w-[92%]" : "max-w-[86%]"} rounded-2xl rounded-tl-sm bg-white px-4 py-3 text-sm leading-6 text-slate-600 shadow-sm`}>{children}</div></div>;
}
