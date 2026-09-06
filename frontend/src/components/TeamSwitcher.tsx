"use client";

import { useEffect, useState } from "react";
import { activateTeam, listTeams } from "@/lib/api";
import type { AuthUser, TeamMembership } from "@/types/analysis";

export default function TeamSwitcher({ user, onChange }: { user: AuthUser; onChange: (user: AuthUser) => void }) {
  const [teams, setTeams] = useState<TeamMembership[]>([]);
  useEffect(() => { listTeams().then(setTeams).catch(() => setTeams([])); }, [user.team_id]);
  if (teams.length < 2) return <span className="hidden max-w-40 truncate text-xs font-bold text-slate-600 md:block">{user.team_name}</span>;
  return <select aria-label="Active team" value={user.team_id ?? ""} onChange={async (event) => onChange(await activateTeam(event.target.value))} className="max-w-48 rounded-lg border border-slate-200 bg-white px-2 py-2 text-xs font-bold text-[#071c33]">{teams.map((team) => <option key={team.team_id} value={team.team_id}>{team.name} · {team.role === "leader" ? "Team Leader" : team.role}</option>)}</select>;
}
