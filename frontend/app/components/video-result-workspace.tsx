"use client";

import {
  ExternalLink,
  FileText,
  Film,
  PlayCircle,
  ShieldAlert,
} from "lucide-react";
import { useMemo, useState, type RefObject } from "react";

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
};

export type EventFinding = {
  event_id: string;
  policy_id: string;
  evidence_ids: string[];
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
    material_completeness: AuditDimension;
    narrative_structure: AuditDimension;
    hook_clarity: AuditDimension;
    subject_presentation: AuditDimension;
    audiovisual_readability: AuditDimension;
  };
  revision_plan: Array<{
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
    }>;
    actions: Array<{
      id: string;
      related_issue_ids: string[];
      action: "MASK" | "REMOVE" | "TRIM" | "REORDER" | "REPLACE" | "ADD_CONTEXT" | "EDIT_TEXT" | "EDIT_AUDIO" | "RECORD" | "ADD_MEDIA" | "VERIFY" | "MANUAL_REVIEW";
      detail: string;
      target_time_ranges: AuditTimeRange[];
      reuse_time_ranges: AuditTimeRange[];
      insertion_position: string | null;
      requires_reshoot: boolean;
      acceptance_criteria: string;
    }>;
  }>;
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
  meta?: { policy_count?: number };
};

type TabId = "brief" | "shots" | "audit" | "summary";
type ViewMode = "structured" | "html";

const POLICY_NAMES: Record<string, string> = {
  R_DANGER_PROMOTION: "危险行为诱导",
  R_VIOLENCE: "暴力或危险行为画面",
  R_PRIVACY_EXPOSURE: "个人隐私暴露",
  R_MARKETING_CLAIM: "营销及资质声称",
  R_SELF_HARM: "自伤风险",
  R_SEXUAL_CONTENT: "性内容风险",
  R_HATE_HARASSMENT: "仇恨与骚扰",
  R_FRAUD_SCAM: "诈骗与高风险诱导",
  R_CONTROLLED_GOODS: "受控商品风险",
  R_MINORS_PROTECTION: "未成年人保护",
};

const LABELS: Record<Judgement | Disposition, string> = {
  SUPPORTED: "疑似风险", NOT_SUPPORTED: "暂无证据", INSUFFICIENT: "证据不足",
  CONFLICTED: "语境冲突", UNKNOWN: "无法判断", FLAG: "标注关注",
  NONE: "暂无动作", REVIEW: "人工复核", VERIFY_EXTERNAL: "外部核验",
  RECHECK: "补充观察", RETRY: "需要重试",
};

const AUDIT_STATUS_LABELS: Record<AuditStatus | AuditVerdict, string> = {
  PASS: "通过", WARNING: "注意", FAIL: "未通过", MANUAL_REVIEW: "人工复核", NOT_APPLICABLE: "不适用",
  PUBLISHABLE: "可进入人工发布复核", NEEDS_REVISION: "需修改后复核", BLOCKED: "存在阻断项",
};

const AUDIT_DIMENSION_LABELS: Record<keyof AuditReport["dimension_scores"], string> = {
  audit_coverage: "审核覆盖", evidence_traceability: "证据可追溯性", safety_risk_control: "风险控制",
  context_completeness: "语境完整性", material_completeness: "素材完整性", narrative_structure: "内容结构",
  hook_clarity: "开头信息建立", subject_presentation: "主体展示", audiovisual_readability: "音视频可读性",
};

const AUDIT_ACTION_LABELS: Record<AuditReport["revision_plan"][number]["actions"][number]["action"], string> = {
  MASK: "遮挡", REMOVE: "移除", TRIM: "缩短", REORDER: "调序", REPLACE: "替换", ADD_CONTEXT: "补充语境",
  EDIT_TEXT: "修改文字", EDIT_AUDIO: "编辑音频", RECORD: "补录", ADD_MEDIA: "补充素材", VERIFY: "核验", MANUAL_REVIEW: "人工复核",
};

const REASON_LABELS: Record<string, string> = {
  RELATED_ACTION_AND_PROMOTION: "危险动作与鼓励或挑战内容指向同一事件。",
  CONFLICTING_STANCE: "同一事件同时存在鼓励与警示信息，需要人工核对具体语境。",
  MISSING_SEMANTIC_RELATION: "观察到相关线索，但无法确认它们是否指向同一事件。",
  UNLOCATED_PROMOTION: "观察到可能的鼓励内容，但缺少可靠时间位置。",
  RELATION_CHECK_UNAVAILABLE: "关键语义关系尚未完成自动核验，需要人工复核。",
  RELATION_DISPUTES_BASELINE: "自动分析对原有支持关系存在分歧，需要人工复核。",
  RELATION_NOT_CONFIRMED: "未能确认危险动作与相关表述存在明确关联。",
  RELATION_AMBIGUITY: "相关表述的语义存在歧义，需要人工复核。",
  RELATION_REFERENT_DISAGREEMENT: "不同观察对所指事件存在分歧，需要人工复核。",
  VIOLENCE_DEPICTION: "观察到疑似暴力或危险行为画面。",
  DEPICTION_WITH_CONTEXT: "观察到相关画面，同时存在新闻、影视或教育等语境线索。",
  POTENTIAL_PII: "观察到可能包含个人隐私的信息。",
  CREDENTIAL_AUTHENTICITY_UNKNOWN: "观察到资质声称，真实性需要外部材料核验。",
  MARKETING_CLAIM_NEEDS_CONTEXT: "观察到营销或绝对化表述，需要结合上下文核对。",
  SELF_HARM_CUE: "观察到可能涉及自伤、自杀或相关方法传播的内容线索。",
  SEXUAL_CONTENT_CUE: "观察到可能不适宜的性内容或性暗示线索。",
  HATE_HARASSMENT_CUE: "观察到可能涉及仇恨、歧视、侮辱或定向骚扰的内容线索。",
  FRAUD_SCAM_CUE: "观察到可能涉及诈骗、冒充、虚假获利或高风险交易诱导的内容线索。",
  CONTROLLED_GOODS_CUE: "观察到可能涉及受控商品展示、交易或引导的内容线索。",
  MINOR_PROTECTION_CUE: "观察到可能涉及未成年人不适宜、剥削或人身安全风险的内容线索。",
  UNVERIFIED_OR_UNLOCATED: "存在相关线索，但证据未能可靠定位。",
  UNLOCATED_PII: "存在隐私暴露线索，但证据未能可靠定位。",
  UNLOCATED_MARKETING_CLAIM: "存在营销或资质声称线索，但证据未能可靠定位。",
  INCOMPLETE_OBSERVATION: "视频观察不完整，需要补充核查。",
  MODEL_UNAVAILABLE: "自动审核未能完成，需要重新执行。",
};

function formatTime(milliseconds: number | null): string {
  if (!Number.isInteger(milliseconds) || milliseconds === null || milliseconds < 0) return "未定位";
  const seconds = Math.floor(milliseconds / 1000);
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

function reasonText(code?: string): string {
  return (code && REASON_LABELS[code]) || "请结合对应证据和原视频进行人工核对。";
}

function policyName(finding: Pick<Finding, "policy_id" | "name">): string {
  return finding.name || POLICY_NAMES[finding.policy_id] || "内容安全问题";
}

function seekVideo(videoRef: RefObject<HTMLVideoElement | null>, startMs: number | null): void {
  if (!videoRef.current || !Number.isInteger(startMs)) return;
  videoRef.current.currentTime = (startMs ?? 0) / 1000;
  void videoRef.current.play().catch(() => undefined);
}

export function VideoResultWorkspace({
  result,
  videoRef,
  videoSrc,
  reportUrl,
  isDemo = false,
}: {
  result: ReviewResult | null;
  videoRef: RefObject<HTMLVideoElement | null>;
  videoSrc?: string | null;
  reportUrl?: string | null;
  isDemo?: boolean;
}) {
  const [viewMode, setViewMode] = useState<ViewMode>("structured");
  const [activeTab, setActiveTab] = useState<TabId>("audit");
  const [activeShot, setActiveShot] = useState<string | null>(null);
  const shots = result?.observation_detail?.timeline?.shots ?? [];
  const activeFindings = useMemo(
    () => (result?.findings ?? []).filter((finding) => finding.disposition !== "NONE"),
    [result],
  );

  function seek(startMs: number | null): void {
    if (isDemo || !videoSrc) return;
    seekVideo(videoRef, startMs);
  }

  function handleShotClick(shot: TimelineShot): void {
    setActiveShot(shot.shot_id);
    seek(shot.start_ms);
  }

  return (
    <section className="min-h-170 rounded-lg border border-[#e4e7ec] bg-white p-5.5 shadow-sm max-[940px]:min-h-0 max-[620px]:p-4">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[#e4e7ec] pb-4">
        <div>
          <p className="mb-1.5 text-[10px] font-extrabold tracking-[0.12em] text-indigo-600">AUDIT REPORT</p>
          <h2 className="text-[17px] font-bold">审核报告</h2>
        </div>
        <div className="inline-flex rounded-md border border-[#d0d5dd] bg-white p-0.5 text-xs font-bold">
          <button type="button" onClick={() => setViewMode("structured")} className={`rounded px-2.5 py-1.5 ${viewMode === "structured" ? "bg-indigo-50 text-indigo-700" : "text-[#667085] hover:bg-[#f2f4f7]"}`}>结构化报告</button>
          <button type="button" disabled={!reportUrl} onClick={() => setViewMode("html")} className={`rounded px-2.5 py-1.5 ${viewMode === "html" ? "bg-indigo-50 text-indigo-700" : "text-[#667085] hover:bg-[#f2f4f7]"} disabled:cursor-not-allowed disabled:opacity-45`}>HTML 报告</button>
        </div>
      </div>

      {!result && <ResultEmptyState />}
      {result && viewMode === "html" && reportUrl && <HtmlReport reportUrl={reportUrl} />}
      {result && viewMode === "structured" && (
        <div className="mt-5 grid min-h-0 grid-cols-[minmax(220px,.78fr)_minmax(0,1.22fr)] gap-5 max-[940px]:grid-cols-1">
          <VideoPanel videoRef={videoRef} videoSrc={videoSrc} isDemo={isDemo} />
          <div className="min-w-0">
            <div role="tablist" aria-label="审核报告内容" className="flex overflow-x-auto border-b border-[#e4e7ec]">
              {(["brief", "shots", "audit", "summary"] as TabId[]).map((tab) => (
                <button key={tab} role="tab" type="button" aria-selected={activeTab === tab} onClick={() => setActiveTab(tab)} className={`shrink-0 border-b-2 px-3 py-2 text-xs font-bold ${activeTab === tab ? "border-indigo-600 text-indigo-700" : "border-transparent text-[#667085] hover:text-[#344054]"}`}>
                  {{ brief: "Brief", shots: "分镜结果", audit: "审核详细", summary: "审核总结" }[tab]}
                </button>
              ))}
            </div>
            <div className="pt-4">
              {activeTab === "brief" && <BriefTab result={result} />}
              {activeTab === "shots" && <ShotsTab shots={shots} activeShot={activeShot} onShotClick={handleShotClick} />}
              {activeTab === "audit" && <AuditTab findings={activeFindings} events={result.event_findings ?? []} observations={result.observations} onSeek={seek} isSeekDisabled={isDemo || !videoSrc} />}
              {activeTab === "summary" && <SummaryTab report={result.audit_report ?? null} onSeek={seek} isSeekDisabled={isDemo || !videoSrc} />}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

function ResultEmptyState() {
  return <div className="grid min-h-115 place-items-center content-center px-9 text-center max-[940px]:min-h-80"><span className="grid size-13 place-items-center rounded-full border border-indigo-200 bg-indigo-50 text-indigo-600"><ShieldAlert size={24} /></span><h3 className="mt-4 text-[17px] font-bold">等待审核结果</h3><p className="mt-2 max-w-87.5 text-[13px] leading-6 text-[#667085]">提交视频后，这里会显示可回溯的分镜、审核问题与整改建议。</p></div>;
}

function HtmlReport({ reportUrl }: { reportUrl: string }) {
  return <div className="mt-5 flex min-h-130 flex-col gap-3"><div className="flex justify-end"><a href={reportUrl} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1.5 rounded-md border border-[#d0d5dd] px-3 py-2 text-xs font-bold text-[#344054] hover:bg-[#f2f4f7]"><ExternalLink size={14} />新标签页打开</a></div><iframe src={reportUrl} title="审核报告" className="min-h-120 flex-1 rounded-lg border border-[#d0d5dd]" /></div>;
}

function VideoPanel({ videoRef, videoSrc, isDemo }: { videoRef: RefObject<HTMLVideoElement | null>; videoSrc?: string | null; isDemo: boolean }) {
  return <div className="sticky top-5 h-fit overflow-hidden rounded-lg border border-[#d0d5dd] bg-[#111827] max-[940px]:static">{videoSrc ? <video ref={videoRef} className="block max-h-120 w-full" controls playsInline src={videoSrc} /> : <div className="grid min-h-65 place-items-center px-5 text-center text-[#98a2b3]"><Film size={24} /><p className="mt-2 text-xs leading-5">{isDemo ? "合成报告未关联原视频" : "当前审核记录没有可播放的视频"}</p></div>}</div>;
}

function BriefTab({ result }: { result: ReviewResult }) {
  const summary = result.observation_detail?.video_summary?.summary_zh;
  return <div className="grid min-h-70 place-items-center rounded-lg border border-dashed border-[#d0d5dd] bg-[#fcfcfd] px-6 text-center"><div><FileText className="mx-auto text-[#98a2b3]" size={28} /><h3 className="mt-3 text-sm font-bold">未提供 Brief 数据</h3><p className="mt-2 max-w-87.5 text-xs leading-5 text-[#667085]">当前入口只接收视频审核结果，因此不会伪造 Brief。{summary ? ` 视频事实摘要：${summary}` : ""}</p></div></div>;
}

function ShotsTab({ shots, activeShot, onShotClick }: { shots: TimelineShot[]; activeShot: string | null; onShotClick: (shot: TimelineShot) => void }) {
  if (!shots.length) return <EmptyContent text="当前没有可展示的分镜结果。" />;
  return <div className="grid gap-2">{shots.map((shot) => <button key={shot.shot_id} type="button" onClick={() => onShotClick(shot)} className={`w-full rounded-md border p-3 text-left transition ${activeShot === shot.shot_id ? "border-indigo-400 bg-indigo-50" : "border-[#e4e7ec] bg-white hover:border-indigo-200"}`}><div className="flex items-center justify-between gap-2"><b className="text-xs text-indigo-700">{shot.shot_id} · {formatTime(shot.start_ms)}—{formatTime(shot.end_ms)}</b><PlayCircle size={15} className="text-indigo-600" /></div><p className="mt-2 text-xs leading-5 text-[#344054]">{shot.scene_summary || "未提供场景摘要"}</p><p className="mt-1 text-[11px] text-[#667085]">{factCount(shot)} 条已记录事实</p></button>)}</div>;
}

function factCount(shot: TimelineShot): number {
  return [shot.visual_facts, shot.speech_transcript, shot.subtitle_text, shot.screen_text, shot.audio_observations].reduce((total, facts) => total + (facts?.length ?? 0), 0);
}

function AuditTab({ findings, events, observations, onSeek, isSeekDisabled }: { findings: Finding[]; events: EventFinding[]; observations: Observation[]; onSeek: (startMs: number | null) => void; isSeekDisabled: boolean }) {
  const byId = new Map(observations.map((observation) => [observation.id, observation]));
  return <div className="space-y-5"><section><TabHeading title="发现的问题" hint="需人工判断" />{findings.length ? <div className="grid gap-2">{findings.map((finding) => <article key={finding.policy_id} className="rounded-md border border-[#e4e7ec] bg-white p-3"><div className="flex items-start justify-between gap-3"><b className="text-[13px]">{policyName(finding)}</b><span className={`rounded-full px-2 py-1 text-[10px] font-bold ${finding.disposition === "FLAG" ? "bg-red-50 text-red-700" : "bg-amber-50 text-amber-700"}`}>{LABELS[finding.judgement]} · {LABELS[finding.disposition]}</span></div><p className="mt-2 text-xs leading-5 text-[#667085]">{reasonText(finding.reason_code)}</p><div className="mt-2 flex flex-wrap gap-1.5">{[...finding.supporting_ids, ...finding.counter_ids].map((id) => <EvidencePill key={id} observation={byId.get(id)} onSeek={onSeek} disabled={isSeekDisabled} />)}</div></article>)}</div> : <EmptyContent text="当前没有需要进一步处理的审核项。" />}</section><section><TabHeading title="事件级审计" hint="独立事件独立保留" />{events.length ? <div className="grid gap-2">{events.map((event) => <article key={event.event_id} className="border-l-3 border-indigo-300 bg-[#fcfcfd] px-3 py-2.5 text-xs"><b>{POLICY_NAMES[event.policy_id] ?? "事件审计"}</b><p className="mt-1 text-[#667085]">{LABELS[event.judgement]} · {LABELS[event.disposition]} · 关联证据：{event.evidence_ids.join("、") || "无"}</p></article>)}</div> : <EmptyContent text="当前没有可单独审计的事件记录。" />}</section><section><TabHeading title="全部证据" hint="点击可回看原片段" />{observations.length ? <div className="grid gap-2">{observations.map((observation) => <EvidenceRow key={observation.id} observation={observation} onSeek={onSeek} disabled={isSeekDisabled} />)}</div> : <EmptyContent text="当前没有可回溯证据。" />}</section></div>;
}

function SummaryTab({ report, onSeek, isSeekDisabled }: { report: AuditReport | null; onSeek: (startMs: number | null) => void; isSeekDisabled: boolean }) {
  if (!report) return <EmptyContent text="当前没有可展示的结构化审核报告。" />;
  const dimensions = Object.entries(report.dimension_scores) as Array<[keyof AuditReport["dimension_scores"], AuditDimension]>;
  return <div className="space-y-4"><article className="rounded-md border border-[#e4e7ec] bg-[#fcfcfd] p-3"><div className="flex flex-wrap items-start justify-between gap-3"><div><b className="text-sm">审核结论</b><p className="mt-1 text-xs leading-5 text-[#475467]">{report.executive_summary}</p></div><span className={`rounded-full px-2 py-1 text-[11px] font-bold ${auditStatusClass(report.overall_verdict)}`}>{AUDIT_STATUS_LABELS[report.overall_verdict]} · {report.overall_score} 分</span></div><p className="mt-3 border-l-3 border-indigo-300 pl-2.5 text-xs leading-5 text-[#475467]">处理方向：{report.overall_direction}</p></article>
    <section><TabHeading title="维度评分" hint="依据可回溯证据" /><div className="grid grid-cols-2 gap-2 max-[620px]:grid-cols-1">{dimensions.map(([key, item]) => <article key={key} className="rounded-md border border-[#e4e7ec] bg-white p-2.5"><div className="flex items-start justify-between gap-2"><b className="text-xs">{AUDIT_DIMENSION_LABELS[key]}</b><span className={`rounded-full px-1.5 py-0.5 text-[10px] font-bold ${auditStatusClass(item.status)}`}>{item.score} · {AUDIT_STATUS_LABELS[item.status]}</span></div><p className="mt-1.5 text-[11px] leading-5 text-[#667085]">{item.summary}</p>{item.items.length > 0 && <div className="mt-2 grid gap-1.5 border-t border-[#eaecf0] pt-2">{item.items.map((detail) => <div key={detail.key} className="text-[11px]"><div className="flex items-center justify-between gap-2"><span className="font-semibold text-[#344054]">{detail.label}</span><span className={auditStatusClass(detail.status)}>{detail.score} · {AUDIT_STATUS_LABELS[detail.status]}</span></div><p className="mt-0.5 leading-4 text-[#667085]">{detail.summary}</p><TimeRanges ranges={detail.time_ranges} onSeek={onSeek} disabled={isSeekDisabled} /></div>)}</div>}{item.limitations.map((limitation, index) => <p key={index} className="mt-1 text-[10px] leading-4 text-amber-700">限制：{limitation}</p>)}</article>)}</div></section>
    <section><TabHeading title="问题定位与整改" hint={`${report.revision_plan.length} 个分组`} />{report.revision_plan.length ? <div className="grid gap-3">{report.revision_plan.map((plan) => <article key={plan.id} className="rounded-md border border-[#e4e7ec] bg-white p-3"><div className="flex flex-wrap items-start justify-between gap-2"><div><b className="text-[13px]">{plan.section || "审核项"}</b><p className="mt-1 text-[11px] text-[#98a2b3]">{plan.id} · {plan.scope === "EVENT" ? "事件级整改" : "全局整改"}</p></div><TimeRanges ranges={plan.video.time_ranges} onSeek={onSeek} disabled={isSeekDisabled} /></div><p className="mt-2 text-xs leading-5 text-[#475467]">{plan.video.summary}</p><div className="mt-3 grid gap-2">{plan.issues.map((issue) => <section key={issue.id} className="border-l-3 border-indigo-300 bg-[#f8faff] px-2.5 py-2"><div className="flex flex-wrap items-center gap-1.5"><span className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${issue.priority === "P0" ? "bg-red-50 text-red-700" : issue.priority === "P1" ? "bg-amber-50 text-amber-700" : "bg-blue-50 text-blue-700"}`}>{issue.priority}</span><b className="text-xs">{issue.title}</b></div><p className="mt-1 text-xs leading-5 text-[#475467]">{issue.description}</p><div className="mt-1.5"><TimeRanges ranges={issue.time_ranges} onSeek={onSeek} disabled={isSeekDisabled} /></div><ul className="mt-2 grid gap-1 text-[11px] leading-4 text-[#667085]">{issue.supporting_evidence.map((evidence) => <li key={evidence.ref}><b className="text-indigo-700">{evidence.ref}</b> · {evidence.content}<TimeRanges ranges={evidence.time_ranges} onSeek={onSeek} disabled={isSeekDisabled} />{evidence.limitations.map((limitation, index) => <span key={index} className="block text-amber-700">限制：{limitation}</span>)}</li>)}</ul>{issue.uncertainties.map((uncertainty, index) => <p key={index} className="mt-1 text-[11px] text-amber-700">限制：{uncertainty}</p>)}</section>)}</div><div className="mt-3 grid gap-2">{plan.actions.map((action) => <section key={action.id} className="rounded border border-emerald-200 bg-emerald-50 p-2.5"><div className="flex flex-wrap items-center justify-between gap-2"><b className="text-xs text-emerald-800">{AUDIT_ACTION_LABELS[action.action]}</b><TimeRanges ranges={action.target_time_ranges} onSeek={onSeek} disabled={isSeekDisabled} /></div><p className="mt-1 text-xs leading-5 text-[#344054]">{action.detail}</p><p className="mt-1 text-[11px] leading-4 text-emerald-800">验收：{action.acceptance_criteria}</p></section>)}</div></article>)}</div> : <EmptyContent text="当前没有需要执行的整改分组。" />}</section>
    {report.limitations.length > 0 && <p className="rounded-md border border-dashed border-[#d0d5dd] bg-[#fcfcfd] px-3 py-2 text-[11px] leading-5 text-[#667085]">限制：{report.limitations.join("；")}</p>}</div>;
}

function auditStatusClass(status: AuditStatus | AuditVerdict): string {
  if (status === "PASS" || status === "PUBLISHABLE") return "bg-emerald-50 text-emerald-700";
  if (status === "FAIL" || status === "BLOCKED") return "bg-red-50 text-red-700";
  return "bg-amber-50 text-amber-700";
}

function TimeRanges({ ranges, onSeek, disabled }: { ranges: AuditTimeRange[]; onSeek: (startMs: number | null) => void; disabled: boolean }) {
  if (!ranges.length) return <span className="text-[11px] text-[#98a2b3]">未精确定位</span>;
  return <span className="flex flex-wrap gap-1">{ranges.map((range, index) => <button key={`${range.start_ms}-${range.end_ms}-${index}`} type="button" disabled={disabled} onClick={() => onSeek(range.start_ms)} className="rounded bg-indigo-50 px-1.5 py-0.5 text-[10px] font-bold text-indigo-700 hover:bg-indigo-100 disabled:cursor-not-allowed disabled:opacity-45">{formatTime(range.start_ms)}—{formatTime(range.end_ms)}</button>)}</span>;
}

function EvidencePill({ observation, onSeek, disabled }: { observation?: Observation; onSeek: (startMs: number | null) => void; disabled: boolean }) {
  if (!observation) return null;
  return <button type="button" disabled={disabled} onClick={() => onSeek(observation.start_ms)} className="rounded bg-indigo-50 px-1.5 py-0.5 text-[11px] font-bold text-indigo-700 hover:bg-indigo-100 disabled:cursor-not-allowed disabled:opacity-45">{observation.id} · {formatTime(observation.start_ms)}</button>;
}

function EvidenceRow({ observation, onSeek, disabled }: { observation: Observation; onSeek: (startMs: number | null) => void; disabled: boolean }) {
  return <button type="button" disabled={disabled} onClick={() => onSeek(observation.start_ms)} className="flex w-full items-start justify-between gap-3 rounded-md border border-[#e4e7ec] bg-white p-3 text-left hover:border-indigo-200 disabled:cursor-not-allowed disabled:opacity-60"><span><b className="text-[11px] text-indigo-700">{observation.id} · {formatTime(observation.start_ms)}—{formatTime(observation.end_ms)}</b><span className="mt-1 block text-xs leading-5 text-[#344054]">{observation.description_redacted || observation.text_redacted || "未提供描述"}</span><small className="mt-1 block text-[11px] text-[#98a2b3]">{observation.modality} · 模型观察，未经人工核实</small></span><PlayCircle className="mt-1 shrink-0 text-indigo-600" size={16} /></button>;
}

function TabHeading({ title, hint }: { title: string; hint: string }) { return <div className="mb-2.5 flex items-center justify-between gap-3"><h3 className="text-sm font-bold">{title}</h3><span className="text-[11px] text-[#98a2b3]">{hint}</span></div>; }
function EmptyContent({ text }: { text: string }) { return <p className="rounded-md border border-dashed border-[#d0d5dd] bg-[#fcfcfd] px-3 py-5 text-center text-xs text-[#667085]">{text}</p>; }
