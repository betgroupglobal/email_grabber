import { orchestratorFetchInit, orchestratorHttp } from "./config";

export interface ExecuteChainErrorBody {
  error?: string;
  code?: string;
  correlation_id?: string;
  details?: { step_index?: number | null; hint?: string };
}

export async function fetchEngagement(engagementId: string) {
  const res = await fetch(orchestratorHttp(`/engagements/${engagementId}`), orchestratorFetchInit());
  if (!res.ok) throw new Error(`Engagement fetch failed (${res.status})`);
  return res.json();
}

export async function executeAttackChain(body: {
  engagement_id: string;
  chain_index: number;
  chain: unknown;
}): Promise<{ ok: true; data: unknown } | { ok: false; status: number; body: ExecuteChainErrorBody }> {
  const res = await fetch(orchestratorHttp("/execute-chain"), orchestratorFetchInit({
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }));

  const data = (await res.json().catch(() => ({}))) as ExecuteChainErrorBody & Record<string, unknown>;

  if (!res.ok) {
    return { ok: false, status: res.status, body: data };
  }
  return { ok: true, data };
}

export async function startFullEngagementFromOpsec(
  opsecEngagementId: string
): Promise<
  | { ok: true; data: { engagement_id: string; message?: string } }
  | { ok: false; status: number; body: Record<string, unknown> }
> {
  const res = await fetch(
    orchestratorHttp(`/engagements/${encodeURIComponent(opsecEngagementId)}/start-full-engagement`),
    orchestratorFetchInit({ method: "POST" })
  );
  const data = (await res.json().catch(() => ({}))) as Record<string, unknown>;
  if (!res.ok) return { ok: false, status: res.status, body: data };
  return {
    ok: true,
    data: data as { engagement_id: string; message?: string },
  };
}

export interface OpsecAssessResult {
  engagement_id?: string;
  overall_score?: number;
  risk_score?: number;
  attack_chains?: {
    chains: Array<{
      chain_id?: string;
      confidence?: number;
      steps?: unknown[];
      steps_count?: number;
    }>;
  };
}

export async function assessOpsecTarget(body: {
  target: string;
  operation_type?: string;
  aggression_level?: string;
}): Promise<
  | { ok: true; data: OpsecAssessResult }
  | { ok: false; status: number; body: Record<string, unknown> }
> {
  const res = await fetch(
    orchestratorHttp("/opsec/assess"),
    orchestratorFetchInit({
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
  );
  const data = (await res.json().catch(() => ({}))) as OpsecAssessResult &
    Record<string, unknown>;
  if (!res.ok) return { ok: false, status: res.status, body: data };
  return { ok: true, data };
}

export interface GuidedAutonomousStartResult {
  engagement_id: string;
  target: string;
  status: string;
  jailbreak_api_configured?: boolean;
  message?: string;
}

export interface GuidedAutonomousStatus {
  engagement_id: string;
  target: string;
  status: string;
  policy?: { allow_high_risk?: boolean };
  guided_autonomous?: {
    status?: string;
    current_phase?: number;
    current_phase_title?: string;
    phases?: Array<{
      phase_number: number;
      title: string;
      status: string;
      ai_source?: string;
      ai_latency_ms?: number;
      narrative?: string;
      artifact_text?: string;
      findings_summary?: string;
      tools_planned?: Array<{ plugin?: string; tool?: string }>;
      tools_executed?: Array<{ plugin?: string; tool?: string; success?: boolean }>;
      tool_results?: Array<{ plugin?: string; tool?: string; success?: boolean }>;
      council_turn?: number | null;
      council_turn_id?: string | null;
    }>;
    last_ai_source?: string;
    last_ai_latency_ms?: number;
    jailbreak_api_configured?: boolean;
    jailbreak_sources?: string[];
    error?: string;
    tools_invoked_count?: number;
    pathway_attempts_count?: number;
    assess_complete?: boolean;
    chain_executed?: boolean;
    completed_at?: string;
    run_summary?: {
      status?: string;
      phases_completed?: number;
      phases_total?: number;
      tools_invoked_count?: number;
      pathway_attempts_count?: number;
      council_turns?: number;
      council_approvals?: number;
      tools_used?: string[];
      assess_complete?: boolean;
      chain_executed?: boolean;
      completed_at?: string | null;
    };
  };
  attack_chains_count?: number;
  live_council?: import("@/lib/liveCouncil").LiveCouncilState;
  attack_chains?: { version?: number };
  reasoning_trace?: Array<Record<string, unknown>>;
  scan_session?: {
    id?: string;
    status?: string;
    scan_type?: string;
    service_count?: number;
    open_port_count?: number;
    fingerprint?: { os?: string; services?: unknown[] };
  } | null;
  fingerprint?: { os?: string; services?: unknown[] } | null;
  /** Server-side run continues when the browser disconnects */
  detach_safe?: boolean;
}

export interface TerminalHistoryLine {
  type?: string;
  content: string;
  timestamp?: string;
}

export async function startGuidedAutonomous(body: {
  target: string;
  aggression_level?: number;
  roe_acknowledged: boolean;
  web_only?: boolean;
}): Promise<
  | { ok: true; data: GuidedAutonomousStartResult }
  | { ok: false; status: number; body: Record<string, unknown> }
> {
  const res = await fetch(
    orchestratorHttp("/guided/autonomous/start"),
    orchestratorFetchInit({
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
  );
  const data = (await res.json().catch(() => ({}))) as GuidedAutonomousStartResult &
    Record<string, unknown>;
  if (!res.ok) return { ok: false, status: res.status, body: data };
  return { ok: true, data };
}

export async function stopGuidedAutonomous(
  engagementId: string
): Promise<{ ok: boolean; status: number }> {
  const res = await fetch(
    orchestratorHttp(`/guided/autonomous/${encodeURIComponent(engagementId)}/stop`),
    orchestratorFetchInit({ method: "POST" })
  );
  return { ok: res.ok, status: res.status };
}

export async function fetchGuidedAutonomousStatus(
  engagementId: string
): Promise<GuidedAutonomousStatus | null> {
  const res = await fetch(
    orchestratorHttp(`/guided/autonomous/${encodeURIComponent(engagementId)}/status`),
    orchestratorFetchInit()
  );
  if (!res.ok) return null;
  return res.json() as Promise<GuidedAutonomousStatus>;
}

export async function approveLiveCouncilDirective(
  engagementId: string
): Promise<{ ok: boolean; status: number }> {
  const res = await fetch(
    orchestratorHttp(`/engagements/${encodeURIComponent(engagementId)}/live/approve`),
    orchestratorFetchInit({ method: "POST" })
  );
  return { ok: res.ok, status: res.status };
}

export async function forceLiveCouncilReplan(
  engagementId: string,
  options?: { chain_index?: number; from_step_index?: number }
): Promise<{ ok: boolean; status: number }> {
  const res = await fetch(
    orchestratorHttp(`/engagements/${encodeURIComponent(engagementId)}/live/force-replan`),
    orchestratorFetchInit({
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(options ?? {}),
    })
  );
  return { ok: res.ok, status: res.status };
}

export async function fetchReasoningTrace(engagementId: string): Promise<{
  reasoning_trace?: Array<Record<string, unknown>>;
} | null> {
  const res = await fetch(
    orchestratorHttp(`/engagements/${encodeURIComponent(engagementId)}/reasoning-trace`),
    orchestratorFetchInit()
  );
  if (!res.ok) return null;
  return res.json();
}

export async function fetchTerminalHistory(
  engagementId: string,
  limit = 200
): Promise<TerminalHistoryLine[]> {
  const res = await fetch(
    orchestratorHttp(
      `/engagements/${encodeURIComponent(engagementId)}/terminal/history?limit=${limit}`
    ),
    orchestratorFetchInit()
  );
  if (!res.ok) return [];
  const data = (await res.json()) as { lines?: TerminalHistoryLine[] };
  return data.lines ?? [];
}

export function formatExecuteChainError(body: ExecuteChainErrorBody): string {
  const base = body.error || "Execution failed";
  const idx = body.details?.step_index;
  const hint = body.details?.hint;
  const parts = [base];
  if (idx != null) parts.push(`step ${idx}`);
  if (hint) parts.push(hint);
  return parts.join(" — ");
}
