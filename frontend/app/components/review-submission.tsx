"use client";

import {
  AudioLines,
  Captions,
  Check,
  FileVideo2,
  FolderOpen,
  GitBranch,
  LoaderCircle,
  LockKeyhole,
  ScanLine,
  ShieldCheck,
  Upload,
  Video,
  X,
} from "lucide-react";
import { useRef, useState, type FormEvent } from "react";

type Props = {
  selectedFile: File | null;
  previewUrl: string | null;
  title: string;
  consented: boolean;
  busy: boolean;
  onFile: (file: File | null) => void;
  onTitle: (title: string) => void;
  onConsent: (consented: boolean) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
};

export function ReviewSubmission({
  selectedFile,
  previewUrl,
  title,
  consented,
  busy,
  onFile,
  onTitle,
  onConsent,
  onSubmit,
}: Props) {
  const fileRef = useRef<HTMLInputElement>(null);
  const dragDepth = useRef(0);
  const [dragging, setDragging] = useState(false);
  return (
    <form className="vg-submission" onSubmit={onSubmit} aria-busy={busy}>
      <section className="vg-media-panel" aria-labelledby="video-heading">
        <div className="vg-panel-heading">
          <div>
            <span className="vg-panel-icon">
              <Video size={19} aria-hidden />
            </span>
            <h2 id="video-heading">视频素材</h2>
          </div>
          <span className="vg-file-state">
            {selectedFile ? "已选择素材" : "等待选择素材"}
          </span>
        </div>
        <div
          className={`vg-dropzone ${dragging ? "is-dragging" : ""} ${selectedFile ? "has-video" : ""}`}
          onDragEnter={(event) => {
            event.preventDefault();
            if (!busy) {
              dragDepth.current++;
              setDragging(true);
            }
          }}
          onDragOver={(event) => {
            event.preventDefault();
            event.dataTransfer.dropEffect = busy ? "none" : "copy";
          }}
          onDragLeave={(event) => {
            event.preventDefault();
            dragDepth.current = Math.max(0, dragDepth.current - 1);
            if (!dragDepth.current) setDragging(false);
          }}
          onDrop={(event) => {
            event.preventDefault();
            dragDepth.current = 0;
            setDragging(false);
            if (!busy) {
              const file = event.dataTransfer.files?.[0];
              if (file) onFile(file);
            }
          }}
        >
          <input
            ref={fileRef}
            type="file"
            className="sr-only"
            aria-label="选择需要审核的视频"
            accept=".mp4,.mov,.webm,video/mp4,video/quicktime,video/webm"
            disabled={busy}
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) onFile(file);
              event.target.value = "";
            }}
          />
          {previewUrl ? (
            <video
              src={previewUrl}
              controls
              playsInline
              preload="metadata"
              className="vg-video-preview"
              aria-label="已选择视频的本地预览"
            />
          ) : (
            <div className="vg-upload-content">
              <div className="vg-viewfinder" aria-hidden>
                <i />
                <i />
                <i />
                <i />
                <div className="vg-upload-symbol">
                  <FileVideo2 size={43} strokeWidth={1.5} />
                  <span>
                    <Upload size={17} strokeWidth={2.5} />
                  </span>
                </div>
                <div className="vg-scan-line" />
              </div>
              <h3>{dragging ? "松开即可添加视频" : "将视频拖到这里"}</h3>
              <p>或从本地选择一段需要审核的视频</p>
              <button
                className="vg-button vg-upload-button"
                type="button"
                disabled={busy}
                onClick={() => fileRef.current?.click()}
              >
                <FolderOpen size={17} aria-hidden />
                选择视频文件
              </button>
            </div>
          )}
          {dragging && selectedFile ? (
            <div className="vg-drop-overlay">
              <Upload size={28} aria-hidden />
              松开以更换视频
            </div>
          ) : null}
        </div>
        {selectedFile ? (
          <div className="vg-selected-file">
            <span className="vg-selected-file-icon">
              <FileVideo2 size={21} aria-hidden />
            </span>
            <div>
              <strong title={selectedFile.name}>{selectedFile.name}</strong>
              <span>
                {(selectedFile.size / 1_000_000).toFixed(2)} MB ·
                文件类型与时长由服务端校验
              </span>
            </div>
            <button
              className="vg-icon-button"
              aria-label="移除已选择的视频"
              type="button"
              disabled={busy}
              onClick={() => onFile(null)}
            >
              <X size={17} aria-hidden />
            </button>
            <button
              className="vg-text-button"
              type="button"
              disabled={busy}
              onClick={() => fileRef.current?.click()}
            >
              更换视频
            </button>
          </div>
        ) : (
          <div className="vg-modality-strip" aria-label="审核使用的视频信息">
            <div>
              <Video size={18} aria-hidden />
              <span>画面观察</span>
              <span className="vg-mini-film" aria-hidden>
                <i />
                <i />
                <i />
              </span>
            </div>
            <div>
              <AudioLines size={18} aria-hidden />
              <span>语音线索</span>
              <span className="vg-mini-wave" aria-hidden>
                {[4, 9, 15, 7, 19, 12, 6, 14, 8].map((height, index) => (
                  <i key={index} style={{ height }} />
                ))}
              </span>
            </div>
            <div>
              <Captions size={18} aria-hidden />
              <span>文本内容</span>
              <span className="vg-mini-text" aria-hidden>
                <i />
                <i />
              </span>
            </div>
          </div>
        )}
        <p className="vg-material-note">
          <LockKeyhole size={14} aria-hidden />
          原始视频不进入审核数据库，审核记录保留脱敏后的结构化结果。
        </p>
      </section>
      <aside className="vg-settings-panel" aria-labelledby="settings-heading">
        <div className="vg-settings-heading">
          <h2 id="settings-heading">审核设置</h2>
          <p>补充素材信息，确认后开始审核。</p>
        </div>
        <label className="vg-input-label" htmlFor="video-title">
          视频标题<span>选填</span>
        </label>
        <input
          id="video-title"
          className="vg-text-input"
          placeholder="为这次审核起个名字"
          value={title}
          maxLength={100}
          disabled={busy}
          onChange={(event) => onTitle(event.target.value)}
        />
        <div className="vg-review-scope">
          <h3>
            审核范围<span>短视频内容安全</span>
          </h3>
          <div>
            <span className="vg-scope-icon">
              <ScanLine size={17} aria-hidden />
            </span>
            <div>
              <strong>发现风险线索</strong>
              <p>关注内容中的疑似风险与观察缺口</p>
            </div>
          </div>
          <div>
            <span className="vg-scope-icon">
              <GitBranch size={17} aria-hidden />
            </span>
            <div>
              <strong>关联事件证据</strong>
              <p>结合时间与语境，核对证据关系</p>
            </div>
          </div>
          <div>
            <span className="vg-scope-icon">
              <ShieldCheck size={17} aria-hidden />
            </span>
            <div>
              <strong>给出处理依据</strong>
              <p>保留原因、时间定位与复核建议</p>
            </div>
          </div>
        </div>
        <div className="vg-output-note">
          <span>
            <Check size={13} aria-hidden />
            风险候选
          </span>
          <span>
            <Check size={13} aria-hidden />
            证据定位
          </span>
          <span>
            <Check size={13} aria-hidden />
            处理建议
          </span>
        </div>
        <label className="vg-consent">
          <input
            type="checkbox"
            checked={consented}
            disabled={busy}
            onChange={(event) => onConsent(event.target.checked)}
          />
          <span>
            我已获得该视频的审核处理授权，并知悉内容会传输至云端模型进行分析。
          </span>
        </label>
        <button
          className="vg-button vg-button-primary vg-submit-button"
          disabled={busy}
          type="submit"
        >
          {busy ? (
            <LoaderCircle size={18} className="animate-spin" aria-hidden />
          ) : (
            <ScanLine size={18} aria-hidden />
          )}
          {busy ? "正在审核，请稍候" : "开始审核"}
        </button>
        <p className="vg-submit-note">审核结论需结合原视频人工确认</p>
      </aside>
    </form>
  );
}
