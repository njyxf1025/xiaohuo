import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  Cpu,
  Gauge,
  Layers,
  Loader2,
  Music2,
  ShieldCheck,
  Sparkles,
  Zap,
} from "lucide-react";

import { getSystemInfo, type SystemInfo, type GpuDevice } from "../api/system";
import { cn } from "../lib/utils";

const STEPS = [
  { label: "上传音乐", desc: "支持 MP3 / WAV / M4A / FLAC" },
  { label: "选择高潮", desc: "自动检测 + 手动拖拽区间" },
  { label: "选择形象", desc: "内置预设 + 自定义上传" },
  { label: "生成视频", desc: "Wav2Lip-ONNX 唇形同步" },
];

const FEATURES = [
  {
    icon: Layers,
    title: "ONNX 跨平台",
    desc: "Wav2Lip ONNX 格式部署，跨框架解耦。",
  },
  {
    icon: Zap,
    title: "DirectML 加速",
    desc: "AMD / NVIDIA / Intel GPU 同一套调度代码。",
  },
  {
    icon: ShieldCheck,
    title: "CPU 自动兜底",
    desc: "DirectML 不可用时无缝回退 CPU。",
  },
  {
    icon: Gauge,
    title: "单一会话缓存",
    desc: "避免重复加载权重，秒级响应。",
  },
];

export default function HomePage() {
  const [info, setInfo] = useState<SystemInfo | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    getSystemInfo()
      .then((d) => {
        if (alive) setInfo(d);
      })
      .catch((e) => console.warn("system info load failed", e))
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  const gpuDevices = info?.gpu?.devices ?? [];
  const providerLabel = info?.onnx_provider?.chosen ?? "unknown";
  const providers = info?.onnx_provider?.providers ?? [];

  return (
    <div className="space-y-16">
      <section className="relative overflow-hidden rounded-3xl border border-slate-800 bg-slate-900/40 px-8 py-16 sm:px-12 sm:py-20">
        <div
          aria-hidden
          className="pointer-events-none absolute -top-32 right-0 h-96 w-96 rounded-full bg-brand-500/20 blur-3xl"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute -bottom-24 left-0 h-80 w-80 rounded-full bg-blue-500/10 blur-3xl"
        />
        <div className="relative grid items-center gap-10 lg:grid-cols-2">
          <div className="space-y-6">
            <span className="inline-flex items-center gap-2 rounded-full border border-brand-500/40 bg-brand-500/10 px-3 py-1 text-xs font-semibold text-brand-200">
              <Sparkles className="h-3.5 w-3.5" />
              Wav2Lip-ONNX · DirectML
            </span>
            <h1 className="text-4xl font-extrabold leading-tight tracking-tight text-white sm:text-5xl">
              上传音乐，一键让
              <span className="bg-gradient-to-r from-brand-300 to-fuchsia-300 bg-clip-text text-transparent">
                数字人
              </span>
              <br />
              为你演唱高潮段落
            </h1>
            <p className="max-w-xl text-base text-slate-300">
              自动检测歌曲高潮区间，可拖拽微调；选择数字人形象后，基于
              Wav2Lip-ONNX + ONNX Runtime DirectML 推理，一键生成唇形同步演唱视频。
            </p>
            <div className="flex flex-wrap items-center gap-3">
              <Link to="/generate" className="btn-primary text-base">
                开始创作
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link to="/history" className="btn-ghost text-base">
                查看历史记录
              </Link>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
              <span className="rounded-md bg-slate-800/80 px-2 py-1">
                跨平台 GPU
              </span>
              <span className="rounded-md bg-slate-800/80 px-2 py-1">
                ONNX 推理
              </span>
              <span className="rounded-md bg-slate-800/80 px-2 py-1">
                CPU 兜底
              </span>
            </div>
          </div>
          <div className="relative">
            <div className="card space-y-4">
              <div className="flex items-center gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-500/20 ring-1 ring-brand-500/30">
                  <Cpu className="h-5 w-5 text-brand-200" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-white">系统状态</p>
                  <p className="text-xs text-slate-400">
                    实时检测到的推理环境
                  </p>
                </div>
              </div>
              {loading ? (
                <div className="flex items-center gap-2 text-sm text-slate-400">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  正在读取后端信息…
                </div>
              ) : (
                <div className="space-y-3 text-sm">
                  <div>
                    <p className="text-xs uppercase tracking-wide text-slate-500">
                      ONNX Provider
                    </p>
                    <p className="mt-1 font-mono text-brand-200">
                      {providerLabel}
                    </p>
                    <p className="mt-1 text-xs text-slate-500">
                      {providers.join(" · ") || "no providers"}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-wide text-slate-500">
                      最大上传体积
                    </p>
                    <p className="mt-1 font-mono text-brand-200">
                      {info?.max_upload_mb
                        ? `${info.max_upload_mb} MB`
                        : "未知"}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-wide text-slate-500">
                      GPU 设备
                    </p>
                    {gpuDevices.length === 0 ? (
                      <p className="mt-1 text-slate-400">未检测到 GPU，将使用 CPU 推理</p>
                    ) : (
                      <ul className="mt-1 space-y-1 text-slate-300">
                        {gpuDevices.slice(0, 4).map((g: GpuDevice, i: number) => (
                          <li
                            key={i}
                            className="rounded-md bg-slate-950/60 px-2 py-1 text-xs"
                          >
                            {g.vendor || g.name || `GPU #${i}`}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </section>

      <section className="space-y-6">
        <div className="flex items-end justify-between">
          <h2 className="text-2xl font-bold text-white">四步完成创作</h2>
          <p className="text-sm text-slate-400">无需复杂配置</p>
        </div>
        <ol className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((s, i) => (
            <li
              key={s.label}
              className="card group relative overflow-hidden transition hover:border-brand-500/40"
            >
              <div className="absolute right-3 top-3 text-5xl font-extrabold leading-none text-slate-800/70 transition group-hover:text-brand-500/20">
                {i + 1}
              </div>
              <div className="relative space-y-2">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-500/15 ring-1 ring-brand-500/30">
                  <Music2 className="h-5 w-5 text-brand-200" />
                </div>
                <p className="text-base font-semibold text-white">{s.label}</p>
                <p className="text-xs text-slate-400">{s.desc}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section className="space-y-6">
        <h2 className="text-2xl font-bold text-white">为什么选择 Wav2Lip-ONNX</h2>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
          {FEATURES.map(({ icon: Icon, title, desc }) => (
            <div
              key={title}
              className="card transition hover:border-brand-500/40 hover:shadow-glow"
            >
              <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-brand-500/15 text-brand-200">
                <Icon className="h-5 w-5" />
              </div>
              <p className="text-base font-semibold text-white">{title}</p>
              <p className="mt-1 text-sm text-slate-400">{desc}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="flex flex-col items-center justify-center gap-4 rounded-3xl border border-slate-800 bg-gradient-to-br from-slate-900/60 to-slate-900/20 p-10 text-center">
        <h3 className="text-2xl font-bold text-white">准备好开始了吗？</h3>
        <p className="max-w-md text-sm text-slate-400">
          拖入你电脑里的 MP3，让数字人替你唱出最燃的 20 秒。
        </p>
        <Link to="/generate" className={cn("btn-primary", "px-6 py-3 text-base")}>
          开始创作
          <ArrowRight className="h-4 w-4" />
        </Link>
      </section>
    </div>
  );
}
