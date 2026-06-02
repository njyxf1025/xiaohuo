import { apiClient, buildUrl } from "./client";

export interface AvatarMetadata {
  avatar_id: string;
  type: "image" | "video";
  filename: string;
  thumbnail_url: string;
  file_url?: string | null;
  face_box?: number[] | null;
  size_bytes: number;
  created_at: number;
  is_preset: boolean;
  has_face?: boolean | null;
}

export interface AvatarListResponse {
  avatars: AvatarMetadata[];
  count: number;
}

export interface PresetAvatar {
  preset_id: string;
  name: string;
  filename: string;
  thumbnail_url: string;
  file_url?: string | null;
  description?: string | null;
  created_at: number;
}

export interface PresetAvatarListResponse {
  presets: PresetAvatar[];
  count: number;
}

export async function uploadAvatar(file: File): Promise<AvatarMetadata> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await apiClient.post<AvatarMetadata>("/avatars/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function listAvatars(): Promise<AvatarListResponse> {
  const { data } = await apiClient.get<AvatarListResponse>("/avatars");
  return data;
}

export async function listPresets(): Promise<PresetAvatarListResponse> {
  const { data } = await apiClient.get<PresetAvatarListResponse>("/avatars/presets");
  return data;
}

export async function deleteAvatar(avatarId: string): Promise<void> {
  await apiClient.delete(`/avatars/${avatarId}`);
}

export function getAvatarUrl(avatarId: string): string {
  return buildUrl(`/avatars/${avatarId}/file`);
}

export function getPresetUrl(presetId: string): string {
  return buildUrl(`/avatars/presets/${presetId}/file`);
}

export function getAvatarThumbUrl(avatarId: string): string {
  return buildUrl(`/avatars/${avatarId}/thumbnail`);
}

export function getPresetThumbUrl(presetId: string): string {
  return buildUrl(`/avatars/presets/${presetId}/thumbnail`);
}
