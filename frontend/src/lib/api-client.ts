import { formatApiError } from "./api-errors.ts";
import type { JobStatus, ProcessingJob } from "../types/workspace.ts";

export const API_KEY_STORAGE_KEY = "lipiocr.operatorApiKey";

type ApiBaseConfig = {
  configured: string;
  basePath: string;
  apiPort: string;
  origin: string;
  hostname: string;
  protocol: string;
};

export class ApiRequestError extends Error {
  status: number;

  constructor(status: number, detail: string) {
    super(detail || `${status}`);
    this.name = "ApiRequestError";
    this.status = status;
  }
}

export function resolveApiBaseFromConfig(config: ApiBaseConfig) {
  if (config.configured !== "auto") {
    return config.configured;
  }
  const basePath = config.basePath.replace(/\/$/, "");
  if (basePath) {
    return basePath;
  }
  return `${config.protocol}//${config.hostname}:${config.apiPort}`;
}

export function resolveApiBase() {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8010";
  if (typeof window === "undefined") {
    return configured === "auto" ? "http://localhost:8010" : configured;
  }
  return resolveApiBaseFromConfig({
    configured,
    basePath: process.env.NEXT_PUBLIC_BASE_PATH ?? "",
    apiPort: process.env.NEXT_PUBLIC_API_PORT ?? "13001",
    origin: window.location.origin,
    hostname: window.location.hostname,
    protocol: window.location.protocol,
  });
}

export function storedApiKey() {
  if (typeof window === "undefined") {
    return "";
  }
  return window.localStorage.getItem(API_KEY_STORAGE_KEY)?.trim() ?? "";
}

export function isUnauthorized(error: unknown) {
  return error instanceof ApiRequestError && error.status === 401;
}

export const API_BASE = resolveApiBase();

export async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  const apiKey = storedApiKey();
  if (apiKey && !headers.has("X-LipiOCR-API-Key")) {
    headers.set("X-LipiOCR-API-Key", apiKey);
  }
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new ApiRequestError(response.status, formatApiError(response.status, detail));
  }
  return (await response.json()) as T;
}

export function listJobs(status?: JobStatus) {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  return apiJson<ProcessingJob[]>(`/api/jobs${query}`, { cache: "no-store" });
}

export function getJob(jobId: string) {
  return apiJson<ProcessingJob>(`/api/jobs/${encodeURIComponent(jobId)}`, { cache: "no-store" });
}

export function retryJob(jobId: string) {
  return apiJson<ProcessingJob>(`/api/jobs/${encodeURIComponent(jobId)}/retry`, { method: "POST" });
}
