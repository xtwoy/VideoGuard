import type {
  AuditAction,
  AuditReport,
  AuditStatus,
  AuditVerdict,
  Coverage,
  Disposition,
  Finding,
  Judgement,
  TimelineShot,
} from "./types";

export const POLICY_NAMES: Record<string, string> = {
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

export const JUDGEMENT_LABELS: Record<Judgement, string> = {
  SUPPORTED: "疑似风险",
  NOT_SUPPORTED: "暂无支持证据",
  INSUFFICIENT: "证据不足",
  CONFLICTED: "语境冲突",
  UNKNOWN: "无法判断",
};

export const DISPOSITION_LABELS: Record<Disposition, string> = {
  FLAG: "标注关注",
  NONE: "暂无动作",
  REVIEW: "人工复核",
  VERIFY_EXTERNAL: "外部核验",
  RECHECK: "补充观察",
  RETRY: "需要重试",
};

export const AUDIT_STATUS_LABELS: Record<AuditStatus | AuditVerdict, string> = {
  PASS: "通过",
  WARNING: "注意",
  FAIL: "未通过",
  MANUAL_REVIEW: "人工复核",
  NOT_APPLICABLE: "不适用",
  PUBLISHABLE: "可进入人工发布复核",
  NEEDS_REVISION: "需修改后复核",
  BLOCKED: "存在阻断项",
};

export const DIMENSION_LABELS: Record<keyof AuditReport["dimension_scores"], string> = {
  audit_coverage: "审核覆盖",
  evidence_traceability: "证据可追溯性",
  safety_risk_control: "风险控制",
  context_completeness: "语境完整性",
  material_completeness: "素材完整性",
  narrative_structure: "内容结构",
  hook_clarity: "开头信息建立",
  subject_presentation: "主体展示",
  audiovisual_readability: "音视频可读性",
};

export const ACTION_LABELS: Record<AuditAction, string> = {
  MASK: "遮挡",
  REMOVE: "移除",
  TRIM: "缩短",
  REORDER: "调序",
  REPLACE: "替换",
  ADD_CONTEXT: "补充语境",
  EDIT_TEXT: "修改文字",
  EDIT_AUDIO: "编辑音频",
  RECORD: "补录",
  ADD_MEDIA: "补充素材",
  VERIFY: "核验",
  MANUAL_REVIEW: "人工复核",
};

export const COVERAGE_LABELS: Record<Coverage, string> = {
  FULL: "完整",
  PARTIAL: "部分",
  UNKNOWN: "未知",
  REFUSED: "拒绝解析",
  ERROR: "失败",
};

export const MODALITY_LABELS: Record<string, string> = {
  visual: "画面",
  speech: "口播",
  subtitle: "字幕",
  screen_text: "屏幕文字",
  sound: "声音",
  metadata: "元数据",
};

export const REASON_LABELS: Record<string, string> = {
  RELATED_ACTION_AND_PROMOTION: "危险动作与鼓励或挑战内容指向同一事件。",
  CONFLICTING_STANCE: "同一事件同时存在鼓励与警示信息，需要人工核对具体语境。",
  MISSING_SEMANTIC_RELATION: "观察到相关线索，但无法确认它们是否指向同一事件。",
  UNLOCATED_PROMOTION: "观察到可能的鼓励内容，但缺少可靠时间位置。",
  RELATION_CHECK_UNAVAILABLE: "关键语义关系尚未完成自动核验，需要人工复核。",
  RELATION_DISPUTES_BASELINE: "自动分析对原有支持关系存在分歧，需要人工复核。",
  RELATION_NOT_CONFIRMED: "未能确认危险动作与相关表述存在明确关联。",
  RELATION_UNRELATED_CONFIRMED: "语义核验确认相关表述指向另一事件，不构成危险行为诱导。",
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

/** Colour is reserved for judgement. `tone` is the only place colour is decided. */
export type Tone = "flag" | "review" | "clear" | "unknown";

export function toneForDisposition(disposition: Disposition): Tone {
  if (disposition === "FLAG") return "flag";
  if (disposition === "NONE") return "clear";
  return "review";
}

export function toneForJudgement(judgement: Judgement): Tone {
  if (judgement === "SUPPORTED") return "flag";
  if (judgement === "NOT_SUPPORTED") return "clear";
  if (judgement === "UNKNOWN") return "unknown";
  return "review";
}

export function toneForStatus(status: AuditStatus | AuditVerdict): Tone {
  if (status === "PASS" || status === "PUBLISHABLE") return "clear";
  if (status === "FAIL" || status === "BLOCKED") return "flag";
  if (status === "NOT_APPLICABLE") return "unknown";
  return "review";
}

export function toneForCoverage(coverage: Coverage): Tone {
  if (coverage === "FULL") return "clear";
  if (coverage === "PARTIAL" || coverage === "UNKNOWN") return "review";
  return "flag";
}

/** Title of a finding, falling back to the policy table then a neutral label. */
export function policyName(finding: Pick<Finding, "policy_id" | "name">): string {
  return finding.name || POLICY_NAMES[finding.policy_id] || "内容安全问题";
}

export function reasonText(code?: string): string {
  return (code && REASON_LABELS[code]) || "请结合对应证据和原视频进行人工核对。";
}

/** `mm:ss`, or an explicit "未定位" so a missing position never renders as 00:00. */
export function formatTime(milliseconds: number | null | undefined): string {
  if (milliseconds === null || milliseconds === undefined) return "未定位";
  if (!Number.isInteger(milliseconds) || milliseconds < 0) return "未定位";
  const seconds = Math.floor(milliseconds / 1000);
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

export function factCount(shot: TimelineShot): number {
  return [shot.visual_facts, shot.speech_transcript, shot.subtitle_text, shot.screen_text, shot.audio_observations].reduce(
    (total, facts) => total + (facts?.length ?? 0),
    0,
  );
}

export const TAB_LABELS = {
  brief: "结论概览",
  shots: "分镜结果",
  audit: "问题与证据",
  summary: "整改与总结",
} as const;
