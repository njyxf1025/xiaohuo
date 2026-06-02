import { Cpu, Gauge, Layers, ShieldCheck, Sparkles, Zap } from "lucide-react";

const features = [
  {
    icon: Layers,
    title: "ONNX 跨平台",
    desc: "Wav2Lip 已导出为 ONNX 格式，与训练框架解耦，部署轻量。",
  },
  {
    icon: Zap,
    title: "DirectML GPU 加速",
    desc: "优先使用 DmlExecutionProvider，AMD / NVIDIA / Intel GPU 自动适配。",
  },
  {
    icon: ShieldCheck,
    title: "CPU 自动兜底",
    desc: "无 GPU 或 DirectML 不可用时无缝回退 CPUExecutionProvider。",
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
              唯一推理模型 · ONNX Runtime + DirectML
            </p>
          </div>
          <span className="ml-auto rounded-full bg-emerald-500/15 px-3 py-1 text-xs font-semibold text-emerald-300 ring-1 ring-emerald-500/30">
            <Cpu className="mr-1 inline h-3.5 w-3.5" /> 单一模型
          </span>
        </div>

        <p className="text-sm leading-relaxed text-slate-300">
          本项目仅保留 Wav2Lip-ONNX 一条推理路径。原 SadTalker、LatentSync 两种
          模型已从代码、权重与调度器中彻底移除，不再提供多模型对比或切换。
          推理时优先选择 DirectML EP，自动覆盖 AMD / NVIDIA / Intel GPU；
          当 DirectML 不可用时无缝回退到 CPUExecutionProvider。
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

        <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-3 text-xs text-amber-200/90">
          <strong>关于模型选型：</strong>
          采用 ONNX 格式是因为它能跨 ONNX Runtime 的多种 Execution Provider
          调度，DirectML 进一步让 AMD / NVIDIA / Intel GPU 共用同一套推理代码，
          极大简化部署与维护成本，相比多模型调度器更轻量、更稳定。
        </div>
      </div>
    </div>
  );
}
