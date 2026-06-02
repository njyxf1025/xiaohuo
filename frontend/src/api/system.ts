import { apiClient } from "./client";

export interface GpuDevice {
  vendor?: string;
  name?: string;
  description?: string;
}

export interface SystemGpuInfo {
  count: number;
  devices: GpuDevice[];
}

export interface SystemOnnxProvider {
  chosen: string;
  providers: string[];
}

export interface SystemDirectML {
  available: boolean;
  reason: string;
  cpu_fallback_enabled: boolean;
}

export interface SystemInfo {
  service: string;
  version: string;
  log_level?: string;
  data_dir?: string;
  models_dir?: string;
  max_upload_mb: number;
  max_upload_bytes: number;
  cors_allow_origins?: string[];
  status?: string;
  gpu: SystemGpuInfo;
  directml: SystemDirectML;
  onnx_provider: SystemOnnxProvider;
  request_id?: string | null;
  timestamp?: number;
}

const DEFAULT_SYSTEM_INFO: SystemInfo = {
  service: "singing-digital-human",
  version: "0.0.0",
  max_upload_mb: 200,
  max_upload_bytes: 200 * 1024 * 1024,
  gpu: { count: 0, devices: [] },
  directml: { available: false, reason: "unknown", cpu_fallback_enabled: false },
  onnx_provider: { chosen: "unavailable", providers: [] },
};

let cached: { value: SystemInfo; expiresAt: number } | null = null;
const CACHE_TTL_MS = 30_000;

export async function getSystemInfo(force = false): Promise<SystemInfo> {
  const now = Date.now();
  if (!force && cached && cached.expiresAt > now) {
    return cached.value;
  }
  try {
    const { data } = await apiClient.get<SystemInfo>("/system/info", {
      // /system/info returns 503 with a valid body when DirectML is unavailable
      // (the strict-policy response). We want the body in that case so the UI
      // can still surface upload limits / GPU info / etc.
      validateStatus: (s) => (s >= 200 && s < 300) || s === 503,
    });
    const merged: SystemInfo = {
      ...DEFAULT_SYSTEM_INFO,
      ...data,
      gpu: { ...DEFAULT_SYSTEM_INFO.gpu, ...(data.gpu ?? {}) },
      directml: { ...DEFAULT_SYSTEM_INFO.directml, ...(data.directml ?? {}) },
      onnx_provider: {
        ...DEFAULT_SYSTEM_INFO.onnx_provider,
        ...(data.onnx_provider ?? {}),
      },
    };
    cached = { value: merged, expiresAt: now + CACHE_TTL_MS };
    return merged;
  } catch (e) {
    if (cached) return cached.value;
    throw e;
  }
}

export function getCachedSystemInfo(): SystemInfo | null {
  return cached ? cached.value : null;
}

export function clearSystemInfoCache(): void {
  cached = null;
}
