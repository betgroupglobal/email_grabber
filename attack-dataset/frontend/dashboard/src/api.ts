const BASE = process.env.REACT_APP_ORCHESTRATOR_URL || "http://localhost:3001";
const WS   = process.env.REACT_APP_WS_URL           || "ws://localhost:3001";

export interface ServiceInfo {
  port: string; protocol: string; name: string; product: string; version: string;
}
export interface TargetFingerprint {
  target: string; ip: string; os: string;
  services: ServiceInfo[]; scan_time: string;
}
export interface AttackRecord {
  id: number; title: string; category: string; attack_type: string;
  mitre_technique: string; impact: string; detection_method: string;
  solution: string; tools_used: string; attack_steps: string;
}
export interface AttackStep {
  phase: string; attack: AttackRecord; rationale: string; mitre_technique: string;
}
export interface AttackChain {
  chain_id: string; target_description: string; confidence: number;
  steps: AttackStep[]; estimated_impact: string; opsec_notes: string;
}
export interface AttackVectorResponse {
  target_description: string; chains: AttackChain[];
}
export interface OpsecFinding {
  rule_id: string; severity: string; title: string;
  description: string; remediation: string; evidence: string;
}
export interface OpsecReport {
  risk_score: number; total_findings: number;
  critical: number; high: number; medium: number; low: number;
  findings: OpsecFinding[]; summary: string;
}
export interface ChainOpsecReport {
  total_findings: number; risk_score: number;
  global_findings: OpsecFinding[];
}
export interface Engagement {
  id: string; target: string; status: string;
  scan_session: { fingerprint?: TargetFingerprint; status: string } | null;
  attack_chains: AttackVectorResponse | null;
  opsec_reports: ChainOpsecReport | null;
  log: { ts: string; msg: string }[];
  started_at: string; completed_at?: string; error?: string;
}

export async function startEngagement(target: string): Promise<{ engagement_id: string }> {
  const r = await fetch(`${BASE}/engage`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ target }),
  });
  return r.json();
}

export async function getEngagement(id: string): Promise<Engagement> {
  const r = await fetch(`${BASE}/engagements/${id}`);
  return r.json();
}

export async function listEngagements(): Promise<Engagement[]> {
  const r = await fetch(`${BASE}/engagements`);
  return r.json();
}

export async function semanticSearch(query: string, topK = 10) {
  const r = await fetch(`${BASE}/search`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, top_k: topK }),
  });
  return r.json();
}

export function subscribeEngagement(
  id: string,
  onUpdate: (eng: Engagement) => void
): () => void {
  const ws = new WebSocket(`${WS}?engagement=${id}`);
  ws.onmessage = (e) => {
    try { onUpdate(JSON.parse(e.data)); } catch { /* ignore */ }
  };
  return () => ws.close();
}
