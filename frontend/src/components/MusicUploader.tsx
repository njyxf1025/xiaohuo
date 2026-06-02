import { useCallback, useEffect, useState } from "react";
import { useDropzone } from "react-dropzone";
import { Loader2, Music, UploadCloud } from "lucide-react";
import { toast } from "sonner";

import { getWaveform, uploadMusic } from "../api/music";
import { getSystemInfo } from "../api/system";
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

const FALLBACK_MAX_UPLOAD_MB = 200;
const FALLBACK_MAX_UPLOAD_BYTES = FALLBACK_MAX_UPLOAD_MB * 1024 * 1024;

interface MusicUploaderProps {
  onUploaded?: (musicId: string) => void;
}

export default function MusicUploader({ onUploaded }: MusicUploaderProps) {
  const [busy, setBusy] = useState(false);
  const [maxBytes, setMaxBytes] = useState<number>(FALLBACK_MAX_UPLOAD_BYTES);
  const [maxMb, setMaxMb] = useState<number>(FALLBACK_MAX_UPLOAD_MB);
  const [limitReady, setLimitReady] = useState(false);
  const setCurrentMusic = useStore((s) => s.setCurrentMusic);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const info = await getSystemInfo();
        if (cancelled) return;
        const mb = Number(info.max_upload_mb) || FALLBACK_MAX_UPLOAD_MB;
        const bytes =
          Number(info.max_upload_bytes) || mb * 1024 * 1024;
        if (mb > 0) {
          setMaxMb(mb);
          setMaxBytes(bytes);
        }
      } catch (e) {
        console.warn("failed to fetch system upload limit, using fallback", e);
      } finally {
        if (!cancelled) setLimitReady(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const onDrop = useCallback(
    async (files: File[]) => {
      const file = files[0];
      if (!file) return;
      if (file.size > maxBytes) {
        toast.error(
          `文件过大：${formatBytes(file.size)}，当前后端允许的最大上传体积为 ${formatBytes(maxBytes)}`,
        );
        return;
      }
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
    [maxBytes, setCurrentMusic, onUploaded],
  );

  const { getRootProps, getInputProps, isDragActive, isDragReject } =
    useDropzone({
      onDrop,
      accept: ACCEPTED,
      maxFiles: 1,
      maxSize: maxBytes,
      disabled: busy,
    });

  const limitLabel = limitReady
    ? `最大 ${formatBytes(maxBytes)}（后端 ${maxMb} MB 上限）`
    : `最大 ${formatBytes(FALLBACK_MAX_UPLOAD_BYTES)}`;

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
        <Music aria-hidden="true" className="h-3.5 w-3.5" />
        {limitLabel}
      </div>
    </div>
  );
}
