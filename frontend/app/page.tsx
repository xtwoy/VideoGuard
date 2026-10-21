"use client";

import {
  ArrowUpRight,
  AudioLines,
  ChevronRight,
  CircleAlert,
  CircleCheck,
  FileCheck2,
  FileText,
  GitBranch,
  Info,
  Layers3,
  LoaderCircle,
  Plus,
  ScanLine,
  ShieldCheck,
  Video,
  X,
} from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { ReviewSubmission } from "./components/review-submission";
import { VideoResultWorkspace } from "./components/video-result-workspace";
import type { ReviewRecord, TabId, ViewMode } from "./lib/types";

type Notice = { message: string; error?: boolean; reviewId?: string } | null;
const API_FALLBACK = "http://127.0.0.1:8000";
const MAX_BYTES = 6_000_000;

function clearReviewLocation(): void {
  const url = new URL(window.location.href);
  for (const key of ["review", "tab", "view"]) url.searchParams.delete(key);
  window.history.replaceState(null, "", url);
}

export default function ReviewWorkspace() {
  const [api, setApi] = useState(API_FALLBACK);
  const [connected, setConnected] = useState<boolean | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [consented, setConsented] = useState(false);
  const [record, setRecord] = useState<ReviewRecord | null>(null);
  const [notice, setNotice] = useState<Notice>(null);
  const [busy, setBusy] = useState(false);
  const [initialTab, setInitialTab] = useState<TabId>("brief");
  const [initialView, setInitialView] = useState<ViewMode>("structured");
  const videoRef = useRef<HTMLVideoElement>(null);
  const resultsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams(window.location.search);
    const base =
      params.get("api") || process.env.NEXT_PUBLIC_API_BASE_URL || API_FALLBACK;
    const tab = params.get("tab");
    if (
      tab === "brief" ||
      tab === "shots" ||
      tab === "audit" ||
      tab === "summary"
    )
      setInitialTab(tab);
    if (params.get("view") === "html") setInitialView("html");
    setApi(base);
    void fetch(`${base}/api/health`, { signal: controller.signal })
      .then((response) => setConnected(response.ok))
      .catch(() => {
        if (!controller.signal.aborted) setConnected(false);
      });
    const reviewId = params.get("review");
    if (reviewId) {
      setBusy(true);
      void fetch(`${base}/api/reviews/${encodeURIComponent(reviewId)}`, {
        signal: controller.signal,
      })
        .then((response) =>
          response.ok
            ? response.json()
            : Promise.reject(
                new Error("无法载入审核记录，请检查记录地址和审核服务。"),
              ),
        )
        .then((loaded: ReviewRecord) => {
          if (loaded.mode !== "LIVE")
            throw new Error("该记录不是正式视频审核记录，请上传视频开始审核。");
          setRecord(loaded);
          setNotice({
            message: "已载入审核记录。原视频不随记录保存，当前无法回看原片。",
          });
        })
        .catch((error: Error) => {
          if (!controller.signal.aborted)
            setNotice({ message: error.message, error: true });
        })
        .finally(() => {
          if (!controller.signal.aborted) setBusy(false);
        });
    }
    return () => controller.abort();
  }, []);

  useEffect(
    () => () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    },
    [previewUrl],
  );

  function selectFile(file: File | null): void {
    if (busy) return;
    setSelectedFile(file);
    setPreviewUrl(file ? URL.createObjectURL(file) : null);
    setConsented(false);
    setRecord(null);
    setNotice(null);
    clearReviewLocation();
  }

  function newReview(): void {
    if (busy) return;
    selectFile(null);
    setTitle("");
    setInitialTab("brief");
    setInitialView("structured");
    window.scrollTo({ top: 0, behavior: "instant" });
  }

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (busy) return;
    if (!selectedFile)
      return setNotice({ message: "请先选择需要审核的视频。", error: true });
    if (selectedFile.size > MAX_BYTES)
      return setNotice({
        message: "视频超过 6 MB，请压缩后重新选择。",
        error: true,
      });
    if (!consented)
      return setNotice({
        message: "开始审核前，请确认已获得素材授权并同意处理说明。",
        error: true,
      });
    const form = new FormData();
    form.append("video", selectedFile);
    form.append("title", title);
    form.append("consent", "true");
    setBusy(true);
    setNotice({
      message: "正在审核视频并整理证据与处理建议，请保持页面打开。",
    });
    try {
      const response = await fetch(`${api}/api/reviews`, {
        method: "POST",
        body: form,
      });
      const data: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        const detail =
          typeof data === "object" && data !== null && "detail" in data
            ? data.detail
            : null;
        const message =
          typeof detail === "string"
            ? detail
            : typeof detail === "object" &&
                detail !== null &&
                "message" in detail &&
                typeof detail.message === "string"
              ? detail.message
              : `审核未能完成（${response.status}），请检查服务后重试。`;
        const reviewId =
          typeof detail === "object" &&
          detail !== null &&
          "review_id" in detail &&
          typeof detail.review_id === "string"
            ? detail.review_id
            : undefined;
        throw Object.assign(new Error(message), { reviewId });
      }
      const next = data as ReviewRecord;
      if (next.mode !== "LIVE")
        throw new Error("审核服务未返回正式审核记录，请检查服务配置后重试。");
      setRecord(next);
      setInitialTab("brief");
      setInitialView("structured");
      const url = new URL(window.location.href);
      url.searchParams.set("review", next.id);
      url.searchParams.delete("tab");
      url.searchParams.delete("view");
      window.history.replaceState(null, "", url);
      setNotice({
        message: "审核完成。请结合证据定位回看视频，并确认需要处理的问题。",
      });
      requestAnimationFrame(() =>
        resultsRef.current?.scrollIntoView({
          behavior: window.matchMedia("(prefers-reduced-motion: reduce)")
            .matches
            ? "instant"
            : "smooth",
          block: "start",
        }),
      );
    } catch (error: unknown) {
      const failure = error as Error & { reviewId?: string };
      setNotice({
        message: failure.message || "无法连接审核服务，请检查连接后重试。",
        error: true,
        reviewId: failure.reviewId,
      });
    } finally {
      setBusy(false);
    }
  }

  const connectionLabel =
    connected === true
      ? "审核服务已连接"
      : connected === false
        ? "审核服务未连接"
        : "正在连接审核服务";

  return (
    <div
      className="vg-app"
      onDragOver={(event) => event.preventDefault()}
      onDrop={(event) => event.preventDefault()}
    >
      <a className="vg-skip-link" href="#workspace">
        跳转到审核工作区
      </a>
      <aside className="vg-sidebar" aria-label="工作台导航">
        <a className="vg-brand" href="#workspace">
          <span className="vg-brand-mark">
            <ScanLine size={25} aria-hidden />
          </span>
          <span>
            <strong>视鉴</strong>
            <span>VideoGuard-E</span>
          </span>
        </a>
        <p className="vg-sidebar-caption">视频内容安全工作台</p>
        <nav className="vg-navigation">
          <a
            className="vg-nav-link is-active"
            href="#workspace"
            aria-current="page"
          >
            <Video size={19} aria-hidden />
            视频审核
            <span className="vg-nav-indicator" />
          </a>
          {record ? (
            <a className="vg-nav-link" href="#review-result">
              <FileText size={19} aria-hidden />
              当前报告
            </a>
          ) : null}
          <a className="vg-nav-link" href="#review-guide">
            <Info size={19} aria-hidden />
            审核说明
          </a>
        </nav>
        <div className="vg-sidebar-bottom">
          <div className="vg-sidebar-evidence">
            <GitBranch size={23} aria-hidden />
            <strong>让判断有据可查</strong>
            <p>
              连接视频、时间与证据，
              <br />
              为人工复核提供清晰依据。
            </p>
            <div className="vg-evidence-motif" aria-hidden>
              <i />
              <span />
              <i />
              <span />
              <i />
            </div>
          </div>
          <div className="vg-sidebar-footer">
            <ShieldCheck size={14} aria-hidden />
            <span>内容安全辅助审核</span>
            <span>v0.6</span>
          </div>
        </div>
      </aside>
      <div className="vg-main-shell">
        <header className="vg-topbar">
          <a href="#workspace" className="vg-mobile-brand">
            <ScanLine size={22} aria-hidden />
            <strong>视鉴</strong>
            <span>VideoGuard-E</span>
          </a>
          <div className="vg-breadcrumb">
            <span>工作台</span>
            <ChevronRight size={14} aria-hidden />
            <strong>视频审核</strong>
          </div>
          <div
            className={`vg-connection ${connected === false ? "is-offline" : connected === null ? "is-pending" : ""}`}
            role="status"
          >
            <span className="vg-connection-dot" />
            {connectionLabel}
          </div>
        </header>
        <main id="workspace" className="vg-workspace">
          <div className="vg-page-heading">
            <div>
              <div className="vg-page-title">
                <h1>{record ? "视频审核报告" : "视频内容审核"}</h1>
                <span className="vg-product-tag">
                  <ShieldCheck size={13} aria-hidden />
                  证据约束审核
                </span>
              </div>
              <p>
                {record
                  ? "查看风险线索与证据关联，逐项确认需要处理的内容。"
                  : "从视频中发现风险线索，让每一个判断都有迹可循。"}
              </p>
            </div>
            {record ? (
              <button
                className="vg-button vg-button-primary"
                type="button"
                disabled={busy}
                onClick={newReview}
              >
                <Plus size={17} aria-hidden />
                新建审核
              </button>
            ) : (
              <div className="vg-heading-note">
                <FileCheck2 size={17} aria-hidden />
                <span>上传素材，开始一次新的审核</span>
              </div>
            )}
          </div>
          {notice ? (
            <div
              className={`vg-notice ${notice.error ? "is-error" : ""}`}
              role={notice.error ? "alert" : "status"}
            >
              {notice.error ? (
                <CircleAlert size={18} aria-hidden />
              ) : busy ? (
                <LoaderCircle size={18} className="animate-spin" aria-hidden />
              ) : (
                <CircleCheck size={18} aria-hidden />
              )}
              <div>
                <p>{notice.message}</p>
                {notice.reviewId ? (
                  <a
                    target="_blank"
                    rel="noopener noreferrer"
                    href={`${api}/api/reviews/${encodeURIComponent(notice.reviewId)}/report`}
                  >
                    查看已保存的失败记录与报告
                    <ArrowUpRight size={13} aria-hidden />
                  </a>
                ) : null}
              </div>
              {!busy ? (
                <button
                  type="button"
                  className="vg-icon-button"
                  aria-label="关闭提示"
                  onClick={() => setNotice(null)}
                >
                  <X size={16} aria-hidden />
                </button>
              ) : null}
            </div>
          ) : null}
          {!record ? (
            <ReviewSubmission
              selectedFile={selectedFile}
              previewUrl={previewUrl}
              title={title}
              consented={consented}
              busy={busy}
              onFile={selectFile}
              onTitle={setTitle}
              onConsent={setConsented}
              onSubmit={submit}
            />
          ) : (
            <div ref={resultsRef} id="review-result" className="vg-results">
              <section className="vg-record-bar">
                <span className="vg-record-icon">
                  <Video size={20} aria-hidden />
                </span>
                <div>
                  <h2>{record.video_name || "当前审核记录"}</h2>
                  <p>
                    记录 {record.id.slice(0, 8)}
                    {previewUrl ? " · 已关联本地原视频" : " · 未关联原视频"}
                  </p>
                </div>
                <a
                  className="vg-button vg-button-secondary"
                  href={`${api}/api/reviews/${encodeURIComponent(record.id)}/report`}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <FileText size={16} aria-hidden />
                  独立报告
                  <ArrowUpRight size={14} aria-hidden />
                </a>
              </section>
              <VideoResultWorkspace
                key={record.id}
                result={record.result}
                videoRef={videoRef}
                videoSrc={previewUrl}
                reportUrl={`${api}/api/reviews/${encodeURIComponent(record.id)}/report`}
                initialTab={initialTab}
                initialView={initialView}
              />
            </div>
          )}
          <section
            id="review-guide"
            className="vg-review-guide"
            aria-labelledby="review-guide-title"
          >
            <div className="vg-guide-heading">
              <h2 id="review-guide-title">围绕证据，完成一次审核</h2>
              <span>机器辅助判断，最终由你确认</span>
            </div>
            <div className="vg-guide-steps">
              <div>
                <span className="vg-guide-icon">
                  <Layers3 size={21} aria-hidden />
                </span>
                <div>
                  <h3>整理视频线索</h3>
                  <p>关联画面、语音与文本，组织可追溯的观察。</p>
                </div>
                <ChevronRight size={17} className="vg-step-arrow" aria-hidden />
              </div>
              <div>
                <span className="vg-guide-icon">
                  <GitBranch size={21} aria-hidden />
                </span>
                <div>
                  <h3>核对证据关系</h3>
                  <p>结合事件与语境，保留证据不足及冲突。</p>
                </div>
                <ChevronRight size={17} className="vg-step-arrow" aria-hidden />
              </div>
              <div>
                <span className="vg-guide-icon">
                  <FileCheck2 size={21} aria-hidden />
                </span>
                <div>
                  <h3>定位并人工复核</h3>
                  <p>回看对应片段，逐项确认风险与处理建议。</p>
                </div>
              </div>
            </div>
          </section>
          <footer className="vg-page-footer">
            <span>
              <ShieldCheck size={15} aria-hidden />
              审核结果仅作辅助参考，不替代人工复核与事实认定。
            </span>
            <span className="vg-footer-modalities">
              <Video size={14} aria-hidden />
              画面
              <AudioLines size={14} aria-hidden />
              语音
              <FileText size={14} aria-hidden />
              文本
            </span>
          </footer>
        </main>
      </div>
    </div>
  );
}
