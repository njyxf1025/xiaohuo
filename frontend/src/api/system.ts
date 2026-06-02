import { apiClient } from "./client";

export interface GpuDevice {
  vendor?: string;
  name?: string;
  index?: number;
  [key: string]: unknown;
}

export interface HealthResponse {
  status: string;
  request_id?: string;
  gpu: { count: number; devices: GpuDevice[] };
  onnx_provider: { chosen: string; providers: string[] };
}

export interface SystemInfoResponse {
  request_id?: string;
  gpu: { count: number; devices: GpuDevice[] };
  onnx_provider: { chosen: string; providers: string[] };
}

export async function getHealth(): Promise<HealthResponse> {
  const { data } = await apiClient.get<HealthResponse>("/health");
  return data;
}

export async function getSystemInfo(): Promise<SystemInfoResponse> {
  const { data } = await apiClient.get<SystemInfoResponse>("/system/info");
  return data;
}
