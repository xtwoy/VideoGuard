"use client";

import {
  ArrowUpRight,
  CircleAlert,
  LoaderCircle,
  ShieldCheck,
  Sparkles,
  Upload,
  X,
} from "lucide-react";
import { FormEvent, useEffect, useRef, useState } from "react";
import { VideoResultWorkspace } from "./components/video-result-workspace";
import type { DemoCase, ReviewRecord, TabId, ViewMode } from "./lib/types";

type Status = { message: string; error?: boolean; reviewId?: string } | null;

const API_FALLBACK = "http://127.0.0.1:8000";
const MAX_BYTES = 6_000_000;

function apiBase(): string {
  const fromEnv = process.env.NEXT_PUBLIC_API_BASE_URL || API_FALLBACK;
  if (typeof window === "undefined") return fromEnv;
  return new URLSearchParams(window.location.search).get("api") || fromEnv;
}

export default function ReviewWorkspace() {
  const [api, setApi] = useState(API_FALLBACK);
  const [connected, setConnected] = useState<boolean | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [consented, setConsented] = useState(false);
  const [record, setRecord] = useState<ReviewRecord | null>(null);
  const [status, setStatus] = useState<Status>(null);
  const [busy, setBusy] = useState(false);
  const [demoCases, setDemoCases] = useState<DemoCase[]>([]);
  const [demoCase, setDemoCase] = useState("danger_promotion");
  const [initialTab, setInitialTab] = useState<TabId>("brief");
  const [initialView, setInitialView] = useState<ViewMode>("structured");
  const [submissionOpen, setSubmissionOpen] = useState(true);
  const videoRef = useRef<HTMLVideoElement>(null);
  const resultsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const base = apiBase();
    const params = new URLSearchParams(window.location.search);
    const tab = params.get("tab");
    if (tab === "brief" || tab === "shots" || tab === "audit" || tab === "summary") setInitialTab(tab);
    if (params.get("view") === "html") setInitialView("html");
    setApi(base);

    void fetch(`${base}/api/health`)
      .then((response) => setConnected(response.ok))
      .catch(() => setConnected(false));

    void fetch(`${base}/api/demo/cases`)
      .then((response) => (response.ok ? response.json() : Promise.reject(new Error("演示场景加载失败"))))
      .then((data: { cases: DemoCase[] }) => setDemoCases(data.cases))
      .catch(() => setDemoCases([]));

    const reviewId = params.get("review");
    if (reviewId) {
      setBusy(true);
      void fetch(`${base}/api/reviews/${encodeURIComponent(reviewId)}`)
        .then((response) => (response.ok ? response.json() : Promise.reject(new Error("审核记录不存在或服务不可用"))))
        .then((loaded: ReviewRecord) => {
          setRecord(loaded);
          setSubmissionOpen(false);
          if (loaded.result.meta?.demo_case) setDemoCase(loaded.result.meta.demo_case);
          setStatus(
            loaded.mode === "DEMO"
              ? { message: "已载入合成场景记录：冻结上游输入，PEAD 真实裁决，未关联原视频。" }
              : { message: "已载入审核记录。历史记录不保存原视频，证据时间仅供参考。" },
          );
        })
        .catch((error: Error) => setStatus({ message: error.message, error: true }))
        .finally(() => setBusy(false));
    }
  }, []);

  useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl); }, [previewUrl]);

  function selectFile(file: File | null): void {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setSelectedFile(file);
    setPreviewUrl(file ? URL.createObjectURL(file) : null);
    setRecord(null);
    setStatus(null);
  }

  function clearSelectedVideo(): void {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setSelectedFile(null);
    setPreviewUrl(null);
  }

  async function request(path: string, body?: FormData): Promise<ReviewRecord> {
    const response = await fetch(`${api}${path}`, { method: "POST", body });
    const data: unknown = await response.json().catch(() => null);
    if (!response.ok) {
      const detail = typeof data === "object" && data !== null && "detail" in data ? data.detail : null;
      const message =
        typeof detail === "string"
          ? detail
          : typeof detail === "object" && detail !== null && "message" in detail && typeof detail.message === "string"
            ? detail.message
            : `服务器错误 ${response.status}`;
      const reviewId =
        typeof detail === "object" && detail !== null && "review_id" in detail && typeof detail.review_id === "string"
          ? detail.review_id
          : undefined;
      throw Object.assign(new Error(message), { reviewId });
    }
    return data as ReviewRecord;
  }

  async function run(operation: () => Promise<ReviewRecord>): Promise<void> {
    setBusy(true);
    setRecord(null);
    setStatus({ message: "正在分析视频内容、核对可回溯证据并生成整改建议。请保持页面打开。" });
    try {
      const nextRecord = await operation();
      setRecord(nextRecord);
      setSubmissionOpen(false);
      const url = new URL(window.location.href);
      url.searchParams.set("review", nextRecord.id);
      url.searchParams.delete("tab");
      url.searchParams.delete("view");
      window.history.replaceState(null, "", url);
      setInitialTab("brief");
      setInitialView("structured");
      setStatus({
        message:
          nextRecord.mode === "DEMO"
            ? "合成场景已生成。以下是冻结输入的审核结果，不是真实视频检测结果。"
            : "审核完成。请结合证据时间回看原视频片段，并核对 HTML 报告。",
      });
      requestAnimationFrame(() => resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }));
    } catch (error: unknown) {
      const typed = error as Error & { reviewId?: string };
      setStatus({ message: typed.message || "请求失败，请检查本地审核服务是否运行。", error: true, reviewId: typed.reviewId });
    } finally {
      setBusy(false);
    }
  }

  function submit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    if (!selectedFile) return setStatus({ message: "请先选择视频文件。", error: true });
    if (selectedFile.size > MAX_BYTES) return setStatus({ message: "视频超过 6 MB，请压缩后重试。", error: true });
    if (!consented) return setStatus({ message: "请先确认已获得该素材的审核授权。", error: true });
    const form = new FormData();
    form.append("video", selectedFile);
    form.append("title", title);
    form.append("consent", "true");
    void run(() => request("/api/reviews", form));
  }

  function runDemo(): void {
    clearSelectedVideo();
    void run(() => request(demoCases.length ? `/api/demo?case=${encodeURIComponent(demoCase)}` : "/api/demo"));
  }

  const isDemo = record?.mode === "DEMO";
  const selectedCase = demoCases.find((item) => item.id === demoCase);

  return (
    <div
      className="min-h-screen"
      onDragOver={(event) => event.preventDefault()}
      onDrop={(event) => event.preventDefault()}
    >
      <header className="bg-ink text-paper">
        <div className="mx-auto flex max-w-[1200px] flex-wrap items-center justify-between gap-x-6 gap-y-2 px-5 py-3 sm:px-8">
          <a className="flex items-baseline gap-3" href="#top">
            <span className="flex items-center gap-2">
              <ShieldCheck size={19} aria-hidden className="translate-y-[2px]" />
              <span className="font-serif text-[19px] font-bold tracking-[0.02em]">视鉴</span>
            </span>
            <span className="text-[11px] font-semibold tracking-[0.18em] text-paper/60">VIDEOGUARD-E</span>
          </a>
          <div className="flex items-center gap-4 text-[12px] text-paper/75">
            <span className="hidden sm:inline">视频内容辅助审核</span>
            <span className="flex items-center gap-2">
              <span
                aria-hidden
                className={`size-1.5 rounded-full ${
                  connected === true ? "bg-paper/80" : connected === false ? "bg-review-bg" : "bg-paper/40"
                }`}
              />
              {connected === true ? "本地服务已连接" : connected === false ? "未连接到本地服务" : "正在连接本地服务"}
            </span>
          </div>
        </div>
      </header>

      <main id="top" className="mx-auto max-w-[1200px] px-5 pb-16 sm:px-8">
        {status ? (
          <div
            aria-live="polite"
            className={`mt-5 flex items-start gap-3 rounded-md border px-4 py-3 text-[13px] leading-6 ${
              status.error ? "border-flag bg-flag-bg text-flag" : "border-rule-strong bg-surface text-ink-2"
            }`}
          >
            {status.error ? (
              <CircleAlert size={16} aria-hidden className="mt-[3px] shrink-0" />
            ) : busy ? (
              <LoaderCircle size={16} aria-hidden className="mt-[3px] shrink-0 animate-spin" />
            ) : (
              <span aria-hidden className="mt-[9px] size-1.5 shrink-0 rounded-full bg-current" />
            )}
            <div className="min-w-0">
              <p>{status.message}</p>
              {status.reviewId ? (
                <a
                  className="mt-1 inline-block font-bold underline underline-offset-2"
                  target="_blank"
                  rel="noopener noreferrer"
                  href={`${api}/api/reviews/${encodeURIComponent(status.reviewId)}/report`}
                >
                  查看已保存的失败记录与报告
                </a>
              ) : null}
            </div>
            {!status.error ? (
              <button
                type="button"
                aria-label="关闭提示"
                onClick={() => setStatus(null)}
                className="ml-auto shrink-0 rounded-sm p-1 text-ink-3 hover:text-ink"
              >
                <X size={15} aria-hidden />
              </button>
            ) : null}
          </div>
        ) : null}

        {!record ? (
          <section className="pt-8 sm:pt-12">
            <h1 className="font-serif text-[30px] font-bold leading-[1.25] text-ink sm:text-[36px]">视频内容审核</h1>
            <p className="measure mt-3 text-[14px] leading-7 text-ink-2">
              上传视频后，系统整理可回溯证据、标注需要人工处理的问题，并给出带时间定位的整改建议。
            </p>
            <p className="mt-3 flex items-start gap-2 text-[12px] leading-5 text-ink-3">
              <span aria-hidden className="mt-[7px] size-1 shrink-0 rounded-full bg-ink-3" />
              审核结论仅作辅助参考，需结合原视频人工核查；系统不判定违法、身份或资质真伪。
            </p>
          </section>
        ) : null}

        {record ? (
          <ResultBar
            record={record}
            isDemo={isDemo}
            api={api}
            submissionOpen={submissionOpen}
            onToggle={() => setSubmissionOpen((open) => !open)}
          />
        ) : null}

        {!record || submissionOpen ? (
          <div className="mt-6">
            <SubmissionPanels
              selectedFile={selectedFile}
              previewUrl={previewUrl}
              title={title}
              consented={consented}
              busy={busy}
              demoCases={demoCases}
              demoCase={demoCase}
              selectedCase={selectedCase}
              isDemo={isDemo}
              onFile={selectFile}
              onClearFile={clearSelectedVideo}
              onTitle={setTitle}
              onConsent={setConsented}
              onSubmit={submit}
              onDemoCase={setDemoCase}
              onRunDemo={runDemo}
            />
          </div>
        ) : null}

        {record ? (
          <div ref={resultsRef} className="mt-6 scroll-mt-4">
            <VideoResultWorkspace
              key={record.id}
              result={record.result}
              videoRef={videoRef}
              videoSrc={previewUrl}
              reportUrl={`${api}/api/reviews/${encodeURIComponent(record.id)}/report`}
              isDemo={isDemo}
              initialTab={initialTab}
              initialView={initialView}
            />
          </div>
        ) : null}
      </main>

      <footer className="mx-auto max-w-[1200px] px-5 pb-10 sm:px-8">
        <p className="border-t border-rule pt-4 text-[12px] leading-5 text-ink-3">
          视鉴 VideoGuard-E · 辅助审核，不替代人工复核 · 本页仅通过 HTTP 与本地审核服务通信
        </p>
      </footer>
    </div>
  );
}

function ResultBar({
  record,
  isDemo,
  api,
  submissionOpen,
  onToggle,
}: {
  record: ReviewRecord;
  isDemo: boolean;
  api: string;
  submissionOpen: boolean;
  onToggle: () => void;
}) {
  const label = isDemo
    ? record.result.meta?.demo_title ?? "合成场景演示"
    : record.video_name || "当前审核记录";

  return (
    <section className="mt-5 overflow-hidden rounded-lg border border-rule bg-surface">
      <div className="flex flex-wrap items-start justify-between gap-x-5 gap-y-2 px-5 py-3.5">
        <div className="min-w-0">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <h2 className="truncate text-[15px] font-bold text-ink">{label}</h2>
            <span
              className={`rounded-sm px-2 py-[2px] text-[11px] font-bold tracking-[0.08em] ${
                isDemo ? "bg-sunken text-ink-2" : "bg-ink text-paper"
              }`}
            >
              {isDemo ? "合成场景" : "真实上传"}
            </span>
          </div>
          <p className="mt-1 text-[12px] leading-5 text-ink-3">
            {isDemo
              ? "冻结上游输入 → PEAD 证据约束与论证裁决 → 报告校验。未关联原视频，时间位置仅用于说明定位结构。"
              : `记录 ${record.id.slice(0, 8)} · 历史记录不保存原视频`}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <a
            href={`${api}/api/reviews/${encodeURIComponent(record.id)}/report`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 rounded-sm border border-rule-strong px-2.5 py-1.5 text-[12px] font-bold text-ink-2 hover:bg-sunken"
          >
            独立报告
            <ArrowUpRight size={13} aria-hidden />
          </a>
          <button
            type="button"
            onClick={onToggle}
            aria-expanded={submissionOpen}
            className="rounded-sm bg-ink px-3 py-1.5 text-[12px] font-bold text-paper hover:bg-ink-2"
          >
            {submissionOpen ? "收起" : "重新提交"}
          </button>
        </div>
      </div>
    </section>
  );
}

function SubmissionPanels({
  selectedFile,
  previewUrl,
  title,
  consented,
  busy,
  demoCases,
  demoCase,
  selectedCase,
  isDemo,
  onFile,
  onClearFile,
  onTitle,
  onConsent,
  onSubmit,
  onDemoCase,
  onRunDemo,
}: {
  selectedFile: File | null;
  previewUrl: string | null;
  title: string;
  consented: boolean;
  busy: boolean;
  demoCases: DemoCase[];
  demoCase: string;
  selectedCase?: DemoCase;
  isDemo: boolean;
  onFile: (file: File | null) => void;
  onClearFile: () => void;
  onTitle: (value: string) => void;
  onConsent: (value: boolean) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onDemoCase: (id: string) => void;
  onRunDemo: () => void;
}) {
  const [dragging, setDragging] = useState(false);

  return (
    <div className="overflow-hidden rounded-lg border border-rule bg-surface">
      <div className="grid divide-y divide-rule lg:grid-cols-[1fr_1fr] lg:divide-x lg:divide-y-0">
        {/* ---------------------------------------------------------- upload */}
        <section className="p-5 sm:p-6" aria-labelledby="upload-heading">
          <div className="flex items-baseline justify-between gap-3">
            <h2 id="upload-heading" className="text-[15px] font-bold text-ink">
              提交视频审核
            </h2>
            <span className="text-[12px] text-ink-3">MP4 / MOV / WebM</span>
          </div>

          <form onSubmit={onSubmit} className="mt-3">
            <label
              onDragOver={(event) => {
                event.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(event) => {
                event.preventDefault();
                setDragging(false);
                const file = event.dataTransfer.files?.[0];
                if (file) onFile(file);
              }}
              className={`flex cursor-pointer flex-col items-center justify-center gap-1.5 rounded-md border-2 border-dashed px-4 py-6 text-center transition-colors ${
                dragging ? "border-ink bg-sunken" : "border-rule-strong hover:border-ink-2 hover:bg-sunken"
              }`}
            >
              <input
                className="sr-only"
                type="file"
                accept=".mp4,.mov,.webm"
                onChange={(event) => onFile(event.target.files?.[0] ?? null)}
              />
              <Upload size={18} aria-hidden className="text-ink-3" />
              <strong className="text-[14px] font-bold text-ink">
                {selectedFile ? selectedFile.name : "拖入视频，或点击选择文件"}
              </strong>
              <span className="text-[12px] text-ink-3">
                {selectedFile
                  ? `${(selectedFile.size / 1_000_000).toFixed(2)} MB${previewUrl ? " · 可在上方预览" : ""}`
                  : "单个文件不超过 6 MB，时长不超过 180 秒"}
              </span>
            </label>

            {selectedFile ? (
              <div className="mt-2 flex items-center justify-between gap-3">
                <span className="text-[12px] text-ink-3">文件类型与时长最终由服务端校验。</span>
                <button
                  type="button"
                  onClick={onClearFile}
                  className="text-[12px] font-bold text-ink-2 underline underline-offset-[3px] hover:text-ink"
                >
                  移除
                </button>
              </div>
            ) : null}

            <label className="mt-4 block text-[12px] font-bold text-ink-2">
              视频标题
              <span className="ml-2 font-normal text-ink-3">可选，便于在历史记录中区分</span>
              <input
                value={title}
                maxLength={100}
                onChange={(event) => onTitle(event.target.value)}
                className="mt-1.5 w-full rounded-sm border border-rule-strong bg-surface px-3 py-2 text-[13px] font-normal text-ink placeholder:text-ink-3"
                placeholder="例如：安全教育短片"
              />
            </label>

            <label className="mt-3 flex cursor-pointer items-start gap-2.5 text-[12px] leading-5 text-ink-2">
              <input
                className="mt-[3px] size-3.5 shrink-0 accent-[#16211f]"
                type="checkbox"
                checked={consented}
                onChange={(event) => onConsent(event.target.checked)}
              />
              <span>我已获得该视频的审核处理授权，并知悉内容会传输至云端模型。</span>
            </label>

            <button
              type="submit"
              disabled={busy}
              className="mt-4 flex w-full items-center justify-center gap-2 rounded-sm bg-ink px-4 py-2.5 text-[13px] font-bold text-paper hover:bg-ink-2 disabled:opacity-60"
            >
              {busy ? <LoaderCircle size={15} aria-hidden className="animate-spin" /> : null}
              {busy ? "正在审核" : "开始审核"}
            </button>

            {previewUrl ? (
              <video
                className="mt-3 block max-h-56 w-full rounded-sm bg-ink"
                controls
                playsInline
                src={previewUrl}
                aria-label="本地预览"
              />
            ) : null}
          </form>
        </section>

        {/* ----------------------------------------------------------- demo */}
        <section className="p-5 sm:p-6" aria-labelledby="demo-heading">
          <div className="flex items-baseline justify-between gap-3">
            <h2 id="demo-heading" className="text-[15px] font-bold text-ink">
              合成场景演示
            </h2>
            <span className="text-[12px] text-ink-3">无需模型密钥</span>
          </div>
          <p className="mt-1.5 text-[12px] leading-5 text-ink-3">
            使用冻结的上游输入，PEAD 与报告链路真实执行；不调用外部模型，也不关联原视频。
          </p>

          <div
            role="radiogroup"
            aria-label="选择演示场景"
            className="mt-3 overflow-hidden rounded-md border border-rule"
          >
            {demoCases.length ? (
              demoCases.map((item) => {
                const active = item.id === demoCase;
                return (
                  <button
                    key={item.id}
                    type="button"
                    role="radio"
                    aria-checked={active}
                    disabled={busy}
                    onClick={() => onDemoCase(item.id)}
                    className={`flex w-full items-center gap-2.5 border-b border-rule px-3 py-2.5 text-left last:border-b-0 ${
                      active ? "bg-sunken" : "hover:bg-sunken"
                    }`}
                  >
                    <span
                      aria-hidden
                      className={`size-2 shrink-0 rounded-full border ${
                        active ? "border-ink bg-ink" : "border-rule-strong"
                      }`}
                    />
                    <span className={`text-[13px] ${active ? "font-bold text-ink" : "text-ink-2"}`}>{item.title}</span>
                  </button>
                );
              })
            ) : (
              <p className="px-3 py-4 text-[13px] text-ink-3">演示场景列表不可用，可改用综合合成示例。</p>
            )}
          </div>

          <p className="mt-2 min-h-[2.5rem] text-[12px] leading-5 text-ink-2">
            {selectedCase?.description ?? "无需模型密钥，使用合成证据演示完整审核流程。"}
          </p>

          <button
            type="button"
            disabled={busy}
            onClick={onRunDemo}
            className="mt-3 flex w-full items-center justify-center gap-2 rounded-sm border border-ink px-4 py-2.5 text-[13px] font-bold text-ink hover:bg-sunken disabled:opacity-60"
          >
            <Sparkles size={15} aria-hidden />
            {busy ? "正在生成" : isDemo ? "重新运行所选场景" : "运行所选场景"}
          </button>
        </section>
      </div>
    </div>
  );
}
