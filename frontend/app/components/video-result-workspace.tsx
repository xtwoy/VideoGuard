"use client";

import { ExternalLink, FileText, PanelsTopLeft } from "lucide-react";
import { useMemo, useState, type RefObject } from "react";
import { TAB_LABELS } from "../lib/labels";
import type { ReviewResult, TabId, TimelineShot, ViewMode } from "../lib/types";
import { AuditTab, BriefTab, ShotsTab, SummaryTab } from "./result-tabs";
import { TimeRail } from "./time-rail";
import { LimitNote } from "./ui";

export type { ReviewResult, ReviewRecord, TabId } from "../lib/types";

/**
 * Structured/HTML switch. Kept as its own component so the mode stays a
 * `ViewMode` here and does not get narrowed by the branch that renders it.
 */
function ViewToggle({
  mode,
  onChange,
  reportUrl,
}: {
  mode: ViewMode;
  onChange: (mode: ViewMode) => void;
  reportUrl?: string | null;
}) {
  return (
    <div className="flex items-center gap-1" role="group" aria-label="报告视图">
      <button
        type="button"
        onClick={() => onChange("structured")}
        aria-pressed={mode === "structured"}
        className={`flex items-center gap-1.5 rounded-sm px-2 py-1.5 text-[12px] font-bold ${
          mode === "structured" ? "bg-sunken text-ink" : "text-ink-3 hover:text-ink"
        }`}
      >
        <PanelsTopLeft size={14} aria-hidden />
        结构视图
      </button>
      <button
        type="button"
        disabled={!reportUrl}
        onClick={() => onChange("html")}
        aria-pressed={mode === "html"}
        className={`flex items-center gap-1.5 rounded-sm px-2 py-1.5 text-[12px] font-bold disabled:opacity-50 ${
          mode === "html" ? "bg-sunken text-ink" : "text-ink-3 hover:text-ink"
        }`}
      >
        <FileText size={14} aria-hidden />
        报告视图
      </button>
    </div>
  );
}

/**
 * The result sheet: media strip, tabs, content.
 *
 * The sheet is the whole page once a review exists. The submission controls move
 * up into a compact bar outside it, so nothing competes with the verdict.
 */
export function VideoResultWorkspace({
  result,
  videoRef,
  videoSrc,
  reportUrl,
  isDemo = false,
  initialTab = "brief",
  initialView = "structured",
}: {
  result: ReviewResult;
  videoRef: RefObject<HTMLVideoElement | null>;
  videoSrc?: string | null;
  reportUrl?: string | null;
  isDemo?: boolean;
  initialTab?: TabId;
  initialView?: ViewMode;
}) {
  const [viewMode, setViewMode] = useState<ViewMode>(initialView);
  const [activeTab, setActiveTab] = useState<TabId>(initialTab);
  const [activeShot, setActiveShot] = useState<string | null>(null);

  const shots = result.observation_detail?.timeline?.shots ?? [];
  const activeFindings = useMemo(
    () => result.findings.filter((finding) => finding.disposition !== "NONE"),
    [result],
  );

  const seekDisabled = isDemo || !videoSrc;
  const hasVideo = Boolean(videoSrc) && !isDemo;

  function seek(startMs: number | null): void {
    if (seekDisabled || !Number.isInteger(startMs)) return;
    const video = videoRef.current;
    if (!video) return;
    video.currentTime = (startMs ?? 0) / 1000;
    void video.play().catch(() => undefined);
  }

  function handleShotClick(shot: TimelineShot): void {
    setActiveShot(shot.shot_id);
    seek(shot.start_ms);
  }

  function changeTab(tab: TabId): void {
    setActiveTab(tab);
    const url = new URL(window.location.href);
    url.searchParams.set("tab", tab);
    window.history.replaceState(null, "", url);
  }

  function changeView(mode: ViewMode): void {
    setViewMode(mode);
    const url = new URL(window.location.href);
    if (mode === "html") {
      url.searchParams.set("view", "html");
    } else {
      url.searchParams.delete("view");
    }
    window.history.replaceState(null, "", url);
  }

  return (
    <section className="rounded-lg border border-rule bg-surface">
      {viewMode === "structured" ? (
        <>
          <div className={`grid ${hasVideo ? "lg:grid-cols-[17rem_1fr]" : "grid-cols-1"}`}>
            {hasVideo ? (
              <div className="border-b border-rule p-4 lg:border-b-0 lg:border-r">
                <video
                  ref={videoRef}
                  className="block w-full rounded-sm bg-ink"
                  controls
                  playsInline
                  src={videoSrc ?? undefined}
                />
                <p className="mt-2 text-[12px] leading-5 text-ink-3">原视频 · 证据定位会跳转到此播放器</p>
              </div>
            ) : null}
            <div className="px-5 pb-3 pt-4">
              <TimeRail
                shots={shots}
                observations={result.observations}
                selectedShot={activeShot}
                onSeek={seek}
                seekDisabled={seekDisabled}
                isDemo={isDemo}
              />
            </div>
          </div>

          <div className="sticky top-0 z-20 flex flex-col gap-y-1 border-y border-rule bg-surface/95 px-5 py-1 backdrop-blur sm:flex-row sm:items-center sm:justify-between sm:gap-x-4 sm:py-0">
            <div role="tablist" aria-label="审核报告内容" className="flex w-full overflow-x-auto sm:w-auto">
              {(Object.keys(TAB_LABELS) as TabId[]).map((tab) => (
                <button
                  key={tab}
                  role="tab"
                  type="button"
                  id={`tab-${tab}`}
                  aria-selected={activeTab === tab}
                  aria-controls={`panel-${tab}`}
                  onClick={() => changeTab(tab)}
                  className={`shrink-0 border-b-2 px-2.5 py-3 text-[13px] font-bold transition-colors sm:px-3 ${
                    activeTab === tab
                      ? "border-ink text-ink"
                      : "border-transparent text-ink-3 hover:border-rule-strong hover:text-ink"
                  }`}
                >
                  {TAB_LABELS[tab]}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-1 pb-1 sm:pb-0">
              <ViewToggle mode={viewMode} onChange={changeView} reportUrl={reportUrl} />
            </div>
          </div>

          <div
            role="tabpanel"
            id={`panel-${activeTab}`}
            aria-labelledby={`tab-${activeTab}`}
            className="px-5 py-5"
          >
            {activeTab === "brief" ? <BriefTab result={result} /> : null}
            {activeTab === "shots" ? (
              <ShotsTab
                shots={shots}
                activeShot={activeShot}
                onShotClick={handleShotClick}
                seekDisabled={seekDisabled}
              />
            ) : null}
            {activeTab === "audit" ? (
              <AuditTab
                findings={activeFindings}
                events={result.event_findings ?? []}
                observations={result.observations}
                onSeek={seek}
                seekDisabled={seekDisabled}
                isDemo={isDemo}
              />
            ) : null}
            {activeTab === "summary" ? (
              <SummaryTab report={result.audit_report ?? null} onSeek={seek} seekDisabled={seekDisabled} />
            ) : null}
          </div>
        </>
      ) : (
        <div className="flex flex-col gap-3 p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <ViewToggle mode="html" onChange={changeView} reportUrl={reportUrl} />
            {reportUrl ? (
              <a
                href={reportUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 rounded-sm border border-rule-strong px-2.5 py-1.5 text-[12px] font-bold text-ink-2 hover:bg-sunken"
              >
                <ExternalLink size={14} aria-hidden />
                在新标签页打开
              </a>
            ) : null}
          </div>
          {reportUrl ? (
            <iframe
              src={reportUrl}
              title="服务端生成的 HTML 审核报告"
              className="min-h-[36rem] w-full rounded-sm border border-rule"
            />
          ) : (
            <LimitNote>当前记录没有可访问的 HTML 报告地址。</LimitNote>
          )}
        </div>
      )}
    </section>
  );
}
