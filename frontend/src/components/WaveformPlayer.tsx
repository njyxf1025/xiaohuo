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
  const audioRef = useRef<HTMLAudioElement | null>(null);
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

  useEffect(() => {
    setRange(initial);
  }, [initial.start, initial.end, musicId]);

  // Wavesurfer is used ONLY as a static waveform renderer. We never pass
  // `url` so it never issues a fetch (the trae preview proxy was killing
  // those requests with ERR_ABORTED, leaving the UI stuck on "波形加载中…").
  // Audio playback is driven by a separate, fully-controlled <audio>
  // element below — if the audio fetch fails the user can still drag the
  // selection range and the waveform stays visible.
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

  // Drive audio with a plain <audio> element. We give it the download URL
  // directly and only swap to the live element after a successful load.
  // When the network blocks the audio (404 / 503 / abort) we mark it
  // "unavailable" and the play buttons become disabled — no more red
  // console errors.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const audio = new Audio();
    audio.preload = "metadata";
    audio.crossOrigin = "anonymous";
    audioRef.current = audio;
    setAudioStatus("loading");

    const onLoadedMetadata = () => {
      const realDur = audio.duration;
      if (realDur > 0 && Number.isFinite(realDur) && Math.abs(realDur - safeDuration) > 0.5) {
        setRange((prev) => {
          const scale = realDur / safeDuration;
          return {
            start: prev.start * scale,
            end: Math.min(realDur, prev.end * scale),
          };
        });
      }
      setAudioStatus("ready");
    };
    const onTimeUpdate = () => {
      setPosition(audio.currentTime);
      if (audio.currentTime > range.end) {
        audio.pause();
        audio.currentTime = range.start;
        setIsPlaying(false);
      }
    };
    const onPlay = () => setIsPlaying(true);
    const onPause = () => setIsPlaying(false);
    const onEnded = () => setIsPlaying(false);
    const onError = () => {
      console.warn("WaveformPlayer: <audio> error, switching to peaks-only mode.");
      setAudioStatus("unavailable");
      setIsPlaying(false);
    };

    audio.addEventListener("loadedmetadata", onLoadedMetadata);
    audio.addEventListener("timeupdate", onTimeUpdate);
    audio.addEventListener("play", onPlay);
    audio.addEventListener("pause", onPause);
    audio.addEventListener("ended", onEnded);
    audio.addEventListener("error", onError);

    audio.src = getMusicDownloadUrl(musicId);
    audio.load();

    return () => {
      audio.removeEventListener("loadedmetadata", onLoadedMetadata);
      audio.removeEventListener("timeupdate", onTimeUpdate);
      audio.removeEventListener("play", onPlay);
      audio.removeEventListener("pause", onPause);
      audio.removeEventListener("ended", onEnded);
      audio.removeEventListener("error", onError);
      try {
        audio.pause();
      } catch {
        /* noop */
      }
      audio.removeAttribute("src");
      audio.load();
      audioRef.current = null;
    };
  }, [musicId, safeDuration, range.end, range.start]);

  useEffect(() => {
    onChange?.(range);
  }, [range, onChange]);

  const playSegment = () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (audioStatus !== "ready") return;
    try {
      audio.currentTime = range.start;
      const p = audio.play();
      if (p && typeof p.catch === "function") p.catch(() => setIsPlaying(false));
    } catch (e) {
      console.warn(e);
    }
  };

  const togglePlay = () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (audioStatus !== "ready") return;
    if (isPlaying) {
      audio.pause();
    } else {
      const p = audio.play();
      if (p && typeof p.catch === "function") p.catch(() => setIsPlaying(false));
    }
  };

  const resetRange = () => {
    setRange(initial);
  };

  const audioPlayable = audioStatus === "ready" && safeDuration > 0;

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
          disabled={!audioPlayable}
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
          disabled={!audioPlayable}
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
