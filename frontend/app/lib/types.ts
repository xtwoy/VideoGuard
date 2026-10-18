/**
 * Wire types for the review API.
 *
 * These mirror the JSON the backend returns. Nothing here is frontend-specific
 * state; keep it that way so the API contract stays readable in one place.
 */

export type Coverage = "FULL" | "PARTIAL" | "UNKNOWN" | "REFUSED" | "ERROR";
export type Judgement = "SUPPORTED" | "NOT_SUPPORTED" | "INSUFFICIENT" | "CONFLICTED" | "UNKNOWN";
export type Disposition = "FLAG" | "NONE" | "REVIEW" | "VERIFY_EXTERNAL" | "RECHECK" | "RETRY";

export type Observation = {
  id: string;
  modality: string;
  start_ms: number | null;
  end_ms: number | null;
  description_redacted: string;
  text_redacted: string;
};

export type Finding = {
  id?: string;
  policy_id: string;
  name?: string;
  judgement: Judgement;
  disposition: Disposition;
  reason_code: string;
  supporting_ids: string[];
  counter_ids: string[];
  /** How sure the upstream cue is — separate from how severe the risk would be. */
  evidence_confidence?: "HIGH" | "LOW";
  needs_human_review?: boolean;
};

export type EventFinding = {
  event_id: string;
  policy_id: string;
  /** This policy's own evidence within the event. */
  evidence_ids: string[];
  /** Other cues in the same event: background, not this finding's proof. */
  context_evidence_ids?: string[];
  judgement: Judgement;
  disposition: Disposition;
  reason_code: string;
};

export type AuditStatus = "PASS" | "WARNING" | "FAIL" | "MANUAL_REVIEW" | "NOT_APPLICABLE";
export type AuditVerdict = "PUBLISHABLE" | "NEEDS_REVISION" | "BLOCKED" | "MANUAL_REVIEW";

export type AuditTimeRange = {
  start_ms: number;
  end_ms: number;
  evidence_refs: string[];
};

export type AuditDimension = {
  score: number;
  status: AuditStatus;
  summary: string;
  items: Array<{
    key: string;
    label: string;
    score: number;
    status: AuditStatus;
    summary: string;
    evidence_refs: string[];
    time_ranges: AuditTimeRange[];
    limitations: string[];
  }>;
  evidence_refs: string[];
  time_ranges: AuditTimeRange[];
  limitations: string[];
};

export type AuditAction = "MASK" | "REMOVE" | "TRIM" | "REORDER" | "REPLACE" | "ADD_CONTEXT" | "EDIT_TEXT" | "EDIT_AUDIO" | "RECORD" | "ADD_MEDIA" | "VERIFY" | "MANUAL_REVIEW";

export type AuditRevisionPlan = {
  id: string;
  section: string;
  scope: "EVENT" | "GLOBAL";
  event_id: string | null;
  video: { summary: string; time_ranges: AuditTimeRange[] };
  issues: Array<{
    id: string;
    priority: "P0" | "P1" | "P2";
    category: string;
    title: string;
    description: string;
    time_ranges: AuditTimeRange[];
    supporting_evidence: Array<{
      ref: string;
      type: "OBSERVATION" | "FACT" | "EVENT" | "ANALYSIS";
      content: string;
      time_ranges: AuditTimeRange[];
      limitations: string[];
    }>;
    uncertainties: string[];
    /** Evidence ids whose cues are not reliable enough to act on unconfirmed. */
    low_confidence_evidence?: string[];
  }>;
  actions: Array<{
    id: string;
    related_issue_ids: string[];
    action: AuditAction;
    detail: string;
    target_time_ranges: AuditTimeRange[];
    reuse_time_ranges: AuditTimeRange[];
    insertion_position: string | null;
    requires_reshoot: boolean;
    acceptance_criteria: string;
  }>;
};

export type AuditReport = {
  schema_version: "videoguard_audit_report_v1";
  overall_verdict: AuditVerdict;
  overall_score: number;
  executive_summary: string;
  dimension_scores: {
    audit_coverage: AuditDimension;
    evidence_traceability: AuditDimension;
    safety_risk_control: AuditDimension;
    context_completeness: AuditDimension;
    audiovisual_readability: AuditDimension;
  };
  revision_plan: AuditRevisionPlan[];
  overall_direction: string;
  limitations: string[];
};

export type TimelineFact = {
  fact_id: string;
  start_ms: number;
  end_ms: number;
  summary_zh: string;
  verbatim_redacted: string;
  confidence: string;
};

export type TimelineShot = {
  shot_id: string;
  start_ms: number;
  end_ms: number;
  scene_summary: string;
  visual_facts?: TimelineFact[];
  speech_transcript?: TimelineFact[];
  subtitle_text?: TimelineFact[];
  screen_text?: TimelineFact[];
  audio_observations?: TimelineFact[];
};

export type ReviewResult = {
  coverage: Coverage;
  coverage_notes?: string;
  observations: Observation[];
  findings: Finding[];
  event_findings?: EventFinding[];
  audit_report?: AuditReport | null;
  observation_detail?: {
    video_summary?: { summary_zh?: string };
    timeline?: { shots?: TimelineShot[] };
  };
  meta?: { policy_count?: number; demo_case?: string; demo_title?: string };
};

export type ReviewRecord = {
  id: string;
  video_name: string;
  mode: "LIVE" | "DEMO";
  status: "DONE" | "ERROR";
  result: ReviewResult;
};

export type TabId = "brief" | "shots" | "audit" | "summary";
export type ViewMode = "structured" | "html";

export type DemoCase = { id: string; title: string; description: string };

export type RequestStatus =
  | { kind: "idle" }
  | { kind: "working"; message: string }
  | { kind: "error"; message: string; reviewId?: string }
  | { kind: "done"; message: string };
