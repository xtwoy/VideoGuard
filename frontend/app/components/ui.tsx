import type { ReactNode } from "react";
import { formatTime, type Tone } from "../lib/labels";

const TONE_PILL: Record<Tone, string> = {
  flag: "bg-flag-bg text-flag",
  review: "bg-review-bg text-review",
  clear: "bg-clear-bg text-clear",
  unknown: "bg-unknown-bg text-unknown",
};

/**
 * A status pill. Always carries words; colour is a second signal, never the only one.
 */
export function Pill({ tone, children, quiet = false }: { tone: Tone; children: ReactNode; quiet?: boolean }) {
  return (
    <span
      className={`inline-flex items-center rounded-sm px-2 py-[3px] text-[12px] font-bold leading-[1.5] whitespace-nowrap ${TONE_PILL[tone]} ${
        quiet ? "opacity-90" : ""
      }`}
    >
      {children}
    </span>
  );
}

/** Neutral pill for identity, source and scope. Never used for judgement. */
export function Tag({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-sm border border-rule-strong px-2 py-[2px] text-[12px] font-semibold leading-[1.5] text-ink-2 whitespace-nowrap">
      {children}
    </span>
  );
}

export function SectionHeading({
  title,
  hint,
  level = 3,
}: {
  title: string;
  hint?: ReactNode;
  level?: 2 | 3;
}) {
  const Tag = level === 2 ? "h2" : "h3";
  return (
    <div className="mb-3 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
      <Tag className="text-[15px] font-bold text-ink">{title}</Tag>
      {hint ? <span className="text-[12px] leading-5 text-ink-3">{hint}</span> : null}
    </div>
  );
}

/**
 * A time position. Becomes a button only when the original video is attached;
 * otherwise it stays plain text at full contrast — the position is still the
 * most useful thing on the row even when it cannot be played.
 */
export function TimeRef({
  start,
  end,
  onSeek,
  disabled,
  tone = "neutral",
}: {
  start: number | null;
  end?: number | null;
  onSeek?: (startMs: number | null) => void;
  disabled?: boolean;
  tone?: "neutral" | "accent";
}) {
  const label = end === undefined || end === null ? formatTime(start) : `${formatTime(start)}–${formatTime(end)}`;
  const base = "tnum text-[13px] font-semibold";
  const colour = tone === "accent" ? "text-ink" : "text-ink-2";

  if (disabled || !onSeek || !Number.isInteger(start)) {
    return <span className={`${base} ${colour}`}>{label}</span>;
  }
  return (
    <button
      type="button"
      onClick={() => onSeek(start)}
      className={`${base} ${colour} rounded-sm px-1 -mx-1 underline decoration-rule-strong decoration-1 underline-offset-[3px] hover:bg-sunken hover:decoration-ink`}
      title="在播放器中定位到这一段"
    >
      {label}
    </button>
  );
}

export function TimeRangeList({
  ranges,
  onSeek,
  disabled,
}: {
  ranges: Array<{ start_ms: number; end_ms: number }>;
  onSeek?: (startMs: number | null) => void;
  disabled?: boolean;
}) {
  if (!ranges.length) return <span className="text-[13px] text-ink-3">未精确定位</span>;
  return (
    <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
      {ranges.map((range, index) => (
        <TimeRef
          key={`${range.start_ms}-${range.end_ms}-${index}`}
          start={range.start_ms}
          end={range.end_ms}
          onSeek={onSeek}
          disabled={disabled}
        />
      ))}
    </span>
  );
}

export function EmptyNote({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-md border border-dashed border-rule-strong px-4 py-5 text-center text-[13px] leading-6 text-ink-2">
      {children}
    </p>
  );
}

/**
 * An explanation of what cannot be done, and why. Used wherever the interface
 * would otherwise look interactive but is not.
 */
export function LimitNote({ children }: { children: ReactNode }) {
  return (
    <p className="flex items-start gap-2 text-[12px] leading-5 text-ink-3">
      <span aria-hidden className="mt-[7px] size-1 shrink-0 rounded-full bg-ink-3" />
      <span>{children}</span>
    </p>
  );
}

export function KeyValue({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1 border-t border-rule py-3 first:border-t-0 first:pt-0">
      <span className="text-[12px] font-semibold text-ink-3">{label}</span>
      <span className="text-[13px] leading-6 text-ink-2">{children}</span>
    </div>
  );
}
