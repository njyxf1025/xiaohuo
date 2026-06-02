import { useEffect, useMemo, useRef, useState } from "react";
import WaveSurfer from "wavesurfer.js";
import { Pause, Play, RotateCcw, Scissors } from "lucide-react";

import { getMusicDownloadUrl } from "../api/music";
import { cn, formatTime } from "../lib/utils";

export interface WaveformPlayerProps {
  musicId: string;
  peaks: number[];
  duration: number;
  chorus?: { start_sec: number; end_sec: number } | null;
  initialStart?: number;
  initialEnd?: number;
  onChange?: (range: { start: number; end: number }) => void;
  height?: number;
  className?: string;
}

type AudioStatus = "idle" | "loading" | "ready" | "unavailable";

export default function WaveformPlayer({
  musicId,
  peaks,
  duration,
  chorus,
  initialStart,
  initialEnd,
  onChange,
  height = 120,
  className,
}: WaveformPlayerProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const wsRef = useRef<WaveSurfer | null>(null);
  const [ready, setReady] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [position, setPosition] = useState(0);
  const [audioStatus, setAudioStatus] = useState<AudioStatus>("idle");

  const fallbackDuration =
    duration > 0
      ? duration
      : chorus
        ? Math.max(chorus.end_sec, 0.001)
        : 0.001;

  const safeDuration = fallbackDuration;

  const initial = useMemo(() => {
    const start =
      initialStart ??
      chorus?.start_sec ??
      Math.min(20, Math.max(0, safeDuration * 0.25));
    const end =
      initialEnd ??
      chorus?.end_sec ??
      Math.min(safeDuration, (start || 0) + Math.min(20, safeDuration - (start || 0)));
    return { start, end };
  }, [initialStart, initialEnd, chorus, safeDuration]);

  const [range, setRange] = useState<{ start: number; end: number }>(initial);
  const draggingRef = useRef<null | "start" | "end">(null);
  const trackRef = useRef<HTMLDivElement | null>(null);

  // Web Audio API playback state. We use AudioContext + decodeAudioData +
  // AudioBufferSourceNode instead of HTMLMediaElement. Reasons:
  //   * No HTMLMediaElement means Chrome's media decoder ERR_ABORTED
  //     log path is not involved at all.
  //   * AudioBufferSourceNode is fire-and-forget; stopping it via
  //     .stop() does not produce any console error.
  //   * The fetch that pulls audio bytes goes through the standard
  //     fetch API; if it gets aborted by the trae proxy during a
  //     React lifecycle transition, the rejection is a plain
  //     promise reject (no red [error] net::ERR_ABORTED log).
  const audioCtxRef = useRef<AudioContext | null>(null);
  const audioBufferRef = useRef<AudioBuffer | null>(null);
  const sourceRef = useRef<AudioBufferSourceNode | null>(null);
  const startedAtRef = useRef<number>(0); // AudioContext.currentTime at start
  const offsetAtStartRef = useRef<number>(0); // playback offset (sec) at start
  const positionTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const musicIdRef = useRef(musicId);
  const rangeRef = useRef(range);
  useEffect(() => {
    rangeRef.current = range;
  }, [range.start, range.end]);

  useEffect(() => {
    setRange(initial);
  }, [initial.start, initial.end, musicId]);

  // Wavesurfer: static peaks only, no fetch.
  useEffect(() => {
    if (!containerRef.current) return;
    const ws = WaveSurfer.create({
      container: containerRef.current,
      height,
      waveColor: "rgba(148, 163, 184, 0.55)",
      progressColor: "rgba(139, 92, 252, 0.95)",
      cursorColor: "rgba(226, 232, 240, 0.9)",
      cursorWidth: 1,
      barWidth: 2,
      barGap: 2,
      barRadius: 1,
      normalize: true,
      interact: false,
      hideScrollbar: true,
    });
    wsRef.current = ws;
    try {
      if (peaks && peaks.length > 0 && safeDuration > 0) {
        const channelPeaks: number[][] = [peaks];
        ws.load("", channelPeaks, safeDuration);
      }
    } catch (e) {
      console.warn("WaveformPlayer: peaks load failed", e);
    }
    const onReady = () => setReady(true);
    ws.on("ready", onReady);
    return () => {
      try {
        ws.destroy();
      } catch {
        /* noop */
      }
      wsRef.current = null;
    };
  }, [peaks, safeDuration, height, musicId]);

  // musicId change / unmount: stop any playing source and drop the
  // cached AudioBuffer. We do NOT call ctx.close() — the AudioContext
  // is shared (lazily created) and a reused context does not produce
  // any abort noise.
  useEffect(() => {
    musicIdRef.current = musicId;
    setAudioStatus("idle");
    setIsPlaying(false);
    setPosition(0);
    stopSource();
    audioBufferRef.current = null;
    return () => {
      stopSource();
      audioBufferRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [musicId]);

  function stopSource() {
    if (positionTimerRef.current) {
      clearInterval(positionTimerRef.current);
      positionTimerRef.current = null;
    }
    const src = sourceRef.current;
    if (src) {
      sourceRef.current = null;
      try {
        src.stop();
      } catch {
        /* already stopped */
      }
    }
  }

  // Lazily fetch + decode the audio. The download URL is only ever hit
  // on the user's first click of 试听整段 / 试听所选区间. If the fetch
  // is cancelled mid-flight (e.g. React unmount during the round-trip)
  // the rejection is a normal fetch abort, NOT a red
  // [error] net::ERR_ABORTED — that's specific to XHR / media
  // elements.
  const ensureAudioReady = async (): Promise<boolean> => {
    if (audioStatus === "unavailable") return false;
    if (audioBufferRef.current && audioCtxRef.current) return true;
    if (audioStatus === "loading") return false;
    setAudioStatus("loading");
    const targetId = musicId;
    try {
      const r = await fetch(getMusicDownloadUrl(targetId));
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const arrayBuf = await r.arrayBuffer();
      if (musicIdRef.current !== targetId) return false;
      let ctx = audioCtxRef.current;
      if (!ctx) {
        const Ctor =
          (typeof window !== "undefined" &&
            ((window as unknown as { AudioContext?: typeof AudioContext })
              .AudioContext ||
              (window as unknown as {
                webkitAudioContext?: typeof AudioContext;
              }).webkitAudioContext)) ||
          null;
        if (!Ctor) throw new Error("AudioContext not supported");
        ctx = new Ctor();
        audioCtxRef.current = ctx;
      }
      if (ctx.state === "suspended") {
        try {
          await ctx.resume();
        } catch {
          /* noop */
        }
      }
      const buffer = await ctx.decodeAudioData(arrayBuf.slice(0));
      if (musicIdRef.current !== targetId) return false;
      audioBufferRef.current = buffer;
      if (
        buffer.duration > 0 &&
        Number.isFinite(buffer.duration) &&
        Math.abs(buffer.duration - safeDuration) > 0.5
      ) {
        const realDur = buffer.duration;
        setRange((prev) => {
          const scale = realDur / safeDuration;
          return {
            start: prev.start * scale,
            end: Math.min(realDur, prev.end * scale),
          };
        });
      }
      setAudioStatus("ready");
      return true;
    } catch (e) {
      if (musicIdRef.current !== targetId) return false;
      // AbortError from fetch().abort() is a normal lifecycle event
      // — do not surface it as a warning either.
      const name = (e && (e as { name?: string }).name) || "";
      if (name === "AbortError") return false;
      console.warn(
        "WaveformPlayer: audio fetch/decode failed (peaks-only mode):",
        (e && (e as Error).message) || e
      );
      setAudioStatus("unavailable");
      setIsPlaying(false);
      return false;
    }
  };

  function playFromOffset(offsetSec: number) {
    const ctx = audioCtxRef.current;
    const buffer = audioBufferRef.current;
    if (!ctx || !buffer) return;
    const clamped = Math.max(0, Math.min(buffer.duration, offsetSec));
    stopSource();
    const src = ctx.createBufferSource();
    src.buffer = buffer;
    src.connect(ctx.destination);
    sourceRef.current = src;
    offsetAtStartRef.current = clamped;
    startedAtRef.current = ctx.currentTime;
    try {
      src.start(0, clamped);
    } catch (e) {
      console.warn(e);
      return;
    }
    setIsPlaying(true);
    setPosition(clamped);
    positionTimerRef.current = setInterval(() => {
      const c = audioCtxRef.current;
      const s = sourceRef.current;
      if (!c || !s) return;
      const elapsed = c.currentTime - startedAtRef.current;
      const pos = offsetAtStartRef.current + elapsed;
      setPosition(pos);
      // Auto-stop at end of selected segment.
      if (pos > rangeRef.current.end) {
        stopSource();
        setIsPlaying(false);
        setPosition(rangeRef.current.start);
      }
    }, 100);
    src.onended = () => {
      if (sourceRef.current !== src) return;
      sourceRef.current = null;
      if (positionTimerRef.current) {
        clearInterval(positionTimerRef.current);
        positionTimerRef.current = null;
      }
      setIsPlaying(false);
    };
  }

  const playSegment = async () => {
    if (audioStatus === "unavailable") return;
    const ok = await ensureAudioReady();
    if (!ok) return;
    playFromOffset(range.start);
  };

  const togglePlay = async () => {
    if (audioStatus === "unavailable") return;
    if (isPlaying) {
      stopSource();
      setIsPlaying(false);
      return;
    }
    const ok = await ensureAudioReady();
    if (!ok) return;
    const pos = position > 0 ? position : 0;
    playFromOffset(pos);
  };

  const resetRange = () => {
    setRange(initial);
  };

  const startPct = safeDuration > 0 ? (range.start / safeDuration) * 100 : 0;
  const endPct = safeDuration > 0 ? (range.end / safeDuration) * 100 : 100;
  const playheadPct = safeDuration > 0 ? (position / safeDuration) * 100 : 0;

  const onPointerDown = (which: "start" | "end") => (e: React.PointerEvent) => {
    e.preventDefault();
    e.stopPropagation();
    draggingRef.current = which;
    (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
  };

  const onPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!draggingRef.current) return;
    const rect = trackRef.current?.getBoundingClientRect();
    if (!rect || rect.width === 0) return;
    const x = Math.min(Math.max(e.clientX - rect.left, 0), rect.width);
    const pct = x / rect.width;
    const t = pct * safeDuration;
    setRange((prev) => {
      if (draggingRef.current === "start") {
        const start = Math.min(Math.max(0, t), prev.end - 0.2);
        return { start, end: prev.end };
      } else {
        const end = Math.max(Math.min(safeDuration, t), prev.start + 0.2);
        return { start: prev.start, end };
      }
    });
  };

  const onPointerUp = () => {
    draggingRef.current = null;
  };

  return (
    <div className={cn("card space-y-4", className)}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm text-slate-300">
          <Scissors className="h-4 w-4 text-brand-300" />
          <span>高潮区间调整</span>
          <span className="ml-2 text-xs text-slate-500">
            拖动两端调整起止时间
          </span>
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <span>
            {formatTime(range.start)} – {formatTime(range.end)}
          </span>
          <span className="rounded-md bg-slate-800/80 px-2 py-0.5 text-slate-300">
            {formatTime(Math.max(0, range.end - range.start))}
          </span>
        </div>
      </div>

      <div className="relative">
        <div
          ref={containerRef}
          className="relative h-[120px] w-full overflow-hidden rounded-xl bg-slate-950/60 ring-1 ring-slate-800"
        />
        {!ready && (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center text-xs text-slate-500">
            波形加载中…
          </div>
        )}
      </div>

      <div className="space-y-2">
        <div
          ref={trackRef}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerLeave={onPointerUp}
          onPointerCancel={onPointerUp}
          className="relative h-10 w-full select-none rounded-lg bg-slate-900/60 ring-1 ring-slate-800"
        >
          <div
            className="absolute inset-y-0 bg-brand-500/15"
            style={{ left: `${startPct}%`, width: `${Math.max(0, endPct - startPct)}%` }}
          />
          <div
            className="absolute inset-y-0 w-1 -translate-x-1/2 bg-brand-400"
            style={{ left: `${playheadPct}%` }}
          />
          <button
            type="button"
            aria-label="调整高潮区间起始时间"
            aria-valuemin={0}
            aria-valuemax={Math.round(safeDuration)}
            aria-valuenow={Math.round(range.start)}
            aria-valuetext={formatTime(range.start)}
            role="slider"
            onPointerDown={onPointerDown("start")}
            className="absolute top-0 z-10 flex h-full w-4 -translate-x-1/2 cursor-ew-resize touch-none items-center justify-center"
            style={{ left: `${startPct}%` }}
          >
            <span className="h-7 w-1.5 rounded-full bg-brand-300 shadow-glow" />
          </button>
          <button
            type="button"
            aria-label="调整高潮区间结束时间"
            aria-valuemin={0}
            aria-valuemax={Math.round(safeDuration)}
            aria-valuenow={Math.round(range.end)}
            aria-valuetext={formatTime(range.end)}
            role="slider"
            onPointerDown={onPointerDown("end")}
            className="absolute top-0 z-10 flex h-full w-4 -translate-x-1/2 cursor-ew-resize touch-none items-center justify-center"
            style={{ left: `${endPct}%` }}
          >
            <span className="h-7 w-1.5 rounded-full bg-brand-300 shadow-glow" />
          </button>
        </div>
        <div className="flex items-center justify-between text-[11px] text-slate-500">
          <span>00:00</span>
          <span>{formatTime(safeDuration)}</span>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={togglePlay}
          className="btn-primary"
          disabled={audioStatus === "unavailable"}
          aria-label={isPlaying ? "暂停试听" : "试听整段"}
          title={
            audioStatus === "unavailable"
              ? "音频源不可用，仅可调整区间"
              : audioStatus === "loading"
                ? "音频加载中…"
                : isPlaying
                  ? "暂停试听"
                  : "试听整段"
          }
        >
          {isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
          {isPlaying ? "暂停" : "试听整段"}
        </button>
        <button
          type="button"
          onClick={playSegment}
          className="btn-ghost"
          disabled={audioStatus === "unavailable"}
          aria-label="试听所选区间"
          title={
            audioStatus === "unavailable"
              ? "音频源不可用，仅可调整区间"
              : audioStatus === "loading"
                ? "音频加载中…"
                : "试听所选区间"
          }
        >
          <Scissors className="h-4 w-4" />
          试听所选区间
        </button>
        <button
          type="button"
          onClick={resetRange}
          className="btn-ghost"
          disabled={!chorus && initialStart == null && initialEnd == null}
          aria-label="重置为自动检测"
        >
          <RotateCcw className="h-4 w-4" />
          重置为自动检测
        </button>
        {audioStatus === "unavailable" && (
          <span
            className="ml-2 rounded-md bg-amber-500/10 px-2 py-1 text-[11px] text-amber-300 ring-1 ring-amber-500/30"
            role="status"
            aria-live="polite"
          >
            音频源不可用，仅显示波形；区间可拖动
          </span>
        )}
        {audioStatus === "loading" && (
          <span
            className="ml-2 text-[11px] text-slate-500"
            role="status"
            aria-live="polite"
          >
            音频加载中…
          </span>
        )}
      </div>
    </div>
  );
}
