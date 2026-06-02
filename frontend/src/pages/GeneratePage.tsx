import { useEffect, useMemo, useState } from "react";
import { AudioLines, Loader2, Sparkles, Wand2 } from "lucide-react";
import { toast } from "sonner";

import AvatarSelector from "../components/AvatarSelector";
import ModelInfoCard from "../components/ModelInfoCard";
import MusicUploader from "../components/MusicUploader";
import ProgressPanel from "../components/ProgressPanel";
import StepGuide from "../components/StepGuide";
import VideoPlayer from "../components/VideoPlayer";
import WaveformPlayer from "../components/WaveformPlayer";
import {
  getTaskDownloadUrl,
  startGeneration,
  type GenerationResponse,
  type TaskStatusResponse,
} from "../api/generation";
import {
  getSliceDownloadUrl,
  sliceMusic,
} from "../api/music";
import { useStore } from "../store/useStore";
import { cn } from "../lib/utils";

type Phase = "idle" | "uploaded" | "sliced" | "generating" | "done" | "failed";

export default function GeneratePage() {
  const currentMusic = useStore((s) => s.currentMusic);
  const selectedSegment = useStore((s) => s.selectedSegment);
  const setSelectedSegment = useStore((s) => s.setSelectedSegment);
  const slice = useStore((s) => s.slice);
  const setSlice = useStore((s) => s.setSlice);
  const avatar = useStore((s) => s.selectedAvatar);
  const currentTask = useStore((s) => s.currentTask);
  const setCurrentTask = useStore((s) => s.setCurrentTask);
  const enableVocalSeparation = useStore((s) => s.enableVocalSeparation);
  const setEnableVocalSeparation = useStore((s) => s.setEnableVocalSeparation);
  const enableDenoising = useStore((s) => s.enableDenoising);
  const setEnableDenoising = useStore((s) => s.setEnableDenoising);

  const [phase, setPhase] = useState<Phase>("idle");
  const [slicing, setSlicing] = useState(false);
  const [starting, setStarting] = useState(false);
  const [finalTask, setFinalTask] = useState<TaskStatusResponse | null>(null);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!currentMusic) {
      setPhase("idle");
    } else if (slice) {
      setPhase("sliced");
    } else {
      setPhase("uploaded");
    }
  }, [currentMusic, slice]);

  useEffect(() => {
    if (currentTask?.status === "success") {
      setFinalTask((prev) => prev ?? (currentTask as unknown as TaskStatusResponse));
    }
  }, [currentTask]);

  const currentStep = useMemo<1 | 2 | 3 | 4>(() => {
    if (phase === "idle") return 1;
    if (phase === "uploaded") return 2;
    if (phase === "sliced" || phase === "generating") return 3;
    if (phase === "done") return 4;
    return 1;
  }, [phase]);

  const onSegmentChange = (range: { start: number; end: number }) => {
    setSelectedSegment(range);
  };

  const onConfirmSegment = async () => {
    if (!currentMusic || !selectedSegment) return;
    setSlicing(true);
    try {
      const res = await sliceMusic(
        currentMusic.musicId,
        selectedSegment.start,
        selectedSegment.end,
      );
      setSlice({
        sliceId: res.slice_id,
        musicId: res.music_id,
        start: res.start_sec,
        end: res.end_sec,
        downloadUrl: res.download_url || getSliceDownloadUrl(res.slice_id),
      });
      toast.success("音频片段已生成");
      setPhase("sliced");
    } catch (e) {
      console.error(e);
    } finally {
      setSlicing(false);
    }
  };

  const onGenerate = async () => {
    if (!currentMusic || !slice || !avatar) return;
    setStarting(true);
    try {
      const payload: Parameters<typeof startGeneration>[0] = {
        avatar_type: avatar.kind,
        fps: 25,
        resize_factor: 1,
        slice_id: slice.sliceId,
        enable_vocal_separation: enableVocalSeparation,
        enable_denoising: enableDenoising,
      };
      if (avatar.kind === "preset") {
        payload.preset_id = avatar.id;
      } else {
        payload.avatar_id = avatar.id;
      }
      const res: GenerationResponse = await startGeneration(payload);
      setCurrentTask({
        taskId: res.task_id,
        status: res.status,
        progress: 0,
        stage: "pending",
        message: res.message ?? null,
      });
      setPhase("generating");
      toast.success("已提交生成任务");
    } catch (e) {
      console.error(e);
    } finally {
      setStarting(false);
    }
  };

  const onTaskComplete = (status: TaskStatusResponse) => {
    setFinalTask(status);
    setCurrentTask({
      taskId: status.task_id,
      status: status.status,
      progress: status.progress,
      stage: status.stage,
      message: status.message ?? null,
    });
    const url = getTaskDownloadUrl(status.task_id);
    setVideoUrl(url);
    setPhase("done");
    toast.success("视频生成完成！");
  };

  const onTaskError = (status: TaskStatusResponse) => {
    setPhase("failed");
    setCurrentTask({
      taskId: status.task_id,
      status: status.status,
      progress: status.progress,
      stage: status.stage,
      message: status.message ?? null,
    });
  };

  const canGenerate = !!slice && !!avatar && phase !== "generating" && phase !== "done";

  return (
    <div className="space-y-8">
      <header className="space-y-2">
        <h1 className="text-3xl font-extrabold tracking-tight text-white">
          创作中心
        </h1>
        <p className="text-sm text-slate-400">
          跟随 4 步引导，从一段音乐到一段唇形同步演唱视频。
        </p>
      </header>

      <StepGuide current={currentStep} />

      <section className="space-y-3">
        <SectionHeader
          index={1}
          title="上传音乐"
          desc="支持 MP3 / WAV / M4A / FLAC；上传后会自动检测高潮段落。"
        />
        <MusicUploader />
      </section>

      {currentMusic && (
        <section className="space-y-3">
          <SectionHeader
            index={2}
            title="选择并调整高潮区间"
            desc="已为你自动检测到高潮段落，拖拽两端微调后确认生成片段。"
          />
          <div className="card">
            <div className="mb-4 flex items-center justify-between text-sm text-slate-300">
              <div className="truncate">
                <span className="text-slate-500">当前音乐：</span>
                <span className="font-semibold text-white">
                  {currentMusic.filename}
                </span>
              </div>
              {currentMusic.chorus && (
                <span className="rounded-md bg-brand-500/15 px-2 py-1 text-xs text-brand-200 ring-1 ring-brand-500/30">
                  自动检测
                </span>
              )}
            </div>
            <WaveformPlayer
              musicId={currentMusic.musicId}
              peaks={currentMusic.peaks}
              duration={currentMusic.duration}
              chorus={currentMusic.chorus}
              initialStart={selectedSegment?.start}
              initialEnd={selectedSegment?.end}
              onChange={onSegmentChange}
            />
            <div className="mt-4 flex flex-wrap items-center justify-end gap-3">
              {slice ? (
                <span className="rounded-md bg-emerald-500/15 px-3 py-1 text-xs text-emerald-200 ring-1 ring-emerald-500/30">
                  已生成 slice {slice.sliceId.slice(0, 8)}
                </span>
              ) : null}
              <button
                type="button"
                onClick={onConfirmSegment}
                disabled={slicing || !selectedSegment || phase === "generating" || phase === "done"}
                className="btn-primary"
              >
                {slicing ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Wand2 className="h-4 w-4" />
                )}
                {slice ? "重新生成片段" : "使用此片段"}
              </button>
            </div>
          </div>
        </section>
      )}

      {currentMusic && slice && (
        <section className="space-y-3">
          <SectionHeader
            index={3}
            title="选择数字人形象"
            desc="可选用预设形象，或上传自定义图片/视频形象。"
          />
          <AvatarSelector />
        </section>
      )}

      {currentMusic && slice && (
        <section className="space-y-3">
          <SectionHeader
            index={4}
            title="生成唇形同步视频"
            desc="基于 Wav2Lip-ONNX + DirectML 进行唇形推理。"
          />
          <div className="space-y-4">
            <div className="card space-y-4">
              <div className="flex flex-col items-start justify-between gap-3 sm:flex-row sm:items-center">
                <div className="text-sm text-slate-300">
                  {avatar ? (
                    <>
                      已选形象：
                      <span className="font-semibold text-white">
                        {avatar.name}
                      </span>
                      <span className="ml-2 text-xs text-slate-500">
                        ({avatar.kind === "preset" ? "预设" : avatar.kind})
                      </span>
                    </>
                  ) : (
                    <span className="text-slate-500">请先选择一个数字人形象</span>
                  )}
                </div>
                <button
                  type="button"
                  disabled={!canGenerate || starting}
                  onClick={onGenerate}
                  className={cn("btn-primary", "px-6 py-3 text-base")}
                >
                  {starting ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Sparkles className="h-4 w-4" />
                  )}
                  生成视频
                </button>
              </div>

              <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
                <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-200">
                  <AudioLines className="h-4 w-4 text-brand-300" />
                  音频预处理选项
                </div>
                <div className="space-y-3">
                  <label className="flex cursor-pointer items-start gap-3">
                    <input
                      type="checkbox"
                      className="mt-0.5 h-4 w-4 rounded border-slate-600 bg-slate-800 text-brand-500 focus:ring-brand-500"
                      checked={enableVocalSeparation}
                      onChange={(e) => setEnableVocalSeparation(e.target.checked)}
                      disabled={phase === "generating" || phase === "done"}
                    />
                    <div>
                      <div className="text-sm font-medium text-slate-100">
                        启用人声分离（ONNX + DirectML）
                        <span className="ml-2 rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-semibold text-emerald-300 ring-1 ring-emerald-500/30">
                          推荐
                        </span>
                      </div>
                      <div className="mt-1 text-xs leading-relaxed text-slate-400">
                        上传带重低音伴奏的歌曲时，开启后先用 ONNX
                        人声分离模型把纯人声送进 Wav2Lip，唇形不再因伴奏震动而
                        抖动；最终视频再把人声与伴奏缝合，听感保持完整。
                        若未安装分离模型，会自动回退到原始音频。
                      </div>
                    </div>
                  </label>

                  <label className="flex cursor-not-allowed items-start gap-3 opacity-60">
                    <input
                      type="checkbox"
                      className="mt-0.5 h-4 w-4 rounded border-slate-600 bg-slate-800 text-brand-500 focus:ring-brand-500"
                      checked={enableDenoising}
                      onChange={(e) => setEnableDenoising(e.target.checked)}
                      disabled
                    />
                    <div>
                      <div className="text-sm font-medium text-slate-100">
                        启用音频降噪（resemble-denoiser）
                        <span className="ml-2 rounded-full bg-slate-700 px-2 py-0.5 text-[10px] font-semibold text-slate-300">
                          预留
                        </span>
                      </div>
                      <div className="mt-1 text-xs leading-relaxed text-slate-500">
                        模型架构已留好接口，等待 resemble-audio-denoiser ONNX
                        权重就位后即可启用。
                      </div>
                    </div>
                  </label>
                </div>
              </div>
            </div>

            {(phase === "generating" || phase === "done" || phase === "failed") &&
              currentTask && (
                <ProgressPanel
                  taskId={currentTask.taskId}
                  onComplete={onTaskComplete}
                  onError={onTaskError}
                />
              )}

            {phase === "done" && finalTask && videoUrl && (
              <VideoPlayer
                src={videoUrl}
                downloadName={`sdh-${finalTask.task_id}.mp4`}
              />
            )}
          </div>
        </section>
      )}

      <section className="space-y-3">
        <SectionHeader
          index={0}
          title="关于模型"
          desc="Wav2Lip-ONNX 是本项目唯一的推理模型。"
        />
        <ModelInfoCard />
      </section>
    </div>
  );
}

function SectionHeader({
  index,
  title,
  desc,
}: {
  index: number;
  title: string;
  desc: string;
}) {
  return (
    <div className="flex items-start gap-3">
      <div
        className={cn(
          "flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-sm font-bold ring-1",
          index === 0
            ? "bg-slate-800 text-slate-300 ring-slate-700"
            : "bg-brand-500/15 text-brand-200 ring-brand-500/30",
        )}
      >
        {index === 0 ? "·" : index}
      </div>
      <div>
        <h2 className="text-lg font-semibold text-white">{title}</h2>
        <p className="text-xs text-slate-400">{desc}</p>
      </div>
    </div>
  );
}
