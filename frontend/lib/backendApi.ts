"use client";

const DEFAULT_BACKEND_URLS = [
  "http://localhost:8000",
  "http://127.0.0.1:8000",
  "http://localhost:8001",
  "http://127.0.0.1:8001",
];

function normalizeBackendUrl(url: string): string {
  return url.replace(/\/+$/, "");
}

export function buildBackendCandidates(preferredUrl?: string): string[] {
  const candidates = [
    preferredUrl?.trim() || null,
    ...DEFAULT_BACKEND_URLS,
  ].filter((value): value is string => Boolean(value));

  const deduped: string[] = [];
  for (const candidate of candidates) {
    const normalized = normalizeBackendUrl(candidate);
    if (!deduped.includes(normalized)) {
      deduped.push(normalized);
    }
  }
  return deduped;
}

export async function fetchBackendJson<T>(path: string, init?: RequestInit): Promise<T> {
  const backendCandidates = buildBackendCandidates(process.env.NEXT_PUBLIC_BACKEND_URL);
  let lastError: unknown = null;

  for (const backendUrl of backendCandidates) {
    try {
      const response = await fetch(`${backendUrl}${path}`, init);
      if (!response.ok) {
        if (response.status >= 500) {
          lastError = new Error(`Backend ${backendUrl} returned ${response.status}.`);
          continue;
        }
        const detail = await response.text();
        throw new Error(detail || `Request failed with status ${response.status}.`);
      }

      return (await response.json()) as T;
    } catch (error) {
      lastError = error;
    }
  }

  throw lastError ?? new Error("No se pudo conectar con el backend.");
}
