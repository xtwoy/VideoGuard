"use client";

import {
  ArrowRight,
  AudioLines,
  Captions,
  Check,
  ChevronDown,
  ChevronRight,
  CircleAlert,
  Eye,
  FileCheck2,
  FileText,
  Film,
  GitBranch,
  Link2,
  ListChecks,
  MessageSquare,
  ScanLine,
  ShieldAlert,
  ShieldCheck,
  Video,
} from "lucide-react";
import {
  ACTION_LABELS,
  AUDIT_STATUS_LABELS,
  COVERAGE_LABELS,
  DIMENSION_LABELS,
  dimensionLabel,
  DISPOSITION_LABELS,
  JUDGEMENT_LABELS,
  MODALITY_LABELS,
  POLICY_NAMES,
  factCount,
  formatTime,
  policyName,
  reasonText,
  toneForCoverage,
  toneForDisposition,
  toneForJudgement,
  toneForStatus,
} from "../lib/labels";
import type {
  AuditDimension,
  AuditReport,
  AuditRevisionPlan,
  EventFinding,
  Finding,
  Observation,
  ReviewResult,
  TabId,
  TimelineShot,
} from "../lib/types";
import { CaseSceneImage } from "./case-scene-image";
import {
  EmptyNote,
  LimitNote,
  Pill,
  SectionHeading,
  Tag,
  TimeRangeList,
  TimeRef,
} from "./ui";

type Seek = { onSeek: (startMs: number | null) => void; seekDisabled: boolean };

function groupFindings(findings: Finding[]): Finding[][] {
  const groups = new Map<string, Finding[]>();
  for (const finding of findings) {
    const key = `${finding.judgement}|${finding.disposition}|${finding.reason_code}`;
    const previous = groups.get(key);
    if (previous) previous.push(finding);
    else groups.set(key, [finding]);
  }
  return [...groups.values()];
}
function groupTitle(group: Finding[]): string {
  return group.length === 1 ? policyName(group[0]) : `${group.length} 类策略`;
}

function Verdict({ report }: { report: AuditReport | null }) {
  const tone = report ? toneForStatus(report.overall_verdict) : "unknown";
  const Icon =
    tone === "flag"
      ? ShieldAlert
      : tone === "clear"
        ? ShieldCheck
        : CircleAlert;
  return (
    <section className="vg-verdict" data-tone={tone} aria-label="审核结论">
      <div className="vg-verdict-main">
        <span className="vg-verdict-symbol">
          <Icon size={27} strokeWidth={1.6} aria-hidden />
        </span>
        <div>
          <span className="vg-verdict-caption">审核结论</span>
          <h3>
            {report
              ? AUDIT_STATUS_LABELS[report.overall_verdict]
              : "已生成结构化审核结果"}
          </h3>
        </div>
      </div>
      {report ? (
        <div className="vg-report-score">
          <span>综合评分</span>
          <div>
            <strong>{report.overall_score}</strong>
            <span>/ 100</span>
          </div>
          <small>取已评估维度最低分</small>
        </div>
      ) : null}
      <p className="vg-verdict-summary">
        {report?.executive_summary ?? "请结合检查状态与具体证据进行人工确认。"}
      </p>
    </section>
  );
}

export function BriefTab({
  result,
  onNavigate,
}: {
  result: ReviewResult;
  onNavigate?: (tab: TabId) => void;
}) {
  const report = result.audit_report ?? null;
  const active = result.findings.filter((item) => item.disposition !== "NONE");
  const summary = result.observation_detail?.video_summary?.summary_zh;
  return (
    <div className="vg-tab-content">
      <Verdict report={report} />
      <dl className="vg-review-facts" aria-label="本次审核概况">
        <div>
          <dt>
            <ListChecks size={15} aria-hidden />
            待处理项
          </dt>
          <dd>
            {active.length}
            <span>项</span>
          </dd>
        </div>
        <div>
          <dt>
            <Link2 size={15} aria-hidden />
            证据线索
          </dt>
          <dd>
            {result.observations.length}
            <span>条</span>
          </dd>
        </div>
        <div>
          <dt>
            <ScanLine size={15} aria-hidden />
            检查策略
          </dt>
          <dd>
            {result.findings.length}
            <span>类</span>
          </dd>
        </div>
        <div>
          <dt>
            <Eye size={15} aria-hidden />
            观察覆盖
          </dt>
          <dd
            className="vg-coverage-value"
            data-tone={toneForCoverage(result.coverage)}
          >
            {COVERAGE_LABELS[result.coverage]}
          </dd>
        </div>
      </dl>
      {result.coverage_notes ? (
        <LimitNote>{result.coverage_notes}</LimitNote>
      ) : null}
      {report?.overall_direction ? (
        <section className="vg-direction">
          <span>
            <FileCheck2 size={20} aria-hidden />
          </span>
          <div>
            <h4>建议处理方向</h4>
            <p>{report.overall_direction}</p>
          </div>
        </section>
      ) : null}
      <section>
        <SectionHeading
          title="需要关注的问题"
          hint={`${active.length} 项待人工确认`}
        />
        {active.length ? (
          <div className="vg-finding-list">
            {groupFindings(active).map((group) => {
              const first = group[0];
              const refs = [
                ...new Set(
                  group.flatMap((item) => [
                    ...item.supporting_ids,
                    ...item.counter_ids,
                  ]),
                ),
              ];
              return (
                <article
                  className="vg-finding-brief"
                  key={`${first.policy_id}-${first.reason_code}`}
                  data-tone={toneForDisposition(first.disposition)}
                >
                  <span className="vg-finding-icon">
                    <ShieldAlert size={20} aria-hidden />
                  </span>
                  <div className="vg-finding-copy">
                    <div>
                      <h4>{groupTitle(group)}</h4>
                      <Pill tone={toneForDisposition(first.disposition)}>
                        {DISPOSITION_LABELS[first.disposition]}
                      </Pill>
                    </div>
                    <p>{reasonText(first.reason_code)}</p>
                    {group.length > 1 ? (
                      <div className="vg-inline-tags">
                        {group.map((item) => (
                          <Tag key={item.policy_id}>{policyName(item)}</Tag>
                        ))}
                      </div>
                    ) : null}
                    <div className="vg-finding-meta">
                      <span>
                        {refs.length
                          ? `引用线索 ${refs.join("、")}`
                          : "尚未关联具体证据"}
                      </span>
                      <Pill quiet tone={toneForJudgement(first.judgement)}>
                        {JUDGEMENT_LABELS[first.judgement]}
                      </Pill>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        ) : (
          <div className="vg-quiet-state">
            <ShieldCheck size={25} aria-hidden />
            <div>
              <h4>当前输入暂无需处理项</h4>
              <p>未发现支持证据不等于内容绝对安全，发布前仍需人工复核。</p>
            </div>
          </div>
        )}
        {onNavigate && active.length ? (
          <div className="vg-result-actions">
            <button type="button" onClick={() => onNavigate("audit")}>
              查看问题与证据
              <ArrowRight size={15} aria-hidden />
            </button>
            <button type="button" onClick={() => onNavigate("summary")}>
              查看整改建议
              <ArrowRight size={15} aria-hidden />
            </button>
          </div>
        ) : null}
      </section>
      <section className="vg-content-summary">
        <div>
          <FileText size={18} aria-hidden />
          <h4>视频内容概述</h4>
        </div>
        <p>{summary ?? "当前未提供内容概述。"}</p>
      </section>
      <details className="vg-policy-details">
        <summary>
          查看全部 {result.findings.length} 类策略的处置
          <ChevronDown size={16} aria-hidden />
        </summary>
        <div>
          {result.findings.map((finding) => (
            <div key={finding.policy_id}>
              <span>{policyName(finding)}</span>
              <Pill tone={toneForDisposition(finding.disposition)} quiet>
                {DISPOSITION_LABELS[finding.disposition]}
              </Pill>
            </div>
          ))}
        </div>
      </details>
    </div>
  );
}

const FACT_GROUPS = [
  ["visual_facts", "画面观察", Video],
  ["speech_transcript", "语音内容", AudioLines],
  ["subtitle_text", "字幕", Captions],
  ["screen_text", "屏幕文字", FileText],
  ["audio_observations", "声音观察", AudioLines],
] as const;

export function ShotsTab({
  shots,
  activeShot,
  onShotClick,
  seekDisabled,
}: {
  shots: TimelineShot[];
  activeShot: string | null;
  onShotClick: (shot: TimelineShot) => void;
  seekDisabled: boolean;
}) {
  if (!shots.length) return <EmptyNote>当前没有可展示的分镜结果。</EmptyNote>;
  return (
    <div className="vg-tab-content">
      <SectionHeading
        title="沿时间线查看视频"
        hint={`${shots.length} 个分镜 · ${seekDisabled ? "当前无原片，仅展示观察记录" : "选择分镜可定位到原片"}`}
      />
      <ol className="vg-shot-list">
        {shots.map((shot) => (
          <li
            key={shot.shot_id}
            className={activeShot === shot.shot_id ? "is-selected" : ""}
          >
            <div className="vg-shot-position">
              <span />
              <strong>{formatTime(shot.start_ms)}</strong>
            </div>
            <article className="vg-shot-card">
              <button
                type="button"
                className="vg-shot-heading"
                aria-pressed={activeShot === shot.shot_id}
                onClick={() => onShotClick(shot)}
              >
                <span>
                  <Film size={18} aria-hidden />
                  <strong>{shot.shot_id}</strong>
                  <span>{factCount(shot)} 条事实记录</span>
                </span>
                <span>
                  {formatTime(shot.start_ms)}–{formatTime(shot.end_ms)}
                  <ChevronRight size={16} aria-hidden />
                </span>
              </button>
              <p>{shot.scene_summary || "未提供场景摘要"}</p>
              <div className="vg-shot-modalities">
                {FACT_GROUPS.map(([key, label, Icon]) =>
                  shot[key]?.length ? (
                    <span key={key}>
                      <Icon size={14} aria-hidden />
                      {label} {shot[key]?.length}
                    </span>
                  ) : null,
                )}
              </div>
              {factCount(shot) > 0 ? (
                <details className="vg-shot-facts">
                  <summary>
                    查看分镜观察记录
                    <ChevronDown size={14} aria-hidden />
                  </summary>
                  {FACT_GROUPS.map(([key, label]) =>
                    shot[key]?.length ? (
                      <div key={key}>
                        <h5>{label}</h5>
                        {shot[key]?.map((fact) => (
                          <p key={fact.fact_id}>
                            <span>
                              {shot.shot_id}:{fact.fact_id}
                            </span>
                            {fact.summary_zh ||
                              fact.verbatim_redacted ||
                              "未提供描述"}
                          </p>
                        ))}
                      </div>
                    ) : null,
                  )}
                </details>
              ) : null}
            </article>
          </li>
        ))}
      </ol>
    </div>
  );
}

function EvidenceCard({
  observation,
  fallbackId,
  label,
  onSeek,
  seekDisabled,
  anchor = false,
}: {
  observation?: Observation;
  fallbackId: string;
  label?: string;
  anchor?: boolean;
} & Seek) {
  const Icon =
    observation?.modality === "speech"
      ? MessageSquare
      : observation?.modality === "screen_text"
        ? Captions
        : Video;
  return (
    <article
      className="vg-evidence-card"
      id={anchor ? `evidence-${fallbackId}` : undefined}
    >
      <header>
        <span className="vg-evidence-id">
          <Icon size={16} aria-hidden />
          {fallbackId}
        </span>
        <span>
          {label ??
            (observation
              ? (MODALITY_LABELS[observation.modality] ?? observation.modality)
              : "引用未解析")}
        </span>
      </header>
      <p>
        {observation?.description_redacted ||
          observation?.text_redacted ||
          "该引用未匹配到结构化观察，需人工核查。"}
      </p>
      {observation?.text_redacted &&
      observation.description_redacted !== observation.text_redacted ? (
        <blockquote>{observation.text_redacted}</blockquote>
      ) : null}
      <footer>
        {observation ? (
          <TimeRef
            start={observation.start_ms}
            end={observation.end_ms}
            onSeek={onSeek}
            disabled={seekDisabled}
          />
        ) : (
          <span>未定位</span>
        )}
        {observation?.event_id ? (
          <span>事件 {observation.event_id}</span>
        ) : null}
      </footer>
      {observation?.source_refs?.length ? (
        <p className="vg-evidence-source">
          来源 {observation.source_refs.join("、")}
        </p>
      ) : null}
    </article>
  );
}

export function AuditTab({
  findings,
  events,
  observations,
  seekDisabled,
  onSeek,
}: {
  findings: Finding[];
  events: EventFinding[];
  observations: Observation[];
} & Seek) {
  const byId = new Map(observations.map((item) => [item.id, item]));
  const located = observations.filter((item) =>
    Number.isInteger(item.start_ms),
  ).length;
  const referenced = new Set(
    findings.flatMap((item) => [...item.supporting_ids, ...item.counter_ids]),
  );
  const showArchive =
    observations.some((item) => !referenced.has(item.id)) ||
    findings.length === 0;
  return (
    <div className="vg-tab-content">
      <section>
        <SectionHeading
          title="问题与判断依据"
          hint={`${findings.length} 项需人工确认`}
        />
        {findings.length ? (
          <div className="vg-audit-findings">
            {groupFindings(findings).map((group) => {
              const first = group[0];
              const supporting = [
                ...new Set(group.flatMap((item) => item.supporting_ids)),
              ];
              const counter = [
                ...new Set(group.flatMap((item) => item.counter_ids)),
              ];
              const checked = group.every(
                (item) => item.counter_evidence?.checked === true,
              );
              return (
                <article
                  className="vg-audit-finding"
                  data-tone={toneForDisposition(first.disposition)}
                  key={`${first.policy_id}-${first.reason_code}`}
                >
                  <header>
                    <span className="vg-finding-icon">
                      <GitBranch size={21} aria-hidden />
                    </span>
                    <div>
                      <h4>{groupTitle(group)}</h4>
                      <span>内容判断与处置建议</span>
                    </div>
                    <div className="vg-inline-tags">
                      <Pill tone={toneForJudgement(first.judgement)}>
                        {JUDGEMENT_LABELS[first.judgement]}
                      </Pill>
                      <Pill tone={toneForDisposition(first.disposition)}>
                        {DISPOSITION_LABELS[first.disposition]}
                      </Pill>
                    </div>
                  </header>
                  <div className="vg-audit-reason">
                    <strong>判断依据</strong>
                    <p>{reasonText(first.reason_code)}</p>
                    {group.some(
                      (item) =>
                        item.needs_human_review ||
                        item.evidence_confidence === "LOW",
                    ) ? (
                      <p className="vg-confidence-note">
                        <CircleAlert size={14} aria-hidden />
                        相关线索置信度低，需人工确认后再据此处置。
                      </p>
                    ) : null}
                  </div>
                  {group.length > 1 ? (
                    <div className="vg-inline-tags vg-group-policies">
                      {group.map((item) => (
                        <Tag key={item.policy_id}>{policyName(item)}</Tag>
                      ))}
                    </div>
                  ) : null}
                  {supporting.length ? (
                    <div className="vg-linked-evidence">
                      <h5>
                        <Link2 size={15} aria-hidden />
                        支持判断所引用的线索<span>{supporting.length} 条</span>
                      </h5>
                      <div>
                        {supporting.map((id) => (
                          <EvidenceCard
                            key={id}
                            observation={byId.get(id)}
                            fallbackId={id}
                            onSeek={onSeek}
                            seekDisabled={seekDisabled}
                          />
                        ))}
                      </div>
                    </div>
                  ) : (
                    <p className="vg-no-evidence">
                      未关联具体支持线索，需结合原视频补充核查。
                    </p>
                  )}
                  {counter.length ? (
                    <div className="vg-linked-evidence vg-counter-evidence">
                      <h5>
                        <GitBranch size={15} aria-hidden />
                        反向线索<span>{counter.length} 条</span>
                      </h5>
                      <div>
                        {counter.map((id) => (
                          <EvidenceCard
                            key={id}
                            observation={byId.get(id)}
                            fallbackId={id}
                            onSeek={onSeek}
                            seekDisabled={seekDisabled}
                          />
                        ))}
                      </div>
                    </div>
                  ) : (
                    <div className="vg-counter-note">
                      <InfoMark />
                      {checked
                        ? "按当前输入检查后，未记录反向线索；仍需核对上游是否遗漏。"
                        : "当前未记录完整的反向线索检查，不应视为已排除反证。"}
                    </div>
                  )}
                </article>
              );
            })}
          </div>
        ) : (
          <EmptyNote>当前没有需要进一步处理的审核项。</EmptyNote>
        )}
      </section>
      <section>
        <SectionHeading title="事件关联" hint="各事件分别保留判断与引用" />
        {events.length ? (
          <div className="vg-event-list">
            {events.map((event) => (
              <article key={`${event.event_id}-${event.policy_id}`}>
                <span className="vg-event-symbol">
                  <GitBranch size={18} aria-hidden />
                </span>
                <div>
                  <h4>{POLICY_NAMES[event.policy_id] ?? "事件审核"}</h4>
                  <p>
                    事件 {event.event_id.replace(`${event.policy_id}:`, "")} ·
                    引用 {event.evidence_ids.join("、") || "未提供"}
                  </p>
                  {event.context_evidence_ids?.length ? (
                    <p>背景线索 {event.context_evidence_ids.join("、")}</p>
                  ) : null}
                  <p>{reasonText(event.reason_code)}</p>
                </div>
                <div className="vg-inline-tags">
                  <Pill tone={toneForJudgement(event.judgement)}>
                    {JUDGEMENT_LABELS[event.judgement]}
                  </Pill>
                  <Pill tone={toneForDisposition(event.disposition)}>
                    {DISPOSITION_LABELS[event.disposition]}
                  </Pill>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <EmptyNote>当前没有可单独审计的事件记录。</EmptyNote>
        )}
      </section>
      <details className="vg-evidence-archive" open={showArchive}>
        <summary>
          <strong>全部证据记录</strong>
          <span>
            {located} 条已定位 · {observations.length - located} 条未定位
            <ChevronDown size={15} aria-hidden />
          </span>
        </summary>
        <div>
          {seekDisabled && observations.length ? (
            <LimitNote>
              当前未关联原视频，可阅读证据记录，暂时无法回看片段。
            </LimitNote>
          ) : null}
          {observations.length ? (
            <div className="vg-all-evidence">
              {observations.map((item) => (
                <EvidenceCard
                  key={item.id}
                  observation={item}
                  fallbackId={item.id}
                  onSeek={onSeek}
                  seekDisabled={seekDisabled}
                  anchor
                />
              ))}
            </div>
          ) : (
            <EmptyNote>
              当前没有记录到证据；观察缺失需补充核查，不能当作没有风险。
            </EmptyNote>
          )}
          <p className="vg-observation-caveat">
            以上为模型观察记录，未经人工核实。
          </p>
        </div>
      </details>
    </div>
  );
}

function InfoMark() {
  return <CircleAlert size={14} aria-hidden />;
}

export function SummaryTab({
  report,
  planImages,
  seekDisabled,
  onSeek,
}: { report: AuditReport | null; planImages?: Record<string, CaseSceneImage[]> } & Seek) {
  if (!report) return <EmptyNote>当前没有可展示的结构化审核报告。</EmptyNote>;
  const dimensions = (
    Object.entries(report.dimension_scores) as Array<[string, AuditDimension]>
  )
    .filter(([key]) => key in DIMENSION_LABELS)
    .sort((a, b) => a[1].score - b[1].score);
  const plans = report.revision_plan;
  const actions = plans.reduce((total, plan) => total + plan.actions.length, 0);
  return (
    <div className="vg-tab-content">
      <section className="vg-next-actions">
        <span className="vg-next-actions-icon">
          <ListChecks size={27} aria-hidden />
        </span>
        <div>
          <h3>
            {actions
              ? `${actions} 项处理动作，逐项完成后再复核`
              : "完成内容核查后，再确认发布"}
          </h3>
          <p>{report.overall_direction || report.executive_summary}</p>
        </div>
        <Pill tone={toneForStatus(report.overall_verdict)}>
          {AUDIT_STATUS_LABELS[report.overall_verdict]}
        </Pill>
      </section>
      <section id="revision-plan">
        <SectionHeading
          title="处理清单"
          hint={`${plans.length} 个分组 · ${plans.reduce((total, plan) => total + plan.issues.length, 0)} 项问题`}
        />
        {plans.length ? (
          <div className="vg-revision-plans">
            {plans.map((plan) => (
              <RevisionPlan
                key={plan.id}
                plan={plan}
                images={planImages?.[plan.id]}
                onSeek={onSeek}
                seekDisabled={seekDisabled}
              />
            ))}
          </div>
        ) : (
          <EmptyNote>
            当前没有需要执行的整改动作；仍需结合原视频人工复核。
          </EmptyNote>
        )}
      </section>
      <section id="dimension-scores">
        <SectionHeading
          title="审核维度"
          hint="按评分从低到高排列 · 点击查看依据"
        />
        <div className="vg-dimension-list">
          {dimensions.map(([key, dimension]) => (
            <DimensionRow
              key={key}
              label={dimensionLabel(key)}
              dimension={dimension}
            />
          ))}
        </div>
        <p className="vg-score-note">
          综合评分 {report.overall_score}
          ，取已评估维度最低分；评分不代表违规概率或视频安全保证。
        </p>
      </section>
      {report.limitations.length ? (
        <section className="vg-report-limits">
          <CircleAlert size={17} aria-hidden />
          <div>
            <h4>本次审核的局限</h4>
            <ul>
              {report.limitations.map((item, index) => (
                <li key={index}>{item}</li>
              ))}
            </ul>
          </div>
        </section>
      ) : null}
    </div>
  );
}

function DimensionRow({
  label,
  dimension,
}: {
  label: string;
  dimension: AuditDimension;
}) {
  return (
    <details className="vg-dimension-row">
      <summary>
        <span>
          <strong>{label}</strong>
          <span>{dimension.items.length} 条子项</span>
        </span>
        <span className="vg-dimension-meter" aria-hidden>
          <i
            style={{ width: `${Math.max(0, Math.min(100, dimension.score))}%` }}
            data-tone={toneForStatus(dimension.status)}
          />
        </span>
        <strong className="vg-dimension-number">{dimension.score}</strong>
        <Pill tone={toneForStatus(dimension.status)}>
          {AUDIT_STATUS_LABELS[dimension.status]}
        </Pill>
        <ChevronDown size={15} aria-hidden />
      </summary>
      <div>
        <p>{dimension.summary}</p>
        {dimension.items.map((item) => (
          <article key={item.key}>
            <header>
              <strong>{item.label}</strong>
              <span>
                {item.score} 分 · {AUDIT_STATUS_LABELS[item.status]}
              </span>
            </header>
            <p>{item.summary}</p>
            <TimeRangeList ranges={item.time_ranges} />
            {item.limitations.map((note, index) => (
              <p key={index} className="vg-confidence-note">
                限制：{note}
              </p>
            ))}
          </article>
        ))}
        {dimension.limitations.map((note, index) => (
          <p key={index} className="vg-confidence-note">
            限制：{note}
          </p>
        ))}
      </div>
    </details>
  );
}

function RevisionPlan({
  plan,
  images,
  onSeek,
  seekDisabled,
}: { plan: AuditRevisionPlan; images?: CaseSceneImage[] } & Seek) {
  const priorityOrder = { P0: 0, P1: 1, P2: 2 } as const;
  const issues = [...plan.issues].sort(
    (a, b) => priorityOrder[a.priority] - priorityOrder[b.priority],
  );
  return (
    <article className="vg-revision-plan">
      <header>
        <div>
          <h4>{plan.section || "审核项目"}</h4>
          <Tag>{plan.scope === "EVENT" ? "事件级" : "全局"}</Tag>
          {issues[0] ? (
            <Pill tone={issues[0].priority === "P0" ? "flag" : "review"}>
              {issues[0].priority} 优先级
            </Pill>
          ) : null}
        </div>
        <TimeRangeList
          ranges={plan.video.time_ranges}
          onSeek={onSeek}
          disabled={seekDisabled}
        />
      </header>
      {images?.length ? (
        <div className="vg-plan-images">
          {images.map((image) => (
            <CaseSceneImage key={image.id} image={image} placement="issue" />
          ))}
        </div>
      ) : null}
      {plan.video.summary && plan.video.summary !== plan.section ? (
        <p className="vg-plan-summary">{plan.video.summary}</p>
      ) : null}
      <div className="vg-plan-actions">
        <h5>
          <FileCheck2 size={16} aria-hidden />
          建议执行的动作
        </h5>
        {plan.actions.length ? (
          <ol>
            {plan.actions.map((action, index) => (
              <li key={action.id}>
                <span className="vg-action-number">{index + 1}</span>
                <div>
                  <header>
                    <strong>{ACTION_LABELS[action.action]}</strong>
                    <TimeRangeList
                      ranges={action.target_time_ranges}
                      onSeek={onSeek}
                      disabled={seekDisabled}
                    />
                    {action.requires_reshoot ? <Tag>需要重拍</Tag> : null}
                  </header>
                  <p>{action.detail}</p>
                  {action.insertion_position ? (
                    <p>插入位置：{action.insertion_position}</p>
                  ) : null}
                  {action.reuse_time_ranges.length ? (
                    <div className="vg-reuse-ranges">
                      可复用片段
                      <TimeRangeList
                        ranges={action.reuse_time_ranges}
                        onSeek={onSeek}
                        disabled={seekDisabled}
                      />
                    </div>
                  ) : null}
                  <div className="vg-acceptance">
                    <Check size={14} aria-hidden />
                    <p>
                      <strong>验收标准</strong>
                      {action.acceptance_criteria}
                    </p>
                  </div>
                </div>
              </li>
            ))}
          </ol>
        ) : (
          <p>本分组暂无结构化动作，请结合问题说明人工处理。</p>
        )}
      </div>
      <details
        className="vg-plan-issues"
        open={issues.some((item) => item.priority === "P0")}
      >
        <summary>
          查看问题与依据<span>{issues.length} 项</span>
          <ChevronDown size={15} aria-hidden />
        </summary>
        <ul>
          {issues.map((issue) => (
            <IssueBlock
              key={issue.id}
              issue={issue}
              onSeek={onSeek}
              seekDisabled={seekDisabled}
            />
          ))}
        </ul>
      </details>
    </article>
  );
}

function IssueBlock({
  issue,
  onSeek,
  seekDisabled,
}: { issue: AuditRevisionPlan["issues"][number] } & Seek) {
  return (
    <li className="vg-issue-block">
      <header>
        <Pill
          tone={
            issue.priority === "P0"
              ? "flag"
              : issue.priority === "P1"
                ? "review"
                : "unknown"
          }
        >
          {issue.priority}
        </Pill>
        <strong>{issue.title}</strong>
        <TimeRangeList
          ranges={issue.time_ranges}
          onSeek={onSeek}
          disabled={seekDisabled}
        />
      </header>
      <p>{issue.description}</p>
      {issue.supporting_evidence.length ? (
        <div className="vg-issue-evidence">
          {issue.supporting_evidence.map((evidence) => (
            <div key={evidence.ref}>
              <span>{evidence.ref}</span>
              <p>{evidence.content}</p>
              {evidence.limitations.map((note, index) => (
                <p key={index} className="vg-confidence-note">
                  限制：{note}
                </p>
              ))}
            </div>
          ))}
        </div>
      ) : null}
      {issue.uncertainties.map((note, index) => (
        <p key={index} className="vg-confidence-note">
          不确定：{note}
        </p>
      ))}
      {issue.low_confidence_evidence?.length ? (
        <p className="vg-confidence-note">
          证据可信度：线索 {issue.low_confidence_evidence.join("、")}{" "}
          置信度不足，需人工确认后再据此处置。
        </p>
      ) : null}
    </li>
  );
}
