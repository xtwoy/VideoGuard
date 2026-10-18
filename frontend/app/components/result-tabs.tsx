"use client";

import { ChevronRight, PlayCircle } from "lucide-react";
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
  TimelineShot,
} from "../lib/types";
import { EmptyNote, LimitNote, Pill, SectionHeading, Tag, TimeRangeList, TimeRef } from "./ui";

const TONE_TEXT = {
  flag: "text-flag",
  review: "text-review",
  clear: "text-clear",
  unknown: "text-unknown",
} as const;

/**
 * Findings that share a judgement, a disposition and a reason say the same thing
 * ten times — one row per policy. Grouping them keeps every category and every
 * field visible while collapsing the repetition.
 */
function groupFindings(findings: Finding[]): Finding[][] {
  const groups = new Map<string, Finding[]>();
  for (const finding of findings) {
    const key = `${finding.judgement}|${finding.disposition}|${finding.reason_code}`;
    const existing = groups.get(key);
    if (existing) existing.push(finding);
    else groups.set(key, [finding]);
  }
  return [...groups.values()];
}

function groupTitle(group: Finding[]): string {
  return group.length === 1 ? policyName(group[0]) : `${group.length} 类策略`;
}

type Seek = { onSeek: (startMs: number | null) => void; seekDisabled: boolean };

/* ------------------------------------------------------------------ brief */

export function BriefTab({ result }: { result: ReviewResult }) {
  const report = result.audit_report ?? null;
  const summary = result.observation_detail?.video_summary?.summary_zh;
  const active = result.findings.filter((item) => item.disposition !== "NONE");
  const coverageTone = toneForCoverage(result.coverage);

  return (
    <div className="space-y-7">
      <section>
        <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2">
          <h3 className="font-serif text-[26px] font-bold leading-tight text-ink">
            {report ? AUDIT_STATUS_LABELS[report.overall_verdict] : "已生成结构化审核结果"}
          </h3>
          {report ? (
            <span className="tnum text-[13px] font-semibold text-ink-2">综合评分 {report.overall_score}（取最低维度）</span>
          ) : null}
        </div>        <p className="measure mt-3 text-[14px] leading-7 text-ink-2">
          {report?.executive_summary ?? "当前未生成审核总结。请查看具体证据与检查状态后再作判断。"}
        </p>
        {report?.overall_direction ? (
          <p className="measure mt-3 border-l-2 border-rule-strong pl-3 text-[13px] leading-6 text-ink-2">
            处理方向：{report.overall_direction}
          </p>
        ) : null}
      </section>

      <section aria-label="本次审核的规模">
        <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-md border border-rule bg-rule sm:grid-cols-4">
          {[
            ["检查策略", `${result.findings.length} 类`],
            ["证据线索", `${result.observations.length} 条`],
            ["待处理项", `${active.length} 项`],
            ["观察覆盖", COVERAGE_LABELS[result.coverage]],
          ].map(([label, value], index) => (
            <div key={label} className="bg-surface px-4 py-3">
              <dt className="text-[12px] font-semibold text-ink-3">{label}</dt>
              <dd className={`tnum mt-1 text-[17px] font-bold ${index === 3 ? TONE_TEXT[coverageTone] : "text-ink"}`}>
                {value}
              </dd>
            </div>
          ))}
        </dl>
        {result.coverage_notes ? <LimitNote>{result.coverage_notes}</LimitNote> : null}
      </section>

      <section>
        <SectionHeading title="需要人工处理" hint={`${active.length} 项`} />
        {active.length ? (
          <ul className="divide-y divide-rule border-y border-rule">
            {groupFindings(active).map((group) => {
              const first = group[0];
              return (
                <li
                  key={`${first.judgement}-${first.disposition}-${first.reason_code}`}
                  className="flex flex-wrap items-start justify-between gap-x-5 gap-y-2 py-3"
                >
                  <div className="min-w-0 flex-1">
                    <b className="text-[14px] font-bold text-ink">{groupTitle(group)}</b>
                    <p className="measure mt-1 text-[13px] leading-6 text-ink-2">{reasonText(first.reason_code)}</p>
                    {group.length > 1 ? (
                      <ul className="mt-2 flex flex-wrap gap-1.5">
                        {group.map((finding) => (
                          <li key={finding.policy_id}>
                            <Tag>{policyName(finding)}</Tag>
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </div>
                  <div className="flex shrink-0 flex-wrap items-center gap-2">
                    <Pill tone={toneForJudgement(first.judgement)}>{JUDGEMENT_LABELS[first.judgement]}</Pill>
                    <Pill tone={toneForDisposition(first.disposition)}>
                      {DISPOSITION_LABELS[first.disposition]}
                    </Pill>
                  </div>
                </li>
              );
            })}
          </ul>
        ) : (
          <EmptyNote>
            当前输入未发现需要处理的风险线索，可进入人工发布复核。这表示没有支持证据，不等于内容绝对安全。
          </EmptyNote>
        )}
      </section>

      <section>
        <SectionHeading title="内容摘要" hint={`观察覆盖：${COVERAGE_LABELS[result.coverage]}`} />
        <p className="measure text-[14px] leading-7 text-ink-2">{summary ?? "当前未提供内容摘要。"}</p>
      </section>
    </div>
  );
}

/* ------------------------------------------------------------------ shots */

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
    <div>
      <SectionHeading
        title="分镜结构"
        hint={seekDisabled ? "没有原视频，仅展示结构与时间" : "选择分镜可在播放器中定位"}
      />
      <ul className="divide-y divide-rule border-y border-rule">
        {shots.map((shot) => {
          const active = activeShot === shot.shot_id;
          return (
            <li key={shot.shot_id}>
              <button
                type="button"
                onClick={() => onShotClick(shot)}
                aria-pressed={active}
                className={`grid w-full grid-cols-[auto_1fr_auto] items-start gap-x-4 py-3 text-left ${
                  active ? "bg-sunken" : "hover:bg-sunken"
                }`}
              >
                <span className="flex w-24 shrink-0 flex-col gap-0.5 pl-1">
                  <b className="tnum text-[13px] font-bold text-ink">{shot.shot_id}</b>
                  <span className="tnum text-[12px] text-ink-3">
                    {formatTime(shot.start_ms)}–{formatTime(shot.end_ms)}
                  </span>
                </span>
                <span className="min-w-0">
                  <span className="block text-[14px] leading-6 text-ink">{shot.scene_summary || "未提供场景摘要"}</span>
                  <span className="mt-1 flex items-center gap-1.5 text-[12px] text-ink-3">
                    <PlayCircle size={13} aria-hidden />
                    {factCount(shot)} 条已记录事实
                    {seekDisabled ? "（无原视频）" : ""}
                  </span>
                </span>
                <ChevronRight size={16} aria-hidden className={`mt-1 shrink-0 ${active ? "text-ink" : "text-ink-3"}`} />
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/* ------------------------------------------------------------------ audit */

export function AuditTab({
  findings,
  events,
  observations,
  seekDisabled,
  onSeek,
  isDemo,
}: {
  findings: Finding[];
  events: EventFinding[];
  observations: Observation[];
} & Seek & { isDemo: boolean }) {
  const byId = new Map(observations.map((observation) => [observation.id, observation]));
  const located = observations.filter((item) => Number.isInteger(item.start_ms));
  const unlocated = observations.length - located.length;

  return (
    <div className="space-y-8">
      <section>
        <SectionHeading title="发现的问题" hint="需人工判断" />
        {findings.length ? (
          <ul className="space-y-3">
            {groupFindings(findings).map((group) => {
              const first = group[0];
              const tone = toneForDisposition(first.disposition);
              const supporting = [...new Set(group.flatMap((item) => item.supporting_ids))];
              const counter = [...new Set(group.flatMap((item) => item.counter_ids))];
              return (
                <li
                  key={`${first.judgement}-${first.disposition}-${first.reason_code}`}
                  className="rounded-md border border-rule bg-surface"
                >
                  <div className={`h-[3px] rounded-t-md ${tone === "flag" ? "bg-flag" : "bg-review"}`} aria-hidden />
                  <div className="px-4 py-3">
                    <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
                      <b className="text-[14px] font-bold text-ink">{groupTitle(group)}</b>
                      <div className="flex flex-wrap items-center gap-2">
                        <Pill tone={toneForJudgement(first.judgement)}>{JUDGEMENT_LABELS[first.judgement]}</Pill>
                        <Pill tone={tone}>{DISPOSITION_LABELS[first.disposition]}</Pill>
                      </div>
                    </div>
                    <p className="measure mt-2 text-[13px] leading-6 text-ink-2">{reasonText(first.reason_code)}</p>
                    {group.length > 1 ? (
                      <ul className="mt-2 flex flex-wrap gap-1.5">
                        {group.map((finding) => (
                          <li key={finding.policy_id}>
                            <Tag>{policyName(finding)}</Tag>
                          </li>
                        ))}
                      </ul>
                    ) : null}
                    <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2">
                      {supporting.length ? (
                        <span className="flex flex-wrap items-center gap-2">
                          <span className="text-[12px] text-ink-3">支持证据</span>
                          {supporting.map((id) => (
                            <EvidenceChip
                              key={id}
                              observation={byId.get(id)}
                              fallbackId={id}
                              onSeek={onSeek}
                              disabled={seekDisabled}
                            />
                          ))}
                        </span>
                      ) : null}
                      {counter.length ? (
                        <span className="flex flex-wrap items-center gap-2">
                          <span className="text-[12px] text-ink-3">反证</span>
                          {counter.map((id) => (
                            <EvidenceChip
                              key={id}
                              observation={byId.get(id)}
                              fallbackId={id}
                              onSeek={onSeek}
                              disabled={seekDisabled}
                            />
                          ))}
                        </span>
                      ) : null}
                      {!supporting.length && !counter.length ? (
                        <span className="text-[12px] text-ink-3">未关联到具体证据</span>
                      ) : null}
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        ) : (
          <EmptyNote>当前没有需要进一步处理的审核项。</EmptyNote>
        )}
      </section>

      <section>
        <SectionHeading title="事件级审计" hint="每个事件独立裁决、独立保留" />
        {events.length ? (
          <ul className="divide-y divide-rule border-y border-rule">
            {events.map((event) => {
              /* The backend prefixes the id with the policy; the policy is already
                 named on the left, so only the event part is worth printing. */
              const eventLabel = event.event_id.replace(`${event.policy_id}:`, "");
              return (
              <li key={`${event.event_id}-${event.policy_id}`} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 py-3">
                <div className="min-w-0">
                  <b className="text-[13px] font-bold text-ink">
                    {POLICY_NAMES[event.policy_id] ?? "事件审计"}
                  </b>
                  <span className="tnum ml-2 text-[12px] text-ink-3">事件 {eventLabel}</span>
                  <p className="mt-1 text-[12px] leading-5 text-ink-2">
                    关联证据：{event.evidence_ids.length ? event.evidence_ids.join("、") : "无"}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <Pill tone={toneForJudgement(event.judgement)}>{JUDGEMENT_LABELS[event.judgement]}</Pill>
                  <Pill tone={toneForDisposition(event.disposition)}>{DISPOSITION_LABELS[event.disposition]}</Pill>
                </div>
              </li>
              );
            })}
          </ul>
        ) : (
          <EmptyNote>当前没有可单独审计的事件记录。</EmptyNote>
        )}
      </section>

      <section>
        <SectionHeading
          title="全部证据"
          hint={
            observations.length
              ? `${located.length} 条已定位${unlocated > 0 ? ` · ${unlocated} 条未定位` : ""}`
              : undefined
          }
        />
        {seekDisabled && observations.length ? (
          <div className="mb-3">
            <LimitNote>
              {isDemo
                ? "合成场景未关联原视频，时间位置仍可读，但无法回看片段。"
                : "当前记录没有关联原视频，时间位置仍可读，但无法回看片段。"}
            </LimitNote>
          </div>
        ) : null}
        {observations.length ? (
          <ul className="divide-y divide-rule border-y border-rule">
            {observations.map((observation) => (
              <li key={observation.id} className="grid grid-cols-1 gap-x-5 gap-y-1 py-3 sm:grid-cols-[9.5rem_1fr]">
                <div className="flex flex-wrap items-baseline gap-x-2 sm:flex-col sm:gap-0.5">
                  <b className="tnum text-[13px] font-bold text-ink">{observation.id}</b>
                  <TimeRef
                    start={observation.start_ms}
                    end={observation.end_ms}
                    onSeek={onSeek}
                    disabled={seekDisabled}
                  />
                  <span className="text-[12px] text-ink-3">
                    {MODALITY_LABELS[observation.modality] ?? observation.modality}
                  </span>
                </div>
                <div className="min-w-0">
                  <p className="text-[14px] leading-6 text-ink">
                    {observation.description_redacted || observation.text_redacted || "未提供描述"}
                  </p>
                  <p className="mt-1 text-[12px] text-ink-3">模型观察，未经人工核实</p>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyNote>
            本次观察没有记录到可定位的证据。观察缺失应视为需要补充核查，不能当作没有风险。
          </EmptyNote>
        )}
      </section>
    </div>
  );
}

function EvidenceChip({
  observation,
  fallbackId,
  onSeek,
  disabled,
}: {
  observation?: Observation;
  fallbackId: string;
  onSeek: (startMs: number | null) => void;
  disabled: boolean;
}) {
  if (!observation) {
    return <Tag>{fallbackId}</Tag>;
  }
  const content = (
    <>
      <span className="tnum font-bold text-ink">{observation.id}</span>
      <span className="tnum ml-1.5 text-ink-2">{formatTime(observation.start_ms)}</span>
    </>
  );
  if (disabled) {
    return <span className="rounded-sm bg-sunken px-2 py-[3px] text-[12px]">{content}</span>;
  }
  return (
    <button
      type="button"
      onClick={() => onSeek(observation.start_ms)}
      className="rounded-sm bg-sunken px-2 py-[3px] text-[12px] hover:bg-rule"
      title="在播放器中定位到这条证据"
    >
      {content}
    </button>
  );
}

/* ---------------------------------------------------------------- summary */

export function SummaryTab({
  report,
  seekDisabled,
  onSeek,
}: { report: AuditReport | null } & Seek) {
  if (!report) return <EmptyNote>当前没有可展示的结构化审核报告。</EmptyNote>;

  // Records written before the rubric change still carry retired dimensions;
  // render only the current set rather than printing raw keys for them.
  const dimensions = (Object.entries(report.dimension_scores) as Array<[string, AuditDimension]>)
    .filter(([key]) => key in DIMENSION_LABELS)
    .sort((a, b) => a[1].score - b[1].score);

  const plans = report.revision_plan;

  return (
    <div className="space-y-8">
      <section>
        <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2">
          <h3 className="font-serif text-[22px] font-bold leading-tight text-ink">
            {AUDIT_STATUS_LABELS[report.overall_verdict]}
          </h3>
          <span className="tnum text-[13px] font-semibold text-ink-2">综合评分 {report.overall_score}（取最低维度）</span>
        </div>
        <p className="measure mt-3 text-[14px] leading-7 text-ink-2">{report.executive_summary}</p>
        <p className="measure mt-3 border-l-2 border-rule-strong pl-3 text-[13px] leading-6 text-ink-2">
          处理方向：{report.overall_direction}
        </p>
      </section>

      <section id="revision-plan" className="scroll-mt-20">
        <SectionHeading
          title="问题定位与整改"
          hint={`${plans.length} 个分组 · ${plans.reduce((total, plan) => total + plan.issues.length, 0)} 项问题 · ${plans.reduce(
            (total, plan) => total + plan.actions.length,
            0,
          )} 项动作`}
        />
        {plans.length ? (
          <div className="space-y-4">
            {plans.map((plan) => (
              <RevisionPlan
                key={plan.id}
                plan={plan}
                onSeek={onSeek}
                seekDisabled={seekDisabled}
              />
            ))}
          </div>
        ) : (
          <EmptyNote>当前没有需要执行的整改动作。</EmptyNote>
        )}
      </section>

      <section id="dimension-scores" className="scroll-mt-20">
        <SectionHeading title="维度评分" hint="按评分由低到高，展开可看子项" />
        <div className="overflow-hidden rounded-md border border-rule">
          {dimensions.map(([key, dimension]) => (
            <DimensionRow key={key} label={dimensionLabel(key)} dimension={dimension} />
          ))}
        </div>
      </section>

      {report.limitations.length ? (
        <p className="rounded-md border border-dashed border-rule-strong px-4 py-3 text-[12px] leading-6 text-ink-2">
          本报告的局限：{report.limitations.join("；")}
        </p>
      ) : null}
    </div>
  );
}

function DimensionRow({ label, dimension }: { label: string; dimension: AuditDimension }) {
  const hasDetail = dimension.items.length > 0 || dimension.limitations.length > 0;
  const body = (
    <>
      <span className="flex min-w-0 items-baseline gap-3">
        <span className="text-[14px] font-semibold text-ink">{label}</span>
        {dimension.items.length > 1 ? (
          <span className="text-[12px] text-ink-3">{dimension.items.length} 条子项</span>
        ) : null}
      </span>
      <span className="flex shrink-0 items-center gap-3">
        <span className="tnum text-[13px] font-bold text-ink-2">{dimension.score}</span>
        <Pill tone={toneForStatus(dimension.status)}>{AUDIT_STATUS_LABELS[dimension.status]}</Pill>
      </span>
    </>
  );

  const detail = (
    <div className="border-t border-rule bg-sunken px-4 py-3">
      {dimension.summary ? (
        <p className="measure text-[13px] leading-6 text-ink-2">{dimension.summary}</p>
      ) : null}
      {dimension.items.length ? (
        <ul className="mt-2 divide-y divide-rule">
          {dimension.items.map((item) => (
            <li key={item.key} className="py-2">
              <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                <span className="text-[13px] font-semibold text-ink">
                  {item.label === label ? "子项" : item.label}
                </span>
                <span className="flex items-center gap-2">
                  <span className="tnum text-[12px] font-bold text-ink-2">{item.score}</span>
                  <Pill tone={toneForStatus(item.status)}>{AUDIT_STATUS_LABELS[item.status]}</Pill>
                </span>
              </div>
              {item.summary ? <p className="measure mt-1 text-[13px] leading-6 text-ink-2">{item.summary}</p> : null}
              <div className="mt-1">
                <TimeRangeList ranges={item.time_ranges} />
              </div>
              {item.limitations.map((limitation, index) => (
                <p key={index} className="mt-1 text-[12px] leading-5 text-review">
                  限制：{limitation}
                </p>
              ))}
            </li>
          ))}
        </ul>
      ) : null}
      {dimension.limitations.map((limitation, index) => (
        <p key={index} className="mt-1 text-[12px] leading-5 text-review">
          限制：{limitation}
        </p>
      ))}
    </div>
  );

  if (!hasDetail) {
    return <div className="flex items-baseline justify-between gap-4 border-t border-rule px-4 py-3 first:border-t-0">{body}</div>;
  }

  return (
    <details className="group border-t border-rule first:border-t-0">
      <summary className="flex cursor-pointer list-none items-baseline justify-between gap-4 px-4 py-3 hover:bg-sunken [&::-webkit-details-marker]:hidden">
        {body}
        <ChevronRight
          size={15}
          aria-hidden
          className="ml-1 shrink-0 self-center text-ink-3 transition group-open:rotate-90"
        />
      </summary>
      {detail}
    </details>
  );
}

function RevisionPlan({
  plan,
  onSeek,
  seekDisabled,
}: { plan: AuditRevisionPlan } & Seek) {
  const priorityOrder = { P0: 0, P1: 1, P2: 2 } as const;
  const issues = [...plan.issues].sort((a, b) => priorityOrder[a.priority] - priorityOrder[b.priority]);
  const urgent = issues.filter((issue) => issue.priority === "P0");
  const rest = issues.filter((issue) => issue.priority !== "P0");

  return (
    <article className="rounded-md border border-rule bg-surface">
      <header className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b border-rule px-4 py-3">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h4 className="text-[15px] font-bold text-ink">{plan.section || "审核项"}</h4>
          <Tag>{plan.scope === "EVENT" ? "事件级" : "全局"}</Tag>
        </div>
        <TimeRangeList ranges={plan.video.time_ranges} onSeek={onSeek} disabled={seekDisabled} />
      </header>

      {plan.video.summary && plan.video.summary !== plan.section ? (
        <p className="measure border-b border-rule px-4 py-3 text-[13px] leading-6 text-ink-2">{plan.video.summary}</p>
      ) : null}

      <div className="px-4 py-3">
        {urgent.length ? (
          <ul className="space-y-3">
            {urgent.map((issue) => (
              <IssueBlock key={issue.id} issue={issue} onSeek={onSeek} seekDisabled={seekDisabled} />
            ))}
          </ul>
        ) : null}

        {rest.length ? (
          <details className="mt-3 border-t border-rule pt-3">
            <summary className="cursor-pointer text-[13px] font-semibold text-ink-2 hover:text-ink">
              其余 {rest.length} 项问题（P1 / P2）
            </summary>
            <ul className="mt-3 space-y-3">
              {rest.map((issue) => (
                <IssueBlock key={issue.id} issue={issue} onSeek={onSeek} seekDisabled={seekDisabled} />
              ))}
            </ul>
          </details>
        ) : null}

        {!issues.length ? <p className="text-[13px] text-ink-3">本分组没有记录问题。</p> : null}
      </div>

      {plan.actions.length ? (
        <div className="border-t border-rule bg-sunken px-4 py-3">
          <h5 className="mb-2 text-[12px] font-bold text-ink-3">整改动作</h5>
          <ul className="space-y-3">
            {plan.actions.map((action) => (
              <li key={action.id}>
                <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                  <Pill tone="unknown">{ACTION_LABELS[action.action]}</Pill>
                  <TimeRangeList ranges={action.target_time_ranges} onSeek={onSeek} disabled={seekDisabled} />
                  {action.requires_reshoot ? <Tag>需要重拍</Tag> : null}
                </div>
                <p className="measure mt-1.5 text-[13px] leading-6 text-ink">{action.detail}</p>
                {action.insertion_position ? (
                  <p className="mt-1 text-[12px] leading-5 text-ink-2">插入位置：{action.insertion_position}</p>
                ) : null}
                <p className="measure mt-1 text-[12px] leading-5 text-ink-2">
                  验收标准：{action.acceptance_criteria}
                </p>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </article>
  );
}

function IssueBlock({
  issue,
  onSeek,
  seekDisabled,
}: {
  issue: AuditRevisionPlan["issues"][number];
  onSeek: (startMs: number | null) => void;
  seekDisabled: boolean;
}) {
  const tone = issue.priority === "P0" ? "flag" : issue.priority === "P1" ? "review" : "unknown";
  return (
    <li>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <Pill tone={tone}>{issue.priority}</Pill>
        <b className="text-[13px] font-bold text-ink">{issue.title}</b>
        <TimeRangeList ranges={issue.time_ranges} onSeek={onSeek} disabled={seekDisabled} />
      </div>
      <p className="measure mt-1 text-[13px] leading-6 text-ink-2">{issue.description}</p>
      {issue.supporting_evidence.length ? (
        <ul className="mt-2 space-y-1">
          {issue.supporting_evidence.map((evidence) => (
            <li key={evidence.ref} className="text-[12px] leading-5 text-ink-2">
              <b className="tnum text-ink">{evidence.ref}</b>
              <span className="mx-1.5 text-rule-strong">/</span>
              {evidence.content}
              {evidence.limitations.map((limitation, index) => (
                <span key={index} className="block text-review">
                  限制：{limitation}
                </span>
              ))}
            </li>
          ))}
        </ul>
      ) : null}
      {issue.uncertainties.map((uncertainty, index) => (
        <p key={index} className="mt-1 text-[12px] leading-5 text-review">
          不确定：{uncertainty}
        </p>
      ))}
    </li>
  );
}
