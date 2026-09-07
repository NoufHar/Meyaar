// Central browser client for authenticated MEYAAR backend requests.
import type {
  LayerType,
  VectorProcessingResponse,
  VisionAnalysisResponse,
  ProcessingResult,
  ErrorReview,
  ReviewStatus,
  AuthResponse,
  AuthUser,
  SavedAnalysisSummary,
  TeamDashboardData,
  MemberWorkDashboard,
  TeamMembership,
  NewUserPreview,
  CreatedTeamUser,
  TeamCommandPlan,
  UserDirectoryEntry,
} from "@/types/analysis";


const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000";

const TOKEN_KEY = "meyaar_auth_token";

export function getAuthToken() { return typeof window === "undefined" ? null : window.localStorage.getItem(TOKEN_KEY); }
export function setAuthToken(token: string | null) { if (typeof window === "undefined") return; if (token) window.localStorage.setItem(TOKEN_KEY, token); else window.localStorage.removeItem(TOKEN_KEY); }
function authHeaders(): HeadersInit { const token = getAuthToken(); return token ? { Authorization: `Bearer ${token}` } : {}; }


async function parseResponse<T>(
  response: Response,
): Promise<T> {
  if (!response.ok) {
    const fallbackMessages: Record<number, string> = {
      400: "The uploaded file is invalid or cannot be processed.",
      413: "The uploaded file is larger than the allowed limit.",
      415: "This file format is not supported.",
      502: "The external AI service is temporarily unavailable.",
      503: "A required backend service is not configured or unavailable.",
    };
    let message = fallbackMessages[response.status] ??
      `Request failed with status ${response.status}`;

    try {
      const body = (await response.json()) as {
        detail?: string;
      };

      if (body.detail) {
        message = body.detail;
      }
    } catch {
      // Keep the default HTTP error message.
    }

    throw new Error(message);
  }

  return (await response.json()) as T;
}


export async function checkBackendHealth(): Promise<boolean> {
  try {
    const response = await fetch(
      `${API_BASE_URL}/health`,
    );

    return response.ok;
  } catch {
    return false;
  }
}


export async function analyzeMapImage(
  file: File,
  onProgress?: (percent: number) => void,
): Promise<VisionAnalysisResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return uploadWithProgress<VisionAnalysisResponse>(`${API_BASE_URL}/images/analyze`, formData, onProgress);
}


export async function processVectorFile(
  file: File,
  layerType?: LayerType,
  onProgress?: (percent: number) => void,
): Promise<VectorProcessingResponse> {
  const formData = new FormData();

  formData.append("file", file);

  if (layerType) {
    formData.append("layer_type", layerType);
  }

  return uploadWithProgress<VectorProcessingResponse>(`${API_BASE_URL}/vectors/process`, formData, onProgress);
}

// XMLHttpRequest exposes upload progress events that fetch does not currently provide.
function uploadWithProgress<T>(url: string, body: FormData, onProgress?: (percent: number) => void): Promise<T> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", url);
    const token = getAuthToken();
    if (token) request.setRequestHeader("Authorization", `Bearer ${token}`);
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress?.(Math.round((event.loaded / event.total) * 100));
    };
    request.onerror = () => reject(new Error("Cannot connect to the backend. Make sure FastAPI and PostGIS are running."));
    request.onload = () => {
      let payload: unknown;
      try { payload = JSON.parse(request.responseText); }
      catch { return reject(new Error(request.responseText || `Request failed with status ${request.status}.`)); }
      if (request.status < 200 || request.status >= 300) {
        const detail = typeof payload === "object" && payload && "detail" in payload ? String((payload as { detail: unknown }).detail) : `Request failed with status ${request.status}.`;
        return reject(new Error(detail));
      }
      onProgress?.(100);
      resolve(payload as T);
    };
    request.send(body);
  });
}

export async function register(name: string, email: string, password: string): Promise<AuthResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/register`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, email, password }) });
  const data = await parseResponse<AuthResponse>(response); setAuthToken(data.token); return data;
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/login`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password }) });
  const data = await parseResponse<AuthResponse>(response); setAuthToken(data.token); return data;
}

export async function getMe(): Promise<AuthUser> { return parseResponse<AuthUser>(await fetch(`${API_BASE_URL}/auth/me`, { headers: authHeaders() })); }
export async function updatePresence(): Promise<void> { await fetch(`${API_BASE_URL}/auth/presence`, { method: "POST", headers: authHeaders() }); }
export async function logout(): Promise<void> { await fetch(`${API_BASE_URL}/auth/logout`, { method: "POST", headers: authHeaders() }); setAuthToken(null); }
export async function listAnalyses(): Promise<SavedAnalysisSummary[]> { return parseResponse<SavedAnalysisSummary[]>(await fetch(`${API_BASE_URL}/analyses`, { headers: authHeaders() })); }
export async function loadAnalysis(id: string): Promise<ProcessingResult> { return parseResponse<ProcessingResult>(await fetch(`${API_BASE_URL}/analyses/${id}`, { headers: authHeaders() })); }
export async function downloadBatchPdf(analysisIds: string[]): Promise<void> { const response = await fetch(`${API_BASE_URL}/reports/pdf/batch`, { method: "POST", headers: { "Content-Type": "application/json", ...authHeaders() }, body: JSON.stringify({ analysis_ids: analysisIds }) }); if (!response.ok) { await parseResponse(response); return; } const blob = await response.blob(); downloadBlob(blob, "meyaar-selected-analyses.pdf"); }
export async function downloadBatchJson(analysisIds: string[]): Promise<void> { const results = await Promise.all(analysisIds.map(loadAnalysis)); downloadBlob(new Blob([JSON.stringify({ exported_at: new Date().toISOString(), analyses: results }, null, 2)], { type: "application/json" }), "meyaar-selected-analyses.json"); }

function downloadBlob(blob: Blob, filename: string) { const url = URL.createObjectURL(blob); const anchor = document.createElement("a"); anchor.href = url; anchor.download = filename; anchor.click(); URL.revokeObjectURL(url); }
export async function getTeamDashboard(): Promise<TeamDashboardData> { return parseResponse<TeamDashboardData>(await fetch(`${API_BASE_URL}/team/dashboard`, { headers: authHeaders() })); }
export async function getMemberWorkDashboard(userId: string): Promise<MemberWorkDashboard> { return parseResponse<MemberWorkDashboard>(await fetch(`${API_BASE_URL}/team/members/${userId}/dashboard`, { headers: authHeaders() })); }
export async function inviteTeamMember(email: string): Promise<{ status: string; email: string }> { return parseResponse(await fetch(`${API_BASE_URL}/team/invitations`, { method: "POST", headers: { "Content-Type": "application/json", ...authHeaders() }, body: JSON.stringify({ email }) })); }
export async function listTeams(): Promise<TeamMembership[]> { return parseResponse(await fetch(`${API_BASE_URL}/teams`, { headers: authHeaders() })); }
export async function createTeam(name: string): Promise<TeamMembership> { return parseResponse(await fetch(`${API_BASE_URL}/teams`, { method: "POST", headers: { "Content-Type": "application/json", ...authHeaders() }, body: JSON.stringify({ name }) })); }
export async function joinTeam(inviteCode: string): Promise<TeamMembership> { return parseResponse(await fetch(`${API_BASE_URL}/teams/join`, { method: "POST", headers: { "Content-Type": "application/json", ...authHeaders() }, body: JSON.stringify({ invite_code: inviteCode }) })); }
export async function activateTeam(teamId: string): Promise<AuthUser> { return parseResponse(await fetch(`${API_BASE_URL}/teams/${teamId}/activate`, { method: "POST", headers: authHeaders() })); }
export async function updateTeamMemberRole(teamId: string, userId: string, role: "leader" | "member"): Promise<void> { await parseResponse(await fetch(`${API_BASE_URL}/teams/${teamId}/members/${userId}/role`, { method: "PATCH", headers: { "Content-Type": "application/json", ...authHeaders() }, body: JSON.stringify({ role }) })); }
export async function removeTeamMember(teamId: string, userId: string): Promise<void> { const response = await fetch(`${API_BASE_URL}/teams/${teamId}/members/${userId}`, { method: "DELETE", headers: authHeaders() }); if (!response.ok) await parseResponse(response); }
export async function changePassword(currentPassword: string, newPassword: string): Promise<void> { const response = await fetch(`${API_BASE_URL}/auth/password`, { method: "PUT", headers: { "Content-Type": "application/json", ...authHeaders() }, body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }) }); if (!response.ok) await parseResponse(response); }
export async function deleteTeam(teamId: string): Promise<AuthUser> { return parseResponse(await fetch(`${API_BASE_URL}/teams/${teamId}`, { method: "DELETE", headers: authHeaders() })); }
export async function interpretNewUser(instruction: string): Promise<NewUserPreview> { return parseResponse(await fetch(`${API_BASE_URL}/team/users/interpret`, { method: "POST", headers: { "Content-Type": "application/json", ...authHeaders() }, body: JSON.stringify({ instruction }) })); }
export async function interpretTeamCommands(instruction: string): Promise<TeamCommandPlan> { return parseResponse(await fetch(`${API_BASE_URL}/team/commands/interpret`, { method: "POST", headers: { "Content-Type": "application/json", ...authHeaders() }, body: JSON.stringify({ instruction }) })); }
export async function searchUserDirectory(query: string): Promise<UserDirectoryEntry[]> { return parseResponse(await fetch(`${API_BASE_URL}/team/user-directory?query=${encodeURIComponent(query)}`, { headers: authHeaders() })); }
export async function addExistingTeamMember(teamId: string, userId: string, role: "leader" | "member"): Promise<UserDirectoryEntry & { role: string }> { return parseResponse(await fetch(`${API_BASE_URL}/teams/${teamId}/members`, { method: "POST", headers: { "Content-Type": "application/json", ...authHeaders() }, body: JSON.stringify({ user_id: userId, role }) })); }
export async function createTeamUser(preview: NewUserPreview): Promise<CreatedTeamUser> { return parseResponse(await fetch(`${API_BASE_URL}/team/users`, { method: "POST", headers: { "Content-Type": "application/json", ...authHeaders() }, body: JSON.stringify(preview) })); }

export async function getErrorReview(resultId: number): Promise<ErrorReview> {
  const response = await fetch(`${API_BASE_URL}/reviews/${resultId}`, { headers: authHeaders() });
  return parseResponse<ErrorReview>(response);
}

export async function updateErrorReview(resultId: number, status: ReviewStatus, comment: string): Promise<ErrorReview> {
  const response = await fetch(`${API_BASE_URL}/reviews/${resultId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ status, comment }),
  });
  return parseResponse<ErrorReview>(response);
}

export async function downloadPdfReport(result: ProcessingResult): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/reports/pdf`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(result),
  });
  if (!response.ok) {
    await parseResponse<never>(response);
    return;
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${result.filename.replace(/\.[^.]+$/, "")}-meyaar-report.pdf`;
  anchor.click();
  URL.revokeObjectURL(url);
}
