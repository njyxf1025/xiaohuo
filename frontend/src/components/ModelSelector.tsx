import { useEffect, useState } from "react";
import { CheckCircle2, Loader2, Sparkles, Zap, AlertTriangle, Cpu } from "lucide-react";

import { getEnginesStatus, type EnginesStatusResponse, type GenerationModel } from "../api/generation";
import { cn } from "../lib/utils";

interface ModelOption {
  id: GenerationModel;
  title: string;
  subtitle: string;
  speedNote: string;
  qualityNote: string;
  provider: string;
  highlights: { icon: typeof Zap; title: string; desc: string }[];
  badge: { label: string; tone: "emerald" | "amber" | "slate" };
  icon: typeof Sparkles;
}

const WAV2LIP_HIGHLIGHTS: ModelOption["highlights"] = [
  {
    icon: Zap,
    title: "闪电生成",
    desc: "ONNX Runtime + DirectML 走图极简，单段 10s 内出片，适合快速迭代。",
  },
  {
    icon: Cpu,
    title: "AMD 6700XT 友好",
    desc: "DmlExecutionProvider 自动覆盖 AMD / NVIDIA / Intel GPU，CPU 降级已禁用。",
  },
];

const MUSETALK_HIGHLIGHTS: ModelOption["highlights"] = [
  {
    icon: Sparkles,
    title: "高清细节",
    desc: "PyTorch + DirectML 上的 UNet 扩散路径，唇形与表情细节显著优于 Wav2Lip。",
  },
  {
    icon: Cpu,
    title: "算力要求高",
    desc: "需要 torch-directml 与 1–4GB 权重，单段生成时间 30s–数分钟。",
  },
];

const MODELS: ModelOption[] = [
  {
    id: "wav2lip",
    title: "闪电生成",
    subtitle: "Wav2Lip-ONNX · DirectML",
    speedNote: "≈10 秒 / 段",
    qualityNote: "标准画质",
    provider: "onnxruntime-directml",
    highlights: WAV2LIP_HIGHLIGHTS,
    badge: { label: "推荐", tone: "emerald" },
    icon: Zap,
  },
  {
    id: "musetalk",
    title: "高清细节",
    subtitle: "MuseTalk · torch-directml",
    speedNote: "≈30s–数分钟 / 段",
    qualityNote: "电影级细节",
    provider: "torch-directml",
    highlights: MUSETALK_HIGHLIGHTS,
    badge: { label: "Step-2 路线", tone: "amber" },
    icon: Sparkles,
  },
];

const BADGE_TONE: Record<ModelOption["badge"]["tone"], string> = {
  emerald: "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30",
  amber: "bg-amber-500/15 text-amber-300 ring-amber-500/30",
  slate: "bg-slate-700 text-slate-300 ring-slate-600",
};

interface ModelSelectorProps {
  value: GenerationModel;
  onChange: (model: GenerationModel) => void;
  disabled?: boolean;
}

export default function ModelSelector({ value, onChange, disabled }: ModelSelectorProps) {
  const [status, setStatus] = useState<EnginesStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await getEnginesStatus();
        if (!cancelled) {
          setStatus(res);
        }
      } catch (e: unknown) {
        if (!cancelled) {
          const msg = e instanceof Error ? e.message : "无法读取引擎状态";
          setError(msg);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-sm font-semibold text-slate-200">选择推理模型</div>
        {loading && <Loader2 className="h-3.5 w-3.5 animate-spin text-slate-400" />}
        {error && (
          <span className="text-xs text-rose-300">引擎状态读取失败：{error}</span>
        )}
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {MODELS.map((m) => {
          const Icon = m.icon;
          const slot = status?.engines[m.id];
          const dmlReady = slot?.directml_ready ?? false;
          const isSelected = value === m.id;
          const blocked = m.id === "musetalk" && !dmlReady;
          return (
            <button
              key={m.id}
              type="button"
              onClick={() => onChange(m.id)}
              disabled={disabled}
              className={cn(
                "group relative flex w-full flex-col gap-3 rounded-2xl border p-4 text-left transition",
                isSelected
                  ? "border-brand-500/60 bg-brand-500/10 shadow-glow"
                  : "border-slate-800 bg-slate-900/40 hover:border-brand-500/40",
                disabled && "cursor-not-allowed opacity-60",
              )}
            >
              <div className="flex items-start gap-3">
                <div
                  aria-hidden="true"
                  className={cn(
                    "flex h-10 w-10 shrink-0 items-center justify-center rounded-xl",
                    isSelected
                      ? "bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-glow"
                      : "bg-slate-800 text-slate-300",
                  )}
                >
                  <Icon className="h-5 w-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-base font-bold text-white">{m.title}</span>
                    <span
                      className={cn(
                        "rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1",
                        BADGE_TONE[m.badge.tone],
                      )}
                    >
                      {m.badge.label}
                    </span>
                    {isSelected && (
                      <CheckCircle2 aria-hidden="true" className="h-4 w-4 text-brand-300" />
                    )}
                  </div>
                  <div className="mt-0.5 text-xs text-slate-400">{m.subtitle}</div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-400">
                <div>
                  <div className="text-slate-500">推理速度</div>
                  <div className="font-medium text-slate-200">{m.speedNote}</div>
                </div>
                <div>
                  <div className="text-slate-500">画面质量</div>
                  <div className="font-medium text-slate-200">{m.qualityNote}</div>
                </div>
              </div>

              <div className="space-y-2">
                {m.highlights.map(({ icon: HIcon, title, desc }) => (
                  <div key={title} className="flex items-start gap-2 rounded-lg border border-slate-800/80 bg-slate-950/30 p-2">
                    <span
                      aria-hidden="true"
                      className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-brand-500/15 text-brand-300"
                    >
                      <HIcon className="h-3 w-3" />
                    </span>
                    <div className="min-w-0">
                      <div className="text-xs font-semibold text-slate-100">
                        {title}
                      </div>
                      <div className="text-[11px] leading-relaxed text-slate-400">
                        {desc}
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              <div className="flex flex-wrap items-center gap-2 text-[10px] text-slate-500">
                <span className="rounded-md bg-slate-800/60 px-1.5 py-0.5 font-mono">
                  {m.provider}
                </span>
                {slot ? (
                  dmlReady ? (
                    <span className="rounded-md bg-emerald-500/10 px-1.5 py-0.5 text-emerald-300 ring-1 ring-emerald-500/30">
                      DirectML ✓
                    </span>
                  ) : (
                    <span className="rounded-md bg-rose-500/10 px-1.5 py-0.5 text-rose-300 ring-1 ring-rose-500/30">
                      DirectML ✗
                    </span>
                  )
                ) : null}
              </div>

              {blocked && (
                <div
                  role="status"
                  className="rounded-md border border-amber-500/30 bg-amber-500/5 p-2 text-[11px] text-amber-200/90"
                >
                  <div className="mb-1 flex items-center gap-1 font-semibold">
                    <AlertTriangle aria-hidden="true" className="h-3 w-3" />
                    torch-directml 未就绪
                  </div>
                  当前主机仅启用了 onnxruntime-directml 路径；MuseTalk 在
                  PyTorch+DirectML 上运行，提交后会被 503 拒绝。
                </div>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
