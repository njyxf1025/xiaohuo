import { useEffect, useMemo, useRef, useState } from "react";
import { Check, Image as ImageIcon, Loader2, Trash2, Upload, User } from "lucide-react";
import { toast } from "sonner";

import {
  deleteAvatar,
  getPresetThumbUrl,
  getAvatarThumbUrl,
  listAvatars,
  listPresets,
  uploadAvatar,
  type AvatarMetadata,
  type PresetAvatar,
} from "../api/avatar";
import { useStore, type SelectedAvatar } from "../store/useStore";
import { cn, formatBytes } from "../lib/utils";

type Tab = "preset" | "custom";

export default function AvatarSelector() {
  const [tab, setTab] = useState<Tab>("preset");
  const [presets, setPresets] = useState<PresetAvatar[]>([]);
  const [avatars, setAvatars] = useState<AvatarMetadata[]>([]);
  const [loadingPresets, setLoadingPresets] = useState(false);
  const [loadingAvatars, setLoadingAvatars] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const selected = useStore((s) => s.selectedAvatar);
  const setSelected = useStore((s) => s.setSelectedAvatar);

  const loadPresets = async () => {
    setLoadingPresets(true);
    try {
      const res = await listPresets();
      setPresets(res.presets || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingPresets(false);
    }
  };

  const loadAvatars = async () => {
    setLoadingAvatars(true);
    try {
      const res = await listAvatars();
      setAvatars((res.avatars || []).filter((a) => !a.is_preset));
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingAvatars(false);
    }
  };

  useEffect(() => {
    loadPresets();
    loadAvatars();
  }, []);

  const onUploadClick = () => fileInputRef.current?.click();

  const onUploadFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setUploading(true);
    try {
      const rec = await uploadAvatar(file);
      toast.success("形象上传成功");
      await loadAvatars();
      const sel: SelectedAvatar = {
        kind: rec.type,
        id: rec.avatar_id,
        name: rec.filename,
        thumbnailUrl: rec.thumbnail_url,
      };
      setSelected(sel);
    } catch (err) {
      console.error(err);
    } finally {
      setUploading(false);
    }
  };

  const onDelete = async (avatarId: string) => {
    try {
      await deleteAvatar(avatarId);
      toast.success("已删除");
      if (selected?.kind !== "preset" && selected?.id === avatarId) {
        setSelected(null);
      }
      await loadAvatars();
    } catch (e) {
      console.error(e);
    }
  };

  const selectPreset = (p: PresetAvatar) => {
    setSelected({
      kind: "preset",
      id: p.preset_id,
      name: p.name,
      thumbnailUrl: p.thumbnail_url,
    });
  };

  const selectCustom = (a: AvatarMetadata) => {
    setSelected({
      kind: a.type,
      id: a.avatar_id,
      name: a.filename,
      thumbnailUrl: a.thumbnail_url,
    });
  };

  const currentList = useMemo(
    () => (tab === "preset" ? presets : avatars),
    [tab, presets, avatars],
  );
  const isLoading = tab === "preset" ? loadingPresets : loadingAvatars;

  return (
    <div className="card space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm text-slate-300">
          <User className="h-4 w-4 text-brand-300" />
          <span>选择数字人形象</span>
        </div>
        <div className="hidden text-xs text-slate-500 sm:block">
          点击卡片即可选中
        </div>
      </div>

      <div className="flex items-center gap-2 rounded-xl bg-slate-900/60 p-1 ring-1 ring-slate-800">
        <button
          type="button"
          onClick={() => setTab("preset")}
          className={cn(
            "flex flex-1 items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition",
            tab === "preset"
              ? "bg-brand-500/20 text-brand-200 ring-1 ring-brand-500/30"
              : "text-slate-400 hover:text-slate-200",
          )}
        >
          预设
        </button>
        <button
          type="button"
          onClick={() => setTab("custom")}
          className={cn(
            "flex flex-1 items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition",
            tab === "custom"
              ? "bg-brand-500/20 text-brand-200 ring-1 ring-brand-500/30"
              : "text-slate-400 hover:text-slate-200",
          )}
        >
          自定义
        </button>
      </div>

      {tab === "custom" && (
        <div className="flex items-center gap-3">
          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp,video/mp4,video/quicktime"
            onChange={onUploadFile}
            className="hidden"
          />
          <button
            type="button"
            onClick={onUploadClick}
            disabled={uploading}
            className="btn-primary"
          >
            {uploading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Upload className="h-4 w-4" />
            )}
            上传自定义形象
          </button>
          <p className="text-xs text-slate-500">
            支持 JPG / PNG / WEBP 图片，MP4 / MOV 视频；需含清晰人脸。
          </p>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        {isLoading && (
          <div className="col-span-full flex items-center justify-center py-10 text-slate-500">
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            加载中…
          </div>
        )}
        {!isLoading && currentList.length === 0 && (
          <div className="col-span-full flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-slate-700 py-10 text-slate-500">
            <ImageIcon className="h-6 w-6" />
            <p className="text-sm">
              {tab === "preset" ? "暂无预设形象" : "尚未上传自定义形象"}
            </p>
          </div>
        )}
        {tab === "preset" &&
          presets.map((p) => {
            const isSel = selected?.kind === "preset" && selected.id === p.preset_id;
            return (
              <button
                key={p.preset_id}
                type="button"
                onClick={() => selectPreset(p)}
                className={cn(
                  "group relative overflow-hidden rounded-xl border bg-slate-900/40 text-left transition",
                  isSel
                    ? "border-brand-400 ring-2 ring-brand-500/40 shadow-glow"
                    : "border-slate-800 hover:border-slate-600",
                )}
              >
                <div className="aspect-[4/5] w-full overflow-hidden bg-slate-800">
                  <img
                    src={getPresetThumbUrl(p.preset_id)}
                    alt={p.name}
                    className="h-full w-full object-cover transition group-hover:scale-105"
                    loading="lazy"
                    onError={(e) => {
                      (e.currentTarget as HTMLImageElement).style.opacity = "0.2";
                    }}
                  />
                </div>
                <div className="flex items-center justify-between p-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-slate-100">
                      {p.name}
                    </p>
                    {p.description && (
                      <p className="truncate text-xs text-slate-500">
                        {p.description}
                      </p>
                    )}
                  </div>
                  {isSel && (
                    <span className="flex h-6 w-6 items-center justify-center rounded-full bg-brand-500 text-white">
                      <Check className="h-3.5 w-3.5" />
                    </span>
                  )}
                </div>
              </button>
            );
          })}
        {tab === "custom" &&
          avatars.map((a) => {
            const isSel =
              selected &&
              selected.kind !== "preset" &&
              selected.id === a.avatar_id;
            return (
              <div
                key={a.avatar_id}
                className={cn(
                  "group relative overflow-hidden rounded-xl border bg-slate-900/40 transition",
                  isSel
                    ? "border-brand-400 ring-2 ring-brand-500/40 shadow-glow"
                    : "border-slate-800",
                )}
              >
                <button
                  type="button"
                  onClick={() => selectCustom(a)}
                  className="block w-full text-left"
                >
                  <div className="aspect-[4/5] w-full overflow-hidden bg-slate-800">
                    <img
                      src={getAvatarThumbUrl(a.avatar_id)}
                      alt={a.filename}
                      className="h-full w-full object-cover transition group-hover:scale-105"
                      loading="lazy"
                      onError={(e) => {
                        (e.currentTarget as HTMLImageElement).style.opacity = "0.2";
                      }}
                    />
                  </div>
                  <div className="flex items-center justify-between p-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-slate-100">
                        {a.filename}
                      </p>
                      <p className="text-[11px] text-slate-500">
                        {a.type.toUpperCase()} · {formatBytes(a.size_bytes)}
                      </p>
                    </div>
                    {isSel && (
                      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-brand-500 text-white">
                        <Check className="h-3.5 w-3.5" />
                      </span>
                    )}
                  </div>
                </button>
                <button
                  type="button"
                  onClick={() => onDelete(a.avatar_id)}
                  className="absolute right-2 top-2 flex h-7 w-7 items-center justify-center rounded-full bg-slate-950/70 text-slate-300 opacity-0 transition hover:bg-rose-500/80 hover:text-white group-hover:opacity-100"
                  aria-label="删除形象"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            );
          })}
      </div>
    </div>
  );
}
