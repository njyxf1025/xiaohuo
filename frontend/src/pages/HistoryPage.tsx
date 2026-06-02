import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Download, Loader2, RefreshCw, Sparkles } from "lucide-react";
import { toast } from "sonner";

import {
  deleteTask,
  getTaskDownloadUrl,
  getTaskThumbUrl,
  listTasks,
  type TaskStatusResponse,
} from "../api/generation";
import { cn } from "../lib/utils";

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-slate-500/15 text-slate-300 ring-slate-500/30",
  running: "bg-amber-500/15 text-amber-200 ring-amber-500/30",
  success: "bg-emerald-500/15 text-emerald-200 ring-emerald-500/30",
  failed: "bg-rose-500/15 text-rose-200 ring-rose-500/30",
  cancelled: "bg-slate-500/15 text-slate-300 ring-slate-500/30",
};

const STATUS_LABELS: Record<string, string> = {
  pending: "等待中",
  running: "进行中",
  success: "已完成",
  failed: "失败",
  cancelled: "已取消",
};

export default function HistoryPage() {
  const [tasks, setTasks] = useState<TaskStatusResponse[]>([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const res = await listTasks(50);
      setTasks(res.tasks || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const onDelete = async (taskId: string) => {
    try {
      await deleteTask(taskId);
      toast.success("已删除任务");
      setTasks((prev) => prev.filter((t) => t.task_id !== taskId));
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="space-y-8">
      <header className="flex flex-col items-start justify-between gap-3 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-white">
            历史记录
          </h1>
          <p className="text-sm text-slate-400">
            查看过往生成任务，下载结果或清理记录。
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={load}
            className="btn-ghost"
            disabled={loading}
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            刷新
          </button>
          <Link to="/generate" className="btn-primary">
            <Sparkles className="h-4 w-4" />
            创作新视频
          </Link>
        </div>
      </header>

      {loading && tasks.length === 0 ? (
        <div className="card flex items-center justify-center gap-2 py-16 text-slate-400">
          <Loader2 className="h-4 w-4 animate-spin" />
          加载历史记录…
        </div>
      ) : tasks.length === 0 ? (
        <div className="card flex flex-col items-center justify-center gap-3 py-16 text-slate-400">
          <p>暂无历史任务</p>
          <Link to="/generate" className="btn-primary">
            前往创作
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {tasks.map((t) => {
            const status = t.status;
            const ready = status === "success";
            return (
              <div key={t.task_id} className="card overflow-hidden p-0">
                <div className="relative aspect-video w-full overflow-hidden bg-slate-950">
                  {ready ? (
                    <img
                      src={getTaskThumbUrl(t.task_id)}
                      alt={`任务 ${t.task_id} 的生成结果缩略图`}
                      className="h-full w-full object-cover"
                      loading="lazy"
                      decoding="async"
                      onError={(e) => {
                        (e.currentTarget as HTMLImageElement).style.opacity =
                          "0.15";
                      }}
                    />
                  ) : (
                    <div className="flex h-full w-full items-center justify-center text-slate-600">
                      {status === "running" || status === "pending" ? (
                        <Loader2 className="h-6 w-6 animate-spin" />
                      ) : (
                        <span className="text-3xl">—</span>
                      )}
                    </div>
                  )}
                  <span
                    className={cn(
                      "absolute left-3 top-3 rounded-full px-2.5 py-1 text-[11px] font-semibold ring-1",
                      STATUS_STYLES[status] || STATUS_STYLES.pending,
                    )}
                  >
                    {STATUS_LABELS[status] || status}
                  </span>
                </div>
                <div className="space-y-2 p-4">
                  <p className="truncate font-mono text-xs text-slate-400">
                    {t.task_id}
                  </p>
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
                    <div
                      className={cn(
                        "h-full rounded-full",
                        ready
                          ? "bg-emerald-400"
                          : status === "failed"
                            ? "bg-rose-400"
                            : "bg-gradient-to-r from-brand-500 to-brand-300",
                      )}
                      style={{ width: `${Math.max(0, Math.min(100, t.progress || 0))}%` }}
                    />
                  </div>
                  <p className="line-clamp-1 text-xs text-slate-400">
                    阶段：{t.stage || "-"} · {t.progress?.toFixed?.(1) ?? t.progress}%
                  </p>
                  <div className="flex items-center justify-between pt-1">
                    {ready ? (
                      <a
                        href={getTaskDownloadUrl(t.task_id)}
                        target="_blank"
                        rel="noreferrer"
                        className="btn-primary px-3 py-1.5 text-xs"
                      >
                        <Download className="h-3.5 w-3.5" />
                        下载
                      </a>
                    ) : (
                      <span className="text-xs text-slate-500">
                        {status === "running" || status === "pending"
                          ? "正在生成…"
                          : status === "failed"
                            ? t.error || "生成失败"
                            : "未生成"}
                      </span>
                    )}
                    <button
                      type="button"
                      onClick={() => onDelete(t.task_id)}
                      className="text-xs text-slate-500 transition hover:text-rose-300"
                    >
                      删除
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
