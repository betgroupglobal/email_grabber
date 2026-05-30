/** Types and helpers for the Real-time Analyzer service (port 8001). */

import { analyzerHttp } from "@/lib/config";

export type AnalyzerSessionStatus = "scanning" | "analysing" | "ready" | "error";

export interface AnalyzerServiceInfo {
  port: string;
  protocol: string;
  name: string;
  product: string;
  version: string;
}

export interface AnalyzerFingerprint {
  target: string;
  ip: string;
  os: string;
  services: AnalyzerServiceInfo[];
  scan_time?: string;
}

export interface AttackChainStep {
  phase: string;
  rationale?: string;
  mitre_technique?: string;
  attack?: { title?: string; category?: string; mitre_technique?: string };
}

export interface AttackChain {
  chain_id: string;
  target_description?: string;
  confidence?: number;
  steps?: AttackChainStep[];
  estimated_impact?: string;
  opsec_notes?: string;
}

export interface AnalyzerVectors {
  target_description?: string;
  chains?: AttackChain[];
}

export interface AnalyzerSession {
  id: string;
  target: string;
  status: AnalyzerSessionStatus;
  scan_timeout_sec?: number;
  scan_type?: string;
  aggression_level?: number;
  fingerprint?: AnalyzerFingerprint;
  vectors?: AnalyzerVectors;
  started_at: string;
  completed_at?: string;
  duration_sec?: number;
  service_count?: number;
  open_port_count?: number;
  error?: string;
}

export interface AnalyzerHealth {
  status: string;
  service: string;
  uptime_sec?: number;
  active_sessions?: number;
  scanning_sessions?: number;
  analysing_sessions?: number;
  nmap_available?: boolean;
  knowledge_engine_url?: string;
}

export type ScanType =
  | "default"
  | "quick"
  | "comprehensive"
  | "web_application"
  | "ssh_brute_force"
  | "database_enumeration";

export const SCAN_TYPE_OPTIONS: { value: ScanType; label: string; hint: string }[] = [
  { value: "default", label: "Balanced", hint: "Timeout-scaled top ports" },
  { value: "quick", label: "Quick", hint: "Top 20 ports" },
  { value: "comprehensive", label: "Comprehensive", hint: "Deep port coverage" },
  { value: "web_application", label: "Web", hint: "HTTP/HTTPS focus" },
  { value: "ssh_brute_force", label: "SSH", hint: "Port 22" },
  { value: "database_enumeration", label: "Database", hint: "Common DB ports" },
];

export function isSessionActive(status: AnalyzerSessionStatus): boolean {
  return status === "scanning" || status === "analysing";
}

export function statusLabel(status: AnalyzerSessionStatus): string {
  switch (status) {
    case "scanning":
      return "Scanning";
    case "analysing":
      return "Analysing";
    case "ready":
      return "Ready";
    case "error":
      return "Error";
    default:
      return status;
  }
}

export function isAdaptiveScanType(scanType?: string): boolean {
  if (!scanType || scanType === "default") return false;
  return [
    "web_application",
    "ssh_brute_force",
    "database_enumeration",
    "comprehensive",
    "quick",
  ].includes(scanType);
}

const SESSION_CACHE_KEY = "opsec_analyzer_session_cache_v1";

export function loadCachedSessionIds(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(SESSION_CACHE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as string[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function cacheSessionId(id: string): void {
  if (typeof window === "undefined") return;
  const ids = loadCachedSessionIds().filter((x) => x !== id);
  ids.unshift(id);
  localStorage.setItem(SESSION_CACHE_KEY, JSON.stringify(ids.slice(0, 50)));
}

export async function fetchAnalyzerHealth(): Promise<AnalyzerHealth | null> {
  try {
    const res = await fetch(analyzerHttp("/health"));
    if (!res.ok) return null;
    return (await res.json()) as AnalyzerHealth;
  } catch {
    return null;
  }
}

export async function fetchSessions(): Promise<AnalyzerSession[]> {
  const res = await fetch(analyzerHttp("/sessions"));
  if (!res.ok) return [];
  const data = await res.json();
  return Array.isArray(data) ? data : [];
}

export async function fetchSession(id: string): Promise<AnalyzerSession | null> {
  const res = await fetch(analyzerHttp(`/sessions/${id}`));
  if (!res.ok) return null;
  return (await res.json()) as AnalyzerSession;
}

export async function startScan(payload: {
  target: string;
  scan_timeout_sec: number;
  scan_type?: ScanType;
  aggression_level?: number;
  scan_args?: string[];
}): Promise<{ session: AnalyzerSession | null; error?: string }> {
  const body: Record<string, unknown> = {
    target: payload.target.trim(),
    scan_timeout_sec: payload.scan_timeout_sec,
  };
  if (payload.scan_type && payload.scan_type !== "default") {
    body.scan_type = payload.scan_type;
  }
  if (payload.aggression_level && payload.aggression_level > 0) {
    body.aggression_level = payload.aggression_level;
  }
  if (payload.scan_args?.length) {
    body.scan_args = payload.scan_args;
  }

  const res = await fetch(analyzerHttp("/scan"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg =
      (data as { message?: string }).message ||
      (data as { error?: string }).error ||
      `Scan failed (${res.status})`;
    return { session: null, error: msg };
  }
  const session = data as AnalyzerSession;
  if (session?.id) cacheSessionId(session.id);
  return { session, error: undefined };
}

export function fingerprintExportUrl(sessionId: string): string {
  return analyzerHttp(`/sessions/${sessionId}/fingerprint`);
}
