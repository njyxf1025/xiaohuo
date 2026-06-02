import { useEffect, useMemo, useRef, useState } from "react";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";

import { getTask, type TaskStatusResponse } from "../api/generation";
import { cn } from "../lib/utils";

interface ProgressPanelProps {
  taskId: string;
  onComplete?: (status: TaskStatusResponse) => void;
  onError?: (status: TaskStatusResponse) => void;
}

const STAGES: { key: string; label: string }[] = [
  { key: "uploaded", label: "上传完成" },
  { key: "chorus_detected", label: "高潮检测完成" },
  { key: "sliced", label: "音频截取完成" },
  { key: "vocal_separation", label: "人声分离（DirectML）" },
  { key: "started", label: "开始生成" },
  { key: "session_loaded", label: "加载推理会话" },
  { key: "mel_extracted", label: "提取音频特征" },
  { key: "lipsync_inference", label: "生成唇形" },
  { key: "video_composed", label: "合成视频" },
  { key: "done", label: "完成" },
];

function mapStageToKey(stage: string | undefined): string {
  if (!stage) return "";
  const s = stage.toLowerCase();
  if (s.includes("vocal") || s.includes("separ") || s.includes("denois")) {
    return "vocal_separation";
  }
  if (s.includes("upload")) return "uploaded";
  if (s.includes("chorus")) return "chorus_detected";
  if (s.includes("slice")) return "sliced";
  if (s.includes("start")) return "started";
  if (s.includes("session") || s.includes("load") || s.includes("init")) {
    return "session_loaded";
  }
  if (s.includes("mel") || s.includes("audio_feature")) {
    return "mel_extracted";
  }
  if (s.includes("lipsync") || s.includes("infer") || s.includes("frame")) {
    return "lipsync_inference";
  }
  if (s.includes("video") || s.includes("compose") || s.includes("mux") || s.includes("accompaniment")) {
    return "video_composed";
  }
  if (s.includes("done") || s.includes("success") || s.includes("finish")) {
    return "done";
  }
  return s;
}

export default function ProgressPanel({
  taskId,
  onComplete,
  onError,
}: ProgressPanelProps) {
  const [status, setStatus] = useState<TaskStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const completedRef = useRef(false);
  const erroredRef = useRef(false);

  useEffect(() => {
    completedRef.current = false;
    erroredRef.current = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let cancelled = false;
    const controller = new AbortController();

    const poll = async () => {
      try {
        const data = await getTask(taskId, { signal: controller.signal });
        if (cancelled) return;
        setStatus(data);
        if (data.status === "success" && !completedRef.current) {
          completedRef.current = true;
          onComplete?.(data);
          return;
        }
        if (data.status === "failed" && !erroredRef.current) {
          erroredRef.current = true;
          setError(data.error || data.message || "生成失败");
          onError?.(data);
          return;
        }
        if (data.status === "cancelled") {
          setError("任务已取消");
          return;
        }
        timer = setTimeout(poll, 1000);
      } catch (e: any) {
        if (cancelled) return;
        // Swallow lifecycle cancel (ERR_CANCELED / CanceledError) so
        // unmount / HMR / tab-switch doesn't print a red
        // [error] net::ERR_ABORTED in the console.
        if (
          e?.code === "ERR_CANCELED" ||
          e?.name === "CanceledError" ||
          /canceled|aborted/i.test(e?.message || "")
        ) {
          return;
        }
        setError(e?.message || "查询任务状态失败");
        timer = setTimeout(poll, 2000);
      }
    };

    poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
      controller.abort();
    };
  }, [taskId, onComplete, onError]);

  const percent = useMemo(() => {
    if (!status) return 0;
    if (status.status === "success") return 100;
    if (status.status === "failed" || status.status === "cancelled") {
      return Math.max(0, Math.min(100, status.progress || 0));
    }
    return Math.max(0, Math.min(100, status.progress || 0));
  }, [status]);

  const activeIndex = useMemo(() => {
    if (!status) return -1;
    if (status.status === "success") return STAGES.length - 1;
    if (status.status === "failed" || status.status === "cancelled") {
      const key = mapStageToKey(status.stage);
      const idx = STAGES.findIndex((s) => s.key === key);
      return idx >= 0 ? idx : 0;
    }
    const key = mapStageToKey(status.stage);
    const idx = STAGES.findIndex((s) => s.key === key);
    return idx >= 0 ? idx : 0;
  }, [status]);

  const isFailed = status?.status === "failed" || status?.status === "cancelled";

  return (
    <div className="card space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm text-slate-300">
          {isFailed ? (
            <XCircle className="h-4 w-4 text-rose-400" />
          ) : status?.status === "success" ? (
            <CheckCircle2 className="h-4 w-4 text-emerald-400" />
          ) : (
            <Loader2 className="h-4 w-4 animate-spin text-brand-300" />
          )}
          <span>
            {status?.status === "success"
              ? "生成完成"
              : isFailed
                ? "生成失败"
                : "正在生成"}
          </span>
        </div>
        <span className="font-mono text-sm text-slate-400">
          {percent.toFixed(1)}%
        </span>
      </div>

      <div className="h-3 w-full overflow-hidden rounded-full bg-slate-800">
        <div
          role="progressbar"
          aria-label="生成进度"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(percent)}
          className={cn(
            "h-full rounded-full transition-[width] duration-500 motion-reduce:transition-none",
            isFailed
              ? "bg-rose-500"
              : "bg-gradient-to-r from-brand-500 to-brand-300",
          )}
          style={{ width: `${percent}%` }}
        />
      </div>

      <ol className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {STAGES.map((s, i) => {
          const done =
            status?.status === "success" || i < activeIndex;
          const active = i === activeIndex && !isFailed && status?.status !== "success";
          return (
            <li
              key={s.key}
              className={cn(
                "flex items-center gap-2 rounded-lg border px-3 py-2 text-xs transition",
                done && "border-emerald-500/30 bg-emerald-500/5 text-emerald-200",
                active && "border-brand-500/40 bg-brand-500/10 text-brand-200",
                !done &&
                  !active &&
                  "border-slate-800 bg-slate-900/40 text-slate-500",
              )}
            >
              {done ? (
                <CheckCircle2 className="h-3.5 w-3.5" />
              ) : active ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <span className="h-2 w-2 rounded-full bg-slate-700" />
              )}
              <span>
                {i + 1}. {s.label}
              </span>
            </li>
          );
        })}
      </ol>

      {status?.message && (
        <p aria-live="polite" className="text-xs text-slate-400">
          <span className="text-slate-500">后端消息：</span>
          {status.message}
        </p>
      )}
      {error && (
        <p aria-live="assertive" className="text-xs text-rose-300">
          <span className="text-rose-400">错误：</span>
          {error}
        </p>
      )}
    </div>
  );
}
