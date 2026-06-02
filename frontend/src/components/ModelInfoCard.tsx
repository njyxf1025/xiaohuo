import { AlertTriangle, Cpu, Gauge, Layers, ShieldX, Sparkles, Zap } from "lucide-react";

const features = [
  {
    icon: Layers,
    title: "ONNX 跨平台",
    desc: "Wav2Lip 已导出为 ONNX 格式，与训练框架解耦，部署轻量。",
  },
  {
    icon: Zap,
    title: "DirectML GPU 加速",
    desc: "强制使用 DmlExecutionProvider，AMD / NVIDIA / Intel GPU 自动适配。",
  },
  {
    icon: ShieldX,
    title: "CPU 降级已禁用",
    desc: "DirectML 不可用时立即报错 503，绝不静默回退到 CPU（CPU 推理太慢，无法使用）。",
  },
  {
    icon: Gauge,
    title: "会话缓存",
    desc: "ONNX InferenceSession 单例复用，避免重复加载耗时。",
  },
];

export default function ModelInfoCard() {
  return (
    <div className="card relative overflow-hidden">
      <div
        aria-hidden
        className="pointer-events-none absolute -right-20 -top-20 h-64 w-64 rounded-full bg-brand-500/10 blur-3xl"
      />
      <div className="relative space-y-5">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 shadow-glow">
            <Sparkles className="h-5 w-5 text-white" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-white">Wav2Lip-ONNX</h3>
            <p className="text-xs text-slate-400">
              唯一推理模型 · ONNX Runtime + DirectML（强制）
            </p>
          </div>
          <span className="ml-auto rounded-full bg-emerald-500/15 px-3 py-1 text-xs font-semibold text-emerald-300 ring-1 ring-emerald-500/30">
            <Cpu className="mr-1 inline h-3.5 w-3.5" /> 单一模型
          </span>
        </div>

        <p className="text-sm leading-relaxed text-slate-300">
          本项目仅保留 Wav2Lip-ONNX 一条推理路径。原 SadTalker、LatentSync 两种
          模型已从代码、权重与调度器中彻底移除，不再提供多模型对比或切换。
          推理时强制使用 DirectML EP，自动覆盖 AMD / NVIDIA / Intel GPU；
          <span className="font-semibold text-amber-300">
            当 DirectML 不可用时系统会立即返回错误（HTTP 503
            directml_unavailable），不允许 CPU 降级
          </span>
          ，避免在无 GPU 环境下「能跑但跑不动」的用户体验。
        </p>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {features.map(({ icon: Icon, title, desc }) => (
            <div
              key={title}
              className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 transition hover:border-brand-500/40"
            >
              <div className="mb-2 flex items-center gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-500/15 text-brand-300">
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

        <div className="rounded-xl border border-rose-500/30 bg-rose-500/5 p-3 text-xs text-rose-200/90">
          <div className="mb-1 flex items-center gap-1.5 font-semibold">
            <AlertTriangle className="h-3.5 w-3.5" />
            部署前置条件
          </div>
          必须在安装了 <code className="rounded bg-rose-500/15 px-1 py-0.5">onnxruntime-directml</code> 的
          Windows 主机上运行，且需具备 DirectML 兼容 GPU（AMD 6700XT / NVIDIA /
          Intel Arc 等）。若检测不到 DirectML 设备，
          <code className="rounded bg-rose-500/15 px-1 py-0.5">/api/v1/health</code>{" "}
          会返回 503。
        </div>
      </div>
    </div>
  );
}
