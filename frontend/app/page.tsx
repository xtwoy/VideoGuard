"use client";

import {
  ArrowUpRight,
  Clock3,
  Info,
  ShieldCheck,
  Sparkles,
  Upload,
  Video,
} from "lucide-react";
import { FormEvent, useEffect, useRef, useState } from "react";
import { VideoResultWorkspace, type ReviewResult } from "./components/video-result-workspace";

type ReviewRecord = {
  id: string;
  video_name: string;
  mode: "LIVE" | "DEMO";
  status: "DONE" | "ERROR";
  result: ReviewResult;
};

type Status = { message: string; error?: boolean; reviewId?: string } | null;

function apiBase(): string {
  if (typeof window === "undefined") return process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";
  return new URLSearchParams(window.location.search).get("api") || process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";
}

export default function ReviewWorkspace() {
  const [api, setApi] = useState("http://127.0.0.1:8000");
  const [connected, setConnected] = useState<boolean | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [consented, setConsented] = useState(false);
  const [record, setRecord] = useState<ReviewRecord | null>(null);
  const [status, setStatus] = useState<Status>(null);
  const [busy, setBusy] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const resultsRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const base = apiBase();
    setApi(base);
    void fetch(`${base}/api/health`)
      .then((response) => setConnected(response.ok))
      .catch(() => setConnected(false));
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
      const message = typeof detail === "string" ? detail :
        typeof detail === "object" && detail !== null && "message" in detail && typeof detail.message === "string" ? detail.message :
          `服务器错误 ${response.status}`;
      const reviewId = typeof detail === "object" && detail !== null && "review_id" in detail && typeof detail.review_id === "string" ? detail.review_id : undefined;
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
      setStatus({ message: nextRecord.mode === "DEMO" ? "合成示例已生成，以下不是实际视频检测结果。" : "审核完成。请回看相关视频片段，并下载 HTML 报告。" });
      requestAnimationFrame(() => resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }));
    } catch (error: unknown) {
      const typed = error as Error & { reviewId?: string };
      setStatus({ message: typed.message || "请求失败，请检查后端服务。", error: true, reviewId: typed.reviewId });
    } finally {
      setBusy(false);
    }
  }

  function submit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    if (!selectedFile) return setStatus({ message: "请选择视频文件。", error: true });
    if (selectedFile.size > 6_000_000) return setStatus({ message: "视频超过 6 MB，请压缩后重试。", error: true });
    if (!consented) return setStatus({ message: "请先确认素材已经授权。", error: true });
    const form = new FormData();
    form.append("video", selectedFile);
    form.append("title", title);
    form.append("consent", "true");
    void run(() => request("/api/reviews", form));
  }

  const isDemo = record?.mode === "DEMO";

  return (
    <div className="min-h-screen bg-[#f7f8fa] text-[#172033]">
      <header className="sticky top-0 z-20 border-b border-[#e4e7ec] bg-white/95 backdrop-blur">
        <div className="mx-auto flex min-h-17 w-[min(1440px,calc(100%-48px))] items-center justify-between gap-6 max-[620px]:min-h-0 max-[620px]:flex-col max-[620px]:items-start max-[620px]:py-3">
          <a className="flex items-center gap-2.5 font-extrabold" href="#top">
            <span className="grid size-8.5 place-items-center rounded-lg bg-indigo-600 text-white shadow-sm"><ShieldCheck size={18} /></span>
            <span>视鉴 <small className="block text-[9px] tracking-[0.14em] text-[#667085]">VIDEOGUARD-E</small></span>
          </a>
          <div className="flex items-center gap-3.5 text-xs text-[#667085] max-[620px]:w-full max-[620px]:justify-between">
            <span className="max-[620px]:hidden">视频内容安全审核工作台</span>
            <span className="flex items-center gap-2 border-l border-[#e4e7ec] pl-3.5 max-[620px]:border-l-0 max-[620px]:pl-0">
              <span className={`size-2 rounded-full ${connected === false ? "bg-[#d69b67]" : "bg-emerald-500"}`} />
              {connected === true ? "本地审核服务已连接" : connected === false ? "无法连接后端，请检查服务" : "连接本地审核服务中"}
            </span>
          </div>
        </div>
      </header>

      <main className="mx-auto w-[min(1440px,calc(100%-48px))] max-[620px]:w-[calc(100%-28px)]" id="top">
        <section className="flex items-end justify-between gap-7 py-9 pb-6 max-[620px]:flex-col max-[620px]:items-start max-[620px]:py-6">
          <div>
            <p className="mb-1.5 text-[10px] font-extrabold tracking-[0.12em] text-indigo-600">CONTENT REVIEW / LOCAL WORKSPACE</p>
            <h1 className="text-3xl font-bold leading-tight max-[620px]:text-[26px]">视频内容审核</h1>
            <p className="mt-2.5 max-w-165 text-sm leading-7 text-[#667085]">上传视频后，系统将整理可回溯证据，标注需要人工处理的问题，并生成可导出的审核报告。</p>
          </div>
          <div className="flex max-w-75 items-start gap-2 rounded-lg border border-purple-200 bg-purple-50 px-3 py-2.5 text-xs leading-5 text-purple-800 max-[620px]:max-w-none"><Info className="mt-0.5 shrink-0" size={16} />审核结论仅作辅助参考，需结合原视频人工核查。</div>
        </section>

        <div className="grid grid-cols-[minmax(340px,.86fr)_minmax(0,1.14fr)] items-start gap-5 max-[940px]:grid-cols-1">
          <section className="grid gap-5">
            {!record && <article className="rounded-lg border border-[#e4e7ec] bg-white p-5 shadow-sm">
              <PanelHeading kicker="MEDIA SUBMISSION" title="待审核视频" right={<Tag>{isDemo ? "合成示例" : selectedFile ? "已选择视频" : "尚未选择"}</Tag>} />
              <div className="grid min-h-90 place-items-center overflow-hidden rounded-lg border border-[#d0d5dd] bg-[#111827] max-[940px]:min-h-75 max-[620px]:min-h-62.5">
                {previewUrl ? <video ref={videoRef} className="block max-h-125 w-full bg-[#111827]" controls playsInline src={previewUrl} /> : <div className="grid place-items-center gap-2.5 px-7 text-center text-[#d0d5dd]"><span className="grid size-13.5 place-items-center rounded-full border border-[#475467] bg-[#1d2939]"><Video size={25} /></span><strong className="text-[15px] text-[#f2f4f7]">选择一段视频开始审核</strong><span className="max-w-62.5 text-xs leading-5 text-[#98a2b3]">审核完成后，可按证据时间点回看原片段</span></div>}
              </div>
              <p className="mt-3 flex items-center gap-2 text-xs leading-5 text-[#667085]"><Clock3 size={15} className="text-violet-500" />{isDemo ? "当前展示的是合成审核数据；未关联原视频，因此证据回看不可用。" : selectedFile ? `${selectedFile.name} · ${(selectedFile.size / 1_000_000).toFixed(2)} MB · 可在审核结果中回看片段` : "支持 MP4、MOV、WebM；文件不超过 6 MB，时长不超过 3 分钟。"}</p>
            </article>}

            <article className="rounded-lg border border-[#e4e7ec] bg-white p-5 shadow-sm">
              <PanelHeading kicker="NEW REVIEW" title="提交审核" right={<span className="font-serif text-3xl italic text-[#b6bdd0]">01</span>} />
              <form onSubmit={submit}>
                <label className="flex min-h-35 cursor-pointer flex-col items-center justify-center gap-1.5 rounded-lg border-2 border-dashed border-indigo-200 bg-indigo-50/50 p-4 text-center transition hover:border-indigo-600 hover:bg-indigo-50">
                  <input className="sr-only" type="file" accept=".mp4,.mov,.webm" onChange={(event) => selectFile(event.target.files?.[0] ?? null)} />
                  <span className="grid size-9 place-items-center rounded-lg border border-indigo-200 bg-white text-indigo-600"><Upload size={18} /></span>
                  <strong className="text-sm">{selectedFile?.name ?? "选择视频文件"}</strong>
                  <span className="text-[11px] text-[#667085]">{selectedFile ? `${(selectedFile.size / 1_000_000).toFixed(2)} MB · 上传前可预览` : "MP4 / MOV / WebM · 最大 6 MB"}</span>
                </label>
                <label className="mt-4 block text-xs font-bold text-[#344054]">视频标题 <span className="float-right font-normal text-[#98a2b3]">可选</span><input value={title} maxLength={100} onChange={(event) => setTitle(event.target.value)} className="mt-1.5 w-full rounded-md border border-[#d0d5dd] px-3 py-2.5 text-[13px] font-normal outline-none focus:border-indigo-600 focus:ring-3 focus:ring-indigo-100" placeholder="例如：安全教育短片" /></label>
                <label className="my-3.5 flex cursor-pointer items-start gap-2 text-xs leading-5 text-[#667085]"><input className="mt-0.75 accent-indigo-600" type="checkbox" checked={consented} onChange={(event) => setConsented(event.target.checked)} />我已获得该视频的审核处理授权，并知悉内容会传输至云端模型。</label>
                <button disabled={busy} className="flex w-full items-center justify-center gap-2 rounded-md border border-indigo-700 bg-indigo-600 px-3.5 py-2.75 text-[13px] font-bold text-white shadow-sm hover:bg-indigo-700 disabled:opacity-60" type="submit">{busy ? "审核处理中" : "开始审核"}<ArrowUpRight size={16} /></button>
              </form>
              <div className="my-4 flex items-center gap-2.5 text-[11px] text-[#98a2b3] before:h-px before:flex-1 before:bg-[#e4e7ec] after:h-px after:flex-1 after:bg-[#e4e7ec]">没有 API 配置时</div>
              <button disabled={busy} onClick={() => { clearSelectedVideo(); void run(() => request("/api/demo")); }} className="flex w-full items-center justify-center gap-2 rounded-md border border-indigo-200 bg-white px-3 py-2.5 text-[13px] font-bold text-indigo-700 hover:bg-indigo-50 disabled:opacity-60"><Sparkles size={16} />查看合成审核示例</button>
            </article>
          </section>

          <section ref={resultsRef} aria-live="polite" className="min-w-0">
            {status && <div className={`mb-4 rounded-md border-l-3 px-3 py-3 text-[13px] leading-5 ${status.error ? "border-red-500 bg-red-50 text-red-800" : "border-violet-500 bg-violet-50 text-violet-800"}`}>{status.message}{status.reviewId && <a className="mt-1.5 block w-fit font-bold underline" target="_blank" rel="noopener" href={`${api}/api/reviews/${encodeURIComponent(status.reviewId)}/report`}>查看失败记录与 HTML 报告 ↗</a>}</div>}
            <VideoResultWorkspace
              result={record?.result ?? null}
              videoRef={videoRef}
              videoSrc={previewUrl}
              reportUrl={record ? `${api}/api/reviews/${encodeURIComponent(record.id)}/report` : null}
              isDemo={isDemo}
            />
          </section>
        </div>
      </main>
      <footer className="mx-auto mt-6 flex w-[min(1440px,calc(100%-48px))] justify-between border-t border-[#e4e7ec] py-4.5 text-[11px] text-[#98a2b3] max-[620px]:w-[calc(100%-28px)] max-[620px]:flex-col max-[620px]:gap-2"><span>VIDEOGUARD-E / 内容安全审核工作台</span><span>Next.js · FastAPI · SQLite</span></footer>
    </div>
  );
}

function PanelHeading({ kicker, title, right }: { kicker: string; title: string; right: React.ReactNode }) {
  return <div className="mb-4 flex items-start justify-between gap-4 border-b border-[#f0f1f3] pb-3.75"><div><p className="mb-1.5 text-[10px] font-extrabold tracking-[0.12em] text-indigo-600">{kicker}</p><h2 className="text-[17px] font-bold">{title}</h2></div>{right}</div>;
}

function Tag({ children }: { children: React.ReactNode }) { return <span className="rounded-full border border-indigo-200 bg-indigo-50 px-2.25 py-1 text-[11px] font-bold text-indigo-700">{children}</span>; }
