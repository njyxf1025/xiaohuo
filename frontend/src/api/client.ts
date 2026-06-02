import axios, {
  AxiosError,
  AxiosInstance,
  AxiosResponse,
  InternalAxiosRequestConfig,
} from "axios";
import { toast } from "sonner";

const RAW_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";
const NORMALIZED_BASE = RAW_BASE.replace(/\/+$/, "");

function generateRequestId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `req-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export const apiClient: AxiosInstance = axios.create({
  baseURL: NORMALIZED_BASE,
  timeout: 300_000,
  maxContentLength: 500 * 1024 * 1024,
  maxBodyLength: 500 * 1024 * 1024,
  headers: {
    "Content-Type": "application/json",
    Accept: "application/json",
  },
});

apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    config.headers = config.headers ?? ({} as any);
    const incoming =
      (config.headers as Record<string, string | undefined>)["X-Request-ID"] ??
      (config.headers as Record<string, string | undefined>)["x-request-id"];
    if (!incoming) {
      (config.headers as Record<string, string>)["X-Request-ID"] =
        generateRequestId();
    }
    return config;
  },
  (error) => Promise.reject(error),
);

apiClient.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error: AxiosError<{ message?: string; error?: string; request_id?: string }>) => {
    const status = error.response?.status;
    const data = error.response?.data;
    const message =
      data?.message ||
      data?.error ||
      error.message ||
      "请求失败，请稍后重试";
    if (status && status >= 500) {
      const friendly = status === 504
        ? "网关响应超时（文件可能较大或后端处理较慢），请稍后重试"
        : status === 502
          ? "网关无响应，请检查后端服务是否运行"
          : status === 503
            ? "后端服务暂不可用（DirectML 引擎未就绪），请稍后重试"
            : `服务器错误 (${status}): ${message}`;
      toast.error(friendly);
    } else if (status === 413) {
      toast.error(`文件过大: ${message}`);
    } else if (status === 404) {
      toast.error(`未找到: ${message}`);
    } else if (status && status >= 400) {
      toast.error(message);
    } else if (error.code === "ECONNABORTED") {
      toast.error("请求超时，请检查后端服务是否运行");
    } else {
      toast.error(message);
    }
    return Promise.reject(error);
  },
);

export const API_BASE = NORMALIZED_BASE;

export function buildUrl(path: string): string {
  if (!path) return NORMALIZED_BASE;
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  if (path.startsWith("/")) return `${NORMALIZED_BASE}${path}`;
  return `${NORMALIZED_BASE}/${path}`;
}
