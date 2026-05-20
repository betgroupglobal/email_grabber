/** Browser-safe service URLs (NEXT_PUBLIC_* from .env.local / docker-compose). */

export const ORCHESTRATOR_URL =
  process.env.NEXT_PUBLIC_ORCHESTRATOR_URL || "http://localhost:3001";

export const ANALYZER_URL =
  process.env.NEXT_PUBLIC_ANALYZER_URL || "http://localhost:8001";

export const KNOWLEDGE_ENGINE_URL =
  process.env.NEXT_PUBLIC_KNOWLEDGE_ENGINE_URL || "http://localhost:8000";

export const OPSEC_URL =
  process.env.NEXT_PUBLIC_OPSEC_URL || "http://localhost:8002";

export const INTEGRATION_HUB_URL =
  process.env.NEXT_PUBLIC_INTEGRATION_HUB_URL || "http://localhost:8500";

export function integrationHubHttp(path: string): string {
  const base = INTEGRATION_HUB_URL.replace(/\/$/, "");
  return path.startsWith("/") ? `${base}${path}` : `${base}/${path}`;
}

/** Optional — required when orchestrator has ORCHESTRATOR_API_KEY set */
export const ORCHESTRATOR_API_KEY =
  process.env.NEXT_PUBLIC_ORCHESTRATOR_API_KEY || "";

export function orchestratorAuthHeaders(): Record<string, string> {
  if (!ORCHESTRATOR_API_KEY) return {};
  return { Authorization: `Bearer ${ORCHESTRATOR_API_KEY}` };
}

export function orchestratorHttp(path: string): string {
  const base = ORCHESTRATOR_URL.replace(/\/$/, "");
  return path.startsWith("/") ? `${base}${path}` : `${base}/${path}`;
}

export function orchestratorWs(path = ""): string {
  const base = ORCHESTRATOR_URL.replace(/^http/, "ws").replace(/\/$/, "");
  let url = !path ? base : path.startsWith("/") ? `${base}${path}` : `${base}/${path}`;
  if (ORCHESTRATOR_API_KEY) {
    const sep = url.includes("?") ? "&" : "?";
    url = `${url}${sep}api_key=${encodeURIComponent(ORCHESTRATOR_API_KEY)}`;
  }
  return url;
}

export function orchestratorFetchInit(init: RequestInit = {}): RequestInit {
  const headers = new Headers(init.headers);
  for (const [k, v] of Object.entries(orchestratorAuthHeaders())) {
    headers.set(k, v);
  }
  return { ...init, headers };
}

export function analyzerHttp(path: string): string {
  const base = ANALYZER_URL.replace(/\/$/, "");
  return path.startsWith("/") ? `${base}${path}` : `${base}/${path}`;
}
