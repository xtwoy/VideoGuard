import { formatTime } from "../lib/labels";
import type { Observation, TimelineShot } from "../lib/types";
import { LimitNote } from "./ui";

/**
 * The time rail.
 *
 * This is the one structural idea in the interface: an audit is a reading of a
 * timeline, so the timeline itself is drawn to scale. Shots are bands, evidence
 * is ticks, and both sit at their real millisecond position. Everything else on
 * the page stays quiet around it.
 *
 * With no attached video the rail still communicates structure; seeking is
 * disabled and the reason is stated instead of silently doing nothing.
 */
export function TimeRail({
  shots,
  observations,
  selectedShot,
  onSeek,
  seekDisabled,
  isDemo,
}: {
  shots: TimelineShot[];
  observations: Observation[];
  selectedShot?: string | null;
  onSeek?: (startMs: number | null) => void;
  seekDisabled: boolean;
  isDemo: boolean;
}) {
  const located = observations.filter(
    (item) => Number.isInteger(item.start_ms) && (item.start_ms ?? -1) >= 0,
  );
  const unlocated = observations.length - located.length;

  const endMs = Math.max(
    0,
    ...shots.map((shot) => (Number.isInteger(shot.end_ms) ? shot.end_ms : 0)),
    ...located.map((item) => item.end_ms ?? item.start_ms ?? 0),
  );

  if (!shots.length && !located.length) {
    return (
      <p className="text-[13px] leading-6 text-ink-2">
        本次结果没有可定位的时间结构，证据与结论仍可在下方查看。
      </p>
    );
  }

  const duration = endMs > 0 ? endMs : 1;
  const pct = (ms: number) => Math.min(100, Math.max(0, (ms / duration) * 100));
  /* With few ticks the id is worth printing; with many they would collide. */
  const showTickLabels = located.length <= 6;

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h3 className="text-[12px] font-bold text-ink-3">时间轴</h3>
        <span className="tnum text-[12px] text-ink-3">
          时长 {formatTime(endMs)} · {shots.length} 个分镜 · {located.length} 条定位证据
          {unlocated > 0 ? ` · ${unlocated} 条未定位` : ""}
        </span>
      </div>

      <div
        className="relative select-none"
        role="group"
        aria-label="视频时间轴：上方为分镜，下方为证据位置"
      >
        {/* Shot bands */}
        <div className="relative h-7 overflow-hidden rounded-sm border border-rule bg-sunken">
          {shots.map((shot, index) => {
            const left = pct(shot.start_ms);
            const width = Math.max(pct(shot.end_ms) - left, 0.6);
            const active = selectedShot === shot.shot_id;
            const wide = width > 9;
            return (
              <div
                key={shot.shot_id}
                className={`absolute inset-y-0 border-r border-rule-strong last:border-r-0 ${
                  active ? "bg-ink text-paper" : index % 2 ? "bg-white" : "bg-sunken"
                }`}
                style={{ left: `${left}%`, width: `${width}%` }}
              >
                {wide ? (
                  <span
                    className={`tnum absolute inset-0 flex items-center justify-center overflow-hidden px-1 text-[11px] font-semibold ${
                      active ? "text-paper" : "text-ink-2"
                    }`}
                  >
                    {shot.shot_id}
                  </span>
                ) : null}
              </div>
            );
          })}
        </div>

        {/* Evidence ticks */}
        <div className={`relative mt-1 ${showTickLabels ? "h-11" : "h-6"}`}>
          <div className="absolute inset-x-0 top-2 h-px bg-rule" aria-hidden />
          {located.map((item) => {
            const left = pct(item.start_ms ?? 0);
            const caption = `${item.id} · ${formatTime(item.start_ms)}`;
            const labelAlign = left < 12 ? "left-0" : left > 88 ? "right-0" : "left-1/2 -translate-x-1/2";
            const marker = (
              <>
                <span className="h-2 w-px bg-ink-2" aria-hidden />
                <span className="size-[9px] rounded-full border-2 border-surface bg-ink" aria-hidden />
                {showTickLabels ? (
                  <span className={`tnum absolute top-[13px] whitespace-nowrap text-[11px] font-semibold text-ink-2 ${labelAlign}`}>
                    {item.id}
                  </span>
                ) : null}
              </>
            );
            return seekDisabled || !onSeek ? (
              <span
                key={item.id}
                className="absolute top-0 flex -translate-x-1/2 flex-col items-center"
                style={{ left: `${left}%` }}
                title={`${caption}（未关联原视频，无法定位播放）`}
              >
                {marker}
                <span className="sr-only">{caption}</span>
              </span>
            ) : (
              <button
                key={item.id}
                type="button"
                onClick={() => onSeek(item.start_ms)}
                className="group absolute top-0 flex -translate-x-1/2 flex-col items-center px-1"
                style={{ left: `${left}%` }}
                aria-label={`定位到证据 ${item.id}，${formatTime(item.start_ms)}`}
                title={`${caption} · 点击定位`}
              >
                <span className="h-2 w-px bg-ink-2 group-hover:bg-ink" aria-hidden />
                <span className="size-[9px] rounded-full border-2 border-surface bg-ink transition group-hover:scale-125" aria-hidden />
                {showTickLabels ? (
                  <span className={`tnum absolute top-[13px] whitespace-nowrap text-[11px] font-semibold text-ink-2 ${labelAlign}`}>
                    {item.id}
                  </span>
                ) : null}
              </button>
            );
          })}
        </div>

        {/* Scale */}
        <div className={`tnum relative flex justify-between text-[11px] text-ink-3 ${showTickLabels ? "mt-1" : "mt-0.5"}`}>
          <span>00:00</span>
          <span>{formatTime(Math.round(duration / 2))}</span>
          <span>{formatTime(endMs)}</span>
        </div>
      </div>

      <div className="mt-2">
        {seekDisabled ? (
          <LimitNote>
            {isDemo
              ? "合成场景未关联原视频，时间位置仅用于说明定位结构，无法回看片段。"
              : "当前记录没有关联原视频，时间位置仅作参考，无法回看片段。"}
          </LimitNote>
        ) : (
          <LimitNote>点击刻度可在播放器中跳到对应位置；时间由后端按毫秒计算。</LimitNote>
        )}
      </div>
    </div>
  );
}
