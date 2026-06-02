import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { Loader2, Music, UploadCloud } from "lucide-react";
import { toast } from "sonner";

import { getWaveform, uploadMusic } from "../api/music";
import { useStore } from "../store/useStore";
import { cn, formatBytes } from "../lib/utils";

const ACCEPTED = {
  "audio/mpeg": [".mp3"],
  "audio/wav": [".wav"],
  "audio/x-wav": [".wav"],
  "audio/mp4": [".m4a"],
  "audio/x-m4a": [".m4a"],
  "audio/flac": [".flac"],
  "audio/x-flac": [".flac"],
};

interface MusicUploaderProps {
  onUploaded?: (musicId: string) => void;
}

export default function MusicUploader({ onUploaded }: MusicUploaderProps) {
  const [busy, setBusy] = useState(false);
  const setCurrentMusic = useStore((s) => s.setCurrentMusic);

  const onDrop = useCallback(
    async (files: File[]) => {
      const file = files[0];
      if (!file) return;
      setBusy(true);
      try {
        const meta = await uploadMusic(file);
        let peaks: number[] = [];
        let duration = meta.duration_sec;
        try {
          const wf = await getWaveform(meta.music_id, 1000);
          peaks = wf.peaks;
          duration = wf.duration_sec || duration;
        } catch (e) {
          console.warn("waveform fetch failed", e);
        }
        setCurrentMusic({
          musicId: meta.music_id,
          filename: meta.filename,
          duration,
          chorus: meta.chorus ?? null,
          peaks,
        });
        toast.success("音乐上传成功");
        onUploaded?.(meta.music_id);
      } catch (e) {
        console.error(e);
      } finally {
        setBusy(false);
      }
    },
    [setCurrentMusic, onUploaded],
  );

  const { getRootProps, getInputProps, isDragActive, isDragReject } =
    useDropzone({
      onDrop,
      accept: ACCEPTED,
      maxFiles: 1,
      disabled: busy,
    });

  return (
    <div
      {...getRootProps()}
      className={cn(
        "group relative flex cursor-pointer flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed border-slate-700 bg-slate-900/40 px-6 py-12 text-center motion-reduce:transition-none",
        isDragActive && "border-brand-400 bg-brand-500/10 shadow-glow",
        isDragReject && "border-rose-500/60 bg-rose-500/10",
        busy && "pointer-events-none opacity-70",
      )}
    >
      <input {...getInputProps()} />
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-800/80 ring-1 ring-slate-700 transition group-hover:bg-brand-500/15 group-hover:ring-brand-500/30">
        {busy ? (
          <Loader2 className="h-7 w-7 animate-spin text-brand-300" />
        ) : (
          <UploadCloud className="h-7 w-7 text-brand-300" />
        )}
      </div>
      <div className="space-y-1">
        <p className="text-base font-semibold text-slate-100">
          {busy
            ? "正在上传并解析音频…"
            : isDragActive
              ? "松手即可上传"
              : "拖入或点击上传音乐"}
        </p>
        <p className="text-xs text-slate-400">
          支持 MP3 / WAV / M4A / FLAC · 单文件
        </p>
      </div>
      <div className="mt-2 flex items-center gap-2 text-xs text-slate-500">
        <Music className="h-3.5 w-3.5" />
        最大 {formatBytes(50 * 1024 * 1024)}
      </div>
    </div>
  );
}
