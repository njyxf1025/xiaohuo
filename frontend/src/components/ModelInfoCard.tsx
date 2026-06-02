import {
  AlertTriangle,
  AudioLines,
  Cpu,
  Gauge,
  Layers,
  ShieldX,
  Sparkles,
  Zap,
} from "lucide-react";

const wav2lipFeatures = [
  {
    icon: Layers,
    title: "ONNX 跨平台",
    desc: "Wav2Lip 已导出为 ONNX 格式，与训练框架解耦，部署轻量；前置 onnxruntime-directml 即可运行。",
  },
  {
    icon: Zap,
    title: "DirectML 闪电推理",
    desc: "强制 DmlExecutionProvider，AMD / NVIDIA / Intel GPU 自动适配；单段 10s 内出片。",
  },
  {
    icon: AudioLines,
    title: "人声分离 + 伴奏重混",
    desc: "Spleeter / UVR5 等 ONNX 分离模型在 DirectML 上跑人声/伴奏分离，纯人声驱动唇形，伴奏重混，告别口型抖动。",
  },
  {
    icon: ShieldX,
    title: "CPU 降级已禁用",
    desc: "DirectML 不可用时立即报错 503，绝不静默回退到 CPU（CPU 推理太慢，无法使用）。",
  },
];

const musetalkFeatures = [
  {
    icon: Sparkles,
    title: "UNet 扩散细节",
    desc: "MuseTalk 走 PyTorch + torch-directml 上的扩散 UNet 路径，唇形与表情细节显著优于 Wav2Lip。",
  },
  {
    icon: Gauge,
    title: "算力要求更高",
    desc: "需要 1–4GB 权重 + torch-directml；单段生成时间 30s–数分钟，建议仅在需要电影级细节时使用。",
  },
  {
    icon: Cpu,
    title: "DirectML 严格策略",
    desc: "与 Wav2Lip 共用同一套 DirectML 严苛策略：可用即推理，不可用立刻返回 503，不走 CPU。",
  },
  {
    icon: Layers,
    title: "Step-2 路线",
    desc: "当前为骨架阶段，路由 /api/v1/generation/musetalk 已就绪，等待推理图实现后再开放真实生成。",
  },
];

export default function ModelInfoCard() {
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <ModelColumn
        accent="brand"
        title="Wav2Lip-ONNX"
        subtitle="ONNX Runtime + DirectML（强制）"
        badge="默认 · 闪电生成"
        features={wav2lipFeatures}
      />
      <ModelColumn
        accent="amber"
        title="MuseTalk"
        subtitle="PyTorch + torch-directml"
        badge="Step-2 路线"
        features={musetalkFeatures}
      />

      <div className="lg:col-span-2 rounded-2xl border border-rose-500/30 bg-rose-500/5 p-3 text-xs text-rose-200/90">
        <div className="mb-1 flex items-center gap-1.5 font-semibold">
          <AlertTriangle className="h-3.5 w-3.5" />
          部署前置条件
        </div>
        两条推理路径都要求 DirectML 兼容 GPU（AMD 6700XT / NVIDIA / Intel Arc）。
        Wav2Lip 需要 <code className="rounded bg-rose-500/15 px-1 py-0.5">onnxruntime-directml</code>；
        MuseTalk 需要 <code className="rounded bg-rose-500/15 px-1 py-0.5">torch-directml</code>。
        若检测不到 DirectML 设备，对应引擎会返回 HTTP 503。
      </div>
    </div>
  );
}

function ModelColumn({
  accent,
  title,
  subtitle,
  badge,
  features,
}: {
  accent: "brand" | "amber";
  title: string;
  subtitle: string;
  badge: string;
  features: { icon: typeof Zap; title: string; desc: string }[];
}) {
  const isBrand = accent === "brand";
  return (
    <div className="card relative overflow-hidden">
      <div
        aria-hidden
        className={
          "pointer-events-none absolute -right-20 -top-20 h-64 w-64 rounded-full blur-3xl " +
          (isBrand ? "bg-brand-500/10" : "bg-amber-500/10")
        }
      />
      <div className="relative space-y-5">
        <div className="flex items-center gap-3">
          <div
            className={
              "flex h-11 w-11 items-center justify-center rounded-xl text-white shadow-glow " +
              (isBrand
                ? "bg-gradient-to-br from-brand-500 to-brand-700"
                : "bg-gradient-to-br from-amber-500 to-amber-700")
            }
          >
            <Sparkles className="h-5 w-5" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-white">{title}</h3>
            <p className="text-xs text-slate-400">{subtitle}</p>
          </div>
          <span
            className={
              "ml-auto rounded-full px-3 py-1 text-xs font-semibold ring-1 " +
              (isBrand
                ? "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30"
                : "bg-amber-500/15 text-amber-300 ring-amber-500/30")
            }
          >
            {badge}
          </span>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {features.map(({ icon: Icon, title, desc }) => (
            <div
              key={title}
              className={
                "rounded-xl border bg-slate-900/40 p-4 transition " +
                (isBrand
                  ? "border-slate-800 hover:border-brand-500/40"
                  : "border-slate-800 hover:border-amber-500/40")
              }
            >
              <div className="mb-2 flex items-center gap-2">
                <span
                  className={
                    "flex h-7 w-7 items-center justify-center rounded-lg " +
                    (isBrand
                      ? "bg-brand-500/15 text-brand-300"
                      : "bg-amber-500/15 text-amber-300")
                  }
                >
                  <Icon className="h-4 w-4" />
                </span>
                <span className="text-sm font-semibold text-slate-100">
                  {title}
                </span>
              </div>
              <p className="text-xs leading-relaxed text-slate-400">{desc}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
