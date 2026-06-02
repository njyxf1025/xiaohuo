import { apiClient, buildUrl } from "./client";

export type AvatarType = "image" | "video" | "preset";

export type GenerationModel = "wav2lip" | "musetalk";

export type TaskState =
  | "pending"
  | "running"
  | "success"
  | "failed"
  | "cancelled";

export interface GenerationRequest {
  music_id?: string;
  slice_id?: string;
  start_sec?: number;
  end_sec?: number;
  avatar_id?: string;
  avatar_type: AvatarType;
  preset_id?: string;
  model?: GenerationModel;
  fps?: number;
  resize_factor?: number;
  enable_vocal_separation?: boolean;
  enable_denoising?: boolean;
}

export interface GenerationResponse {
  task_id: string;
  status: TaskState;
  message?: string | null;
  websocket_url?: string | null;
  request_id?: string | null;
}

export interface TaskStatusResponse {
  task_id: string;
  status: TaskState;
  progress: number;
  stage: string;
  message?: string | null;
  params?: Record<string, unknown> | null;
  result?: Record<string, unknown> | null;
  error?: string | null;
  model?: GenerationModel | null;
  created_at: number;
  updated_at: number;
  request_id?: string | null;
}

export interface TaskListResponse {
  tasks: TaskStatusResponse[];
  count: number;
  limit: number;
}

export interface VocalSeparationStatus {
  loaded: boolean;
  model_present: boolean;
  model_path: string | null;
  providers: string[];
  provider_label?: string;
  last_error?: string | null;
}

export interface EngineStatus {
  loaded: boolean;
  directml_available?: boolean;
  directml_reason?: string;
  cpu_fallback_enabled?: boolean;
  providers: string[];
  provider_label: string;
  wav2lip_path: string | null;
  face_detect_path: string | null;
  last_error: string | null;
  vocal_separation?: VocalSeparationStatus;
  request_id?: string;
  timestamp: number;
}

export interface EngineSlot {
  model: GenerationModel;
  directml_ready: boolean;
  directml_reason: string;
  loaded: boolean;
  provider_label: string;
  providers: string[];
  last_error: string | null;
  paths: Record<string, string>;
}

export interface EnginesStatusResponse {
  engines: {
    wav2lip: EngineSlot;
    musetalk: EngineSlot;
  };
  supported_models: GenerationModel[];
  default_model: GenerationModel;
  cpu_fallback_enabled: boolean;
  request_id?: string;
  timestamp: number;
}

export async function startGeneration(
  req: GenerationRequest,
): Promise<GenerationResponse> {
  const { data } = await apiClient.post<GenerationResponse>("/generation", req);
  return data;
}

export async function startGenerationWav2Lip(
  req: GenerationRequest,
): Promise<GenerationResponse> {
  const { data } = await apiClient.post<GenerationResponse>(
    "/generation/wav2lip",
    req,
  );
  return data;
}

export async function startGenerationMuseTalk(
  req: GenerationRequest,
): Promise<GenerationResponse> {
  const { data } = await apiClient.post<GenerationResponse>(
    "/generation/musetalk",
    req,
  );
  return data;
}

export async function getTask(
  taskId: string,
  config?: { signal?: AbortSignal },
): Promise<TaskStatusResponse> {
  const { data } = await apiClient.get<TaskStatusResponse>(
    `/generation/${taskId}`,
    { signal: config?.signal },
  );
  return data;
}

export async function listTasks(limit = 50): Promise<TaskListResponse> {
  const { data } = await apiClient.get<TaskListResponse>("/generation", {
    params: { limit },
  });
  return data;
}

export async function deleteTask(taskId: string): Promise<void> {
  await apiClient.delete(`/generation/${taskId}`);
}

export async function getEngineStatus(): Promise<EngineStatus> {
  const { data } = await apiClient.get<EngineStatus>("/generation/engine/status");
  return data;
}

export async function getEnginesStatus(): Promise<EnginesStatusResponse> {
  const { data } = await apiClient.get<EnginesStatusResponse>(
    "/generation/engines/status",
  );
  return data;
}

export async function warmupEngine(): Promise<EngineStatus> {
  const { data } = await apiClient.post<EngineStatus>("/generation/engine/warmup");
  return data;
}

export async function warmupWav2LipEngine(): Promise<EngineSlot> {
  const { data } = await apiClient.post<EngineSlot>(
    "/generation/engines/wav2lip/warmup",
  );
  return data;
}

export async function warmupMuseTalkEngine(): Promise<EngineSlot> {
  const { data } = await apiClient.post<EngineSlot>(
    "/generation/engines/musetalk/warmup",
  );
  return data;
}

export async function warmupVocalSeparation(): Promise<EngineStatus> {
  const { data } = await apiClient.post<EngineStatus>(
    "/generation/vocal_separation/warmup",
  );
  return data;
}

export function getTaskDownloadUrl(taskId: string): string {
  return buildUrl(`/generation/${taskId}/download`);
}

export function getTaskThumbUrl(taskId: string): string {
  return buildUrl(`/generation/${taskId}/thumbnail`);
}
