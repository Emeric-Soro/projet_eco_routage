import type { EstimateRequest, EstimateResponse, HealthResponse } from "../types/estimation";

const BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

async function readResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => ({}));
    const detail = typeof body === "object" && body !== null && "detail" in body
      ? (body as { detail?: unknown }).detail : null;
    throw new Error(typeof detail === "string" ? detail : `Erreur du serveur (${response.status}).`);
  }
  return response.json() as Promise<T>;
}

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return readResponse<HealthResponse>(await fetch(`${BASE}/api/health`, { signal }));
}

export async function estimatePrompt(request: EstimateRequest, signal?: AbortSignal): Promise<EstimateResponse> {
  return readResponse<EstimateResponse>(await fetch(`${BASE}/api/estimate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal,
  }));
}
