"use client";

import {
  ArrowLeft,
  ChevronRight,
  FileText,
  FlaskConical,
  ScanLine,
  ShieldCheck,
} from "lucide-react";
import { useRef, useState } from "react";
import type { ReviewResult, TabId, ViewMode } from "../lib/types";
import { VideoResultWorkspace } from "../components/video-result-workspace";
import { illustrationsForCase } from "./case-images";

export function ResultDesignPreview({
  cases,
  initialCase,
  initialTab,
  initialView,
}: {
  cases: Array<{ id: string; title: string; result: ReviewResult }>;
  initialCase: string;
  initialTab: TabId;
  initialView: ViewMode;
}) {
  const [caseId, setCaseId] = useState(initialCase);
  const [tab, setTab] = useState(initialTab);
  const [view, setView] = useState(initialView);
  const videoRef = useRef<HTMLVideoElement>(null);
  const selected = cases.find((item) => item.id === caseId) ?? cases[0];
  function changeCase(id: string): void {
    setCaseId(id);
    setTab("brief");
    setView("structured");
    const url = new URL(window.location.href);
    url.searchParams.set("case", id);
    url.searchParams.set("tab", "brief");
    url.searchParams.delete("view");
    window.history.replaceState(null, "", url);
  }
  return (
    <div className="vg-app">
      <aside className="vg-sidebar" aria-label="设计预览导航">
        <a className="vg-brand" href="/">
          <span className="vg-brand-mark">
            <ScanLine size={25} aria-hidden />
          </span>
          <span>
            <strong>视鉴</strong>
            <span>VideoGuard-E</span>
          </span>
        </a>
        <p className="vg-sidebar-caption">审核结果界面预览</p>
        <nav className="vg-navigation">
          <span className="vg-nav-link is-active">
            <FileText size={19} aria-hidden />
            审核结果
          </span>
          <a href="/" className="vg-nav-link">
            <ArrowLeft size={19} aria-hidden />
            正式工作台
          </a>
        </nav>
        <div className="vg-sidebar-bottom">
          <div className="vg-sidebar-evidence">
            <FlaskConical size={22} aria-hidden />
            <strong>开发专用预览</strong>
            <p>
              使用合成样例查看界面，
              <br />
              不调用真实模型服务。
            </p>
          </div>
        </div>
      </aside>
      <div className="vg-main-shell">
        <header className="vg-topbar">
          <a className="vg-mobile-brand" href="/">
            <ScanLine size={22} aria-hidden />
            <strong>视鉴</strong>
          </a>
          <div className="vg-breadcrumb">
            <span>设计预览</span>
            <ChevronRight size={14} aria-hidden />
            <strong>审核结果</strong>
          </div>
          <a className="vg-preview-back" href="/">
            <ArrowLeft size={14} aria-hidden />
            返回正式工作台
          </a>
        </header>
        <main className="vg-workspace vg-preview-workspace">
          <div className="vg-preview-notice">
            <FlaskConical size={16} aria-hidden />
            <span>
              开发预览 ·
              以下使用冻结合成样例展示审核界面；场景配图仅说明画面内容，未参与审核结论生成。生产环境不提供此页面。
            </span>
          </div>
          <div className="vg-preview-heading">
            <div>
              <h1>视频审核报告</h1>
              <p>{selected.title}</p>
            </div>
            <label>
              查看样例
              <select
                aria-label="选择设计预览样例"
                value={caseId}
                onChange={(event) => changeCase(event.target.value)}
              >
                {cases.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.title}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <VideoResultWorkspace
            key={caseId}
            result={selected.result}
            videoRef={videoRef}
            illustrations={illustrationsForCase(caseId)}
            reportUrl={`/design-preview/report?case=${encodeURIComponent(caseId)}`}
            initialTab={tab}
            initialView={view}
          />
          <footer className="vg-page-footer">
            <span>
              <ShieldCheck size={15} aria-hidden />
              界面复用正式结果组件；合成样例不作为真实识别效果证据。
            </span>
          </footer>
        </main>
      </div>
    </div>
  );
}
