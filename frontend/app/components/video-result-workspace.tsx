"use client";

import {
  Captions,
  ChevronRight,
  ExternalLink,
  FileCheck2,
  FileText,
  Film,
  GitBranch,
  PanelsTopLeft,
  ScanLine,
  Video,
} from "lucide-react";
import { useMemo, useState, type RefObject } from "react";
import { TAB_LABELS } from "../lib/labels";
import type { ReviewResult, TabId, TimelineShot, ViewMode } from "../lib/types";
import { AuditTab, BriefTab, ShotsTab, SummaryTab } from "./result-tabs";
import { TimeRail } from "./time-rail";
import { LimitNote } from "./ui";
import { CaseSceneImage, type CaseIllustrations } from "./case-scene-image";

export type { ReviewResult, ReviewRecord, TabId } from "../lib/types";
const TAB_ICONS = {
  brief: ScanLine,
  shots: Film,
  audit: GitBranch,
  summary: FileCheck2,
};

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
    <div className="vg-view-toggle" role="group" aria-label="报告视图">
      <button
        type="button"
        aria-pressed={mode === "structured"}
        onClick={() => onChange("structured")}
      >
        <PanelsTopLeft size={14} aria-hidden />
        交互视图
      </button>
      <button
        type="button"
        disabled={!reportUrl}
        aria-pressed={mode === "html"}
        onClick={() => onChange("html")}
      >
        <FileText size={14} aria-hidden />
        完整报告
      </button>
    </div>
  );
}

export function VideoResultWorkspace({
  result,
  videoRef,
  videoSrc,
  illustrations,
  reportUrl,
  initialTab = "brief",
  initialView = "structured",
}: {
  result: ReviewResult;
  videoRef: RefObject<HTMLVideoElement | null>;
  videoSrc?: string | null;
  illustrations?: CaseIllustrations;
  reportUrl?: string | null;
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
  const seekDisabled = !videoSrc;

  function seek(startMs: number | null): void {
    if (seekDisabled || !Number.isInteger(startMs) || !videoRef.current) return;
    videoRef.current.currentTime = (startMs ?? 0) / 1000;
    void videoRef.current.play().catch(() => undefined);
  }
  function selectShot(shot: TimelineShot): void {
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
    if (mode === "html") url.searchParams.set("view", "html");
    else url.searchParams.delete("view");
    window.history.replaceState(null, "", url);
  }

  return (
    <section className="vg-result-sheet">
      <div className="vg-result-navigation">
        <div
          role="tablist"
          aria-label="审核报告内容"
          className="vg-result-tablist"
        >
          {(Object.keys(TAB_LABELS) as TabId[]).map((tab) => {
            const Icon = TAB_ICONS[tab];
            return (
              <button
                key={tab}
                role="tab"
                type="button"
                id={`tab-${tab}`}
                aria-selected={activeTab === tab && viewMode === "structured"}
                aria-controls={`panel-${tab}`}
                tabIndex={activeTab === tab ? 0 : -1}
                onClick={() => {
                  changeView("structured");
                  changeTab(tab);
                }}
                onKeyDown={(event) => {
                  const tabs = Object.keys(TAB_LABELS) as TabId[];
                  const offset =
                    event.key === "ArrowRight"
                      ? 1
                      : event.key === "ArrowLeft"
                        ? -1
                        : 0;
                  if (!offset && event.key !== "Home" && event.key !== "End")
                    return;
                  event.preventDefault();
                  const next =
                    event.key === "Home"
                      ? tabs[0]
                      : event.key === "End"
                        ? tabs[tabs.length - 1]
                        : tabs[
                            (tabs.indexOf(tab) + offset + tabs.length) %
                              tabs.length
                          ];
                  changeView("structured");
                  changeTab(next);
                  document.getElementById(`tab-${next}`)?.focus();
                }}
              >
                <Icon size={17} aria-hidden />
                <span>{TAB_LABELS[tab]}</span>
                {tab === "audit" && activeFindings.length ? (
                  <span className="vg-tab-count">{activeFindings.length}</span>
                ) : null}
              </button>
            );
          })}
        </div>
        <ViewToggle
          mode={viewMode}
          onChange={changeView}
          reportUrl={reportUrl}
        />
      </div>

      {viewMode === "structured" ? (
        <div className="vg-result-layout">
          <div
            role="tabpanel"
            id={`panel-${activeTab}`}
            aria-labelledby={`tab-${activeTab}`}
            className="vg-result-panel"
          >
            {activeTab === "brief" ? (
              <BriefTab result={result} onNavigate={changeTab} />
            ) : null}
            {activeTab === "shots" ? (
              <ShotsTab
                shots={shots}
                activeShot={activeShot}
                onShotClick={selectShot}
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
              />
            ) : null}
            {activeTab === "summary" ? (
              <SummaryTab
                report={result.audit_report ?? null}
                planImages={illustrations?.revisionPlans}
                onSeek={seek}
                seekDisabled={seekDisabled}
              />
            ) : null}
          </div>
          <aside className="vg-video-context" aria-label={illustrations ? "场景画面与时间记录" : "原视频与时间定位"}>
            <div className="vg-context-heading">
              <Video size={17} aria-hidden />
              <h3>{illustrations ? "场景画面" : "原视频与定位"}</h3>
            </div>
            {videoSrc ? (
              <video
                ref={videoRef}
                className="vg-context-video"
                src={videoSrc}
                controls
                playsInline
                aria-label="审核原视频"
              />
            ) : illustrations?.overview.length ? (
              <div className="vg-scene-image-list">
                {illustrations.overview.map((image) => (
                  <CaseSceneImage key={image.id} image={image} />
                ))}
              </div>
            ) : (
              <div className="vg-original-missing">
                <Video size={30} strokeWidth={1.3} aria-hidden />
                <strong>当前未关联原视频</strong>
                <span>仅展示已保存的观察与时间记录</span>
              </div>
            )}
            <div className="vg-context-timeline">
              <TimeRail
                shots={shots}
                observations={result.observations}
                selectedShot={activeShot}
                onSeek={seek}
                seekDisabled={seekDisabled}
              />
            </div>
            <div className="vg-context-meta">
              <span>
                <Film size={15} aria-hidden />
                {shots.length} 个分镜
              </span>
              <span>
                <Captions size={15} aria-hidden />
                {result.observations.length} 条线索
              </span>
            </div>
            <p className="vg-context-boundary">
              {illustrations
                ? "场景配图用于界面展示，未参与审核。时间记录来自合成样例。"
                : "时间与内容来自上游观察，定位和判断均需结合原片确认。"}
            </p>
            {reportUrl ? (
              <a
                className="vg-context-report"
                href={reportUrl}
                target="_blank"
                rel="noopener noreferrer"
              >
                <FileText size={16} aria-hidden />
                打开独立报告
                <ExternalLink size={14} aria-hidden />
              </a>
            ) : null}
          </aside>
        </div>
      ) : (
        <div className="vg-html-view">
          <div>
            <h3>
              <FileText size={18} aria-hidden />
              完整审核报告
            </h3>
            {reportUrl ? (
              <a href={reportUrl} target="_blank" rel="noopener noreferrer">
                在新标签页打开
                <ExternalLink size={14} aria-hidden />
              </a>
            ) : null}
          </div>
          {reportUrl ? (
            <iframe src={reportUrl} title="服务端生成的 HTML 审核报告" />
          ) : (
            <LimitNote>当前记录没有可访问的报告地址。</LimitNote>
          )}
        </div>
      )}
    </section>
  );
}
