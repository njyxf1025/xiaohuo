import { apiClient, buildUrl } from "./client";

export interface ChorusSegment {
  start_sec: number;
  end_sec: number;
  confidence: number;
  source: string;
}

export interface MusicUploadResponse {
  music_id: string;
  filename: string;
  duration_sec: number;
  sample_rate: number;
  channels: number;
  chorus?: ChorusSegment | null;
  status: string;
}

export interface MusicMetadataResponse {
  music_id: string;
  filename: string;
  extension: string;
  size_bytes: number;
  mime_type?: string | null;
  duration_sec: number;
  sample_rate: number;
  channels: number;
  status: string;
  chorus?: ChorusSegment | null;
  created_at: number;
}

export interface AudioSliceResponse {
  slice_id: string;
  music_id: string;
  start_sec: number;
  end_sec: number;
  file_path: string;
  download_url: string;
  duration_sec: number;
}

export interface WaveformResponse {
  music_id: string;
  duration_sec: number;
  sample_rate: number;
  channels: number;
  peaks: number[];
  num_peaks: number;
  num_samples: number;
}

export async function uploadMusic(file: File): Promise<MusicUploadResponse> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await apiClient.post<MusicUploadResponse>("/music/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function getMusic(musicId: string): Promise<MusicMetadataResponse> {
  const { data } = await apiClient.get<MusicMetadataResponse>(`/music/${musicId}`);
  return data;
}

export async function detectChorus(musicId: string): Promise<{
  music_id: string;
  chorus: ChorusSegment | null;
  status: string;
}> {
  const { data } = await apiClient.post(`/music/${musicId}/detect-chorus`);
  return data;
}

export async function sliceMusic(
  musicId: string,
  start: number,
  end: number,
  format?: string,
): Promise<AudioSliceResponse> {
  const { data } = await apiClient.post<AudioSliceResponse>(
    `/music/${musicId}/slice`,
    { start_sec: start, end_sec: end, format },
  );
  return data;
}

export async function getWaveform(
  musicId: string,
  peaks = 1000,
): Promise<WaveformResponse> {
  const { data } = await apiClient.get<WaveformResponse>(
    `/music/${musicId}/waveform`,
    { params: { num_peaks: peaks } },
  );
  return data;
}

export function getSliceDownloadUrl(sliceId: string): string {
  return buildUrl(`/music/slice/${sliceId}/download`);
}

export function getMusicDownloadUrl(musicId: string): string {
  return buildUrl(`/music/${musicId}/download`);
}
