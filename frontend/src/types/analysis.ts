import type {
  FeatureCollection,
  Geometry,
} from "geojson";


export type Severity =
  | "critical"
  | "high"
  | "medium"
  | "low"
  | "warning";

export type LayerType = "roads" | "buildings";

export interface VisionElement {
  element: "title" | "legend" | "scale" | "north_arrow";
  present: boolean;
  confidence: number | null;
  location: unknown | null;
}

export interface VisionIssue {
  error_type: string;
  severity: Severity;
  message: string;
  confidence: number | null;
}

export interface VisionAnalysisResponse {
  filename: string;
  status: "completed";
  elements: VisionElement[];
  issues: VisionIssue[];
  quality_checks: Record<string, number>;
  geotiff: GeoTiffMetadata | null;
  compliance_score: number;
  model_status: string;
  analysis_id?: string | null;
}

export interface GeoTiffMetadata {
  available: boolean;
  crs?: string | null;
  bounds?: number[];
  pixel_size?: number[];
  bands?: number;
  dtype?: string[];
  nodata?: number | null;
  nodata_ratio?: number | null;
  width?: number;
  height?: number;
  message?: string;
}

export type ReviewStatus = "new" | "confirmed" | "resolved" | "false_positive";
export interface ErrorReview { result_id: number; status: ReviewStatus; comment: string; updated_at: string | null; }

export interface InsertionResult {
  status: string;
  message?: string;
  table_name?: string;
  inserted_rows?: number;
  crs?: string | null;
  geometry_types?: string[];
}

export interface ValidationSummaryItem {
  rule_id: string;
  layer_name: string;
  error_type: string;
  severity: Severity;
  errors_found: number;
}

export interface ValidationError {
  result_id: number;
  run_id: string;
  layer_name: string;
  feature_id: string;
  rule_id: string;
  error_type: string;
  severity: Severity;
  details: string;
  detected_at: string | null;
  geometry?: Geometry | null;
}

export interface ValidationResult {
  status: string;
  layer_name: string;
  run_id: string;
  total_errors: number;
  summary: ValidationSummaryItem[];
  errors: ValidationError[];
}

export interface AgentAnalysis {
  result_id: number;
  run_id: string;
  layer_name: string;
  feature_id: string;
  rule_id: string;
  error_type: string;
  severity: Severity;
  status: string;
  explanation: string;
  cause: string;
  recommendation: string;
  human_review_required: boolean;
  related_features: string[];
  insufficient_context: boolean;
  agent_model: string;
}

export interface AnalysisSummary {
  total_errors: number;
  critical_errors: number;
  high_errors: number;
  medium_errors: number;
  low_errors: number;
  most_common_error: string | null;
  counts_by_rule: Record<string, number>;
  counts_by_layer: Record<string, number>;
  human_review_pending: number;
  analyzed: number;
  priority_actions: string[];
}

export interface ErrorAnalysisResult {
  run_id: string;
  results_loaded: number;
  analyses: AgentAnalysis[];
  summary: AnalysisSummary;
  trace: string[];
  errors: string[];
}

export interface VectorProcessingResponse {
  filename: string;
  status: "completed";
  layer_name: LayerType;
  run_id: string;
  insertion: InsertionResult;
  validation: ValidationResult;
  analysis: ErrorAnalysisResult;
  compliance_score: number;
  layer_geojson?: FeatureCollection;
  analysis_id?: string | null;
}

export type ProcessingResult =
  | VectorProcessingResponse
  | VisionAnalysisResponse;

export type UserRole = "manager" | "leader" | "member";
export interface AuthUser { user_id: string; name: string; email: string | null; username: string | null; must_change_password: boolean; role: UserRole | null; team_id: string | null; team_name: string | null; invite_code?: string | null; }
export interface AuthResponse { token: string; user: AuthUser; }
export interface SavedAnalysisSummary {
  analysis_id: string;
  filename: string;
  analysis_type: "vector" | "image";
  status: string;
  compliance_score: number | null;
  total_errors: number;
  created_at: string;
  user_id: string;
  owner_name: string;
}
export interface TeamMember { user_id: string; name: string; email: string | null; role: UserRole; created_at: string; last_seen: string | null; is_online: boolean; active_seconds_today: number; analyses_count: number; total_errors: number; }
export interface TeamDashboardData { team: { team_id: string; name: string; invite_code: string }; summary: { active_members: number; analyses_count: number; total_errors: number; average_compliance: number | null }; members: TeamMember[]; }
export interface MemberWorkDashboard { member: { user_id: string; name: string; email: string | null; role: UserRole; active_seconds_today: number; work_hours_today: number; work_percentage: number }; summary: { analyses_count: number; analyses_today: number; total_errors: number; average_compliance: number | null }; recent_analyses: Array<{ analysis_id: string; filename: string; analysis_type: "vector" | "image"; total_errors: number; compliance_score: number | null; created_at: string }>; }
export interface TeamMembership { team_id: string; name: string; role: UserRole; joined_at?: string; invite_code?: string | null; }
export interface NewUserPreview { action: "add" | "remove" | "create_team" | "delete_team" | "change_role" | "list_members" | "team_summary"; name: string | null; email: string | null; team_name: string | null; role: "leader" | "member"; suggested_username: string | null; missing_fields: string[]; }
export interface CreatedTeamUser { user_id: string; name: string; email: string; personal_email: string | null; username: string; role: "leader" | "member"; temporary_password: string; must_change_password: true; welcome_email_sent: boolean; }
