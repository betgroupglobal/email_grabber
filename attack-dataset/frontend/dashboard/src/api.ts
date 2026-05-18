const BASE = process.env.REACT_APP_ORCHESTRATOR_URL || "http://localhost:3001";
const WS = process.env.REACT_APP_WS_URL || "ws://localhost:3001";

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

export interface OverseerEvent {
  ts: string;
  stage: string;
  type: "progress_update" | "evidence_update" | "gap_flag" | "overseer_feedback";
  severity: "info" | "warning" | "medium" | "high";
  message: string;
  suggestions: string[];
}

export interface AnalysisOverseer {
  enabled: boolean;
  objective: string;
  target: string;
  stage_order: string[];
  current_stage: string;
  started_at: string;
  updated_at: string;
  deepening_rounds: number;
  max_deepening_rounds: number;
  quality_gate: {
    threshold: number;
    status: "pending" | "pass" | "fail";
    reason: string;
  };
  quality: {
    coverage: number;
    depth: number;
    evidence: number;
    consistency: number;
    actionability: number;
    overall: number;
  };
  gaps: string[];
  recommendations: string[];
  events: OverseerEvent[];
}

export interface BoundaryProfile {
  aggression_level: number;
  require_private_scope: boolean;
  ai_rate_limit_per_min: number;
  ai_timeout_ms: number;
  scan_timeout_sec: number;
  scan_poll_timeout_ms: number;
  quality_gate_threshold: number;
  max_deepening_rounds: number;
  base_top_chains: number;
  deepening_top_chains: number;
}

export interface AIReasoningStep {
  step: number;
  stage: "data_collection" | "chain_analysis" | "opsec_analysis" | "final_synthesis";
  message: string;
  details: string;
  timestamp: string;
}

export interface Engagement {
  id: string; target: string; status: string;
  aggression_level?: number;
  boundary_profile?: BoundaryProfile;
  scan_session: { fingerprint?: TargetFingerprint; status: string } | null;
  attack_chains: AttackVectorResponse | null;
  opsec_reports: ChainOpsecReport | null;
  opsec_audit?: OpSecAuditResult | null;
  analysis_overseer?: AnalysisOverseer | null;
  ai_summary?: string;
  ai_reasoning?: AIReasoningStep[];
  log: { ts: string; msg: string }[];
  started_at: string; completed_at?: string; error?: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

/**
 * Streaming chat — calls the /ai/chat SSE endpoint.
 * onChunk is called with each text chunk as it arrives.
 * onDone is called when the stream finishes.
 */
export async function chatStream(
  question: string,
  history: ChatMessage[],
  engagementContext: AttackVectorResponse | null,
  engagementId: string | null,
  executionMode: "single_agent" | "swarm",
  swarmMaxSteps: number,
  onChunk: (chunk: string) => void,
  onDone: () => void,
  onError: (err: string) => void,
): Promise<void> {
  let resp: Response;
  try {
    resp = await fetch(`${BASE}/ai/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        history,
        engagement_context: engagementContext
          ? { chains: engagementContext.chains }
          : null,
        engagement_id: engagementId,
        stream: true,
        execution_mode: executionMode,
        swarm_max_steps: swarmMaxSteps,
      }),
    });
  } catch (e: any) {
    onError(e.message);
    return;
  }

  if (!resp.ok) {
    onError(`HTTP ${resp.status}`);
    return;
  }

  const reader = resp.body!.getReader();
  const decoder = new TextDecoder();
  let buf = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const lines = buf.split("\n");
    buf = lines.pop() ?? "";
    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const payload = line.slice(6);
      if (payload === "[DONE]") { onDone(); return; }
      onChunk(payload);
    }
  }
  onDone();
}

export async function analyseEngagement(eng: Engagement): Promise<string> {
  const r = await fetch(`${BASE}/ai/analyse/engagement`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      engagement_id: eng.id,
      target: eng.target,
      chains: eng.attack_chains?.chains ?? [],
      opsec_report: eng.opsec_reports,
      scan_fingerprint: eng.scan_session?.fingerprint ?? null,
    }),
  });
  const data = await r.json();
  return data.report ?? data.error ?? "No report returned";
}

export async function analyseChain(chain: AttackChain, engagementId: string | null = null): Promise<string> {
  const r = await fetch(`${BASE}/ai/analyse/chain`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chain, engagement_id: engagementId }),
  });
  const data = await r.json();
  return data.report ?? data.error ?? "No report returned";
}

export async function startEngagement(target: string, aggressionLevel = 1): Promise<{ engagement_id: string }> {
  const r = await fetch(`${BASE}/engage`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ target, aggression_level: aggressionLevel }),
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

// OpSec Audit API functions
export interface OpSecAuditResult {
  chain_id: string;
  chain_description: string;
  overall_risk_score: number;
  overall_risk_level: string;
  step_risks: {
    step_index: number;
    step_description: string;
    tools_found: string[];
    tool_risks: {
      tool_name: string;
      risk_level: string;
      risk_factors: string[];
      detection_methods: string[];
      opsec_recommendations: string[];
      substitution_alternative: string | null;
    }[];
    overall_risk: string;
    recommendations: string[];
  }[];
  critical_findings: string[];
  tool_substitutions: Record<string, string>;
  evasive_techniques: string[];
  detection_coverage: Record<string, string[]>;
}

export async function auditAttackVector(attackVector: any): Promise<OpSecAuditResult> {
  const r = await fetch(`${BASE}/opsec/audit/vector`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(attackVector),
  });
  if (!r.ok) {
    throw new Error(`HTTP ${r.status}: ${await r.text()}`);
  }
  return r.json();
}

export async function auditChain(
  chainId: string,
  chainDescription: string,
  steps: string[]
): Promise<OpSecAuditResult> {
  const r = await fetch(`${BASE}/opsec/audit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chain_id: chainId,
      chain_description: chainDescription,
      steps: steps,
    }),
  });
  if (!r.ok) {
    throw new Error(`HTTP ${r.status}: ${await r.text()}`);
  }
  return r.json();
}

export async function getToolRecommendations(toolName: string): Promise<any> {
  const r = await fetch(`${BASE}/opsec/tool/${encodeURIComponent(toolName)}`, {
    method: "POST",
  });
  if (!r.ok) {
    throw new Error(`HTTP ${r.status}: ${await r.text()}`);
  }
  return r.json();
}

export function subscribeEngagement(
  id: string,
  onUpdate: (eng: Engagement) => void
): () => void {
  let ws: WebSocket | null = null;
  let stopped = false;
  let retryDelay = 1000;
  let retryTimer: ReturnType<typeof setTimeout> | null = null;

  function connect() {
    if (stopped) return;
    ws = new WebSocket(`${WS}?engagement=${id}`);
    ws.onmessage = (e) => {
      try { onUpdate(JSON.parse(e.data)); } catch { /* ignore parse errors */ }
    };
    ws.onopen = () => { retryDelay = 1000; }; // reset backoff on success
    ws.onclose = () => {
      if (!stopped) {
        retryTimer = setTimeout(() => {
          retryDelay = Math.min(retryDelay * 2, 30_000); // cap at 30s
          connect();
        }, retryDelay);
      }
    };
    ws.onerror = () => ws?.close(); // trigger onclose for reconnect
  }

  connect();

  return () => {
    stopped = true;
    if (retryTimer) clearTimeout(retryTimer);
    ws?.close();
  };
}

// Plugin management API functions
const INTEGRATION_HUB_URL = process.env.REACT_APP_INTEGRATION_HUB_URL || "http://localhost:8500";

export interface PluginInfo {
  name: string;
  version: string;
  category: string;
  description: string;
  author: string;
  license: string;
  status: string;
  health_status: string;
}

export async function listPlugins(): Promise<PluginInfo[]> {
  const r = await fetch(`${INTEGRATION_HUB_URL}/api/v1/plugins`);
  const data = await r.json();
  return data.plugins || [];
}

export async function enablePlugin(pluginName: string): Promise<{ status: string; plugin: string }> {
  const r = await fetch(`${INTEGRATION_HUB_URL}/api/v1/plugins/${pluginName}/enable`, {
    method: "POST",
  });
  return r.json();
}

export async function disablePlugin(pluginName: string): Promise<{ status: string; plugin: string }> {
  const r = await fetch(`${INTEGRATION_HUB_URL}/api/v1/plugins/${pluginName}/disable`, {
    method: "POST",
  });
  return r.json();
}

// ── Health & Robustness API ──────────────────────────────────────────────────

const KNOWLEDGE_ENGINE_URL = process.env.REACT_APP_KNOWLEDGE_ENGINE_URL || "http://localhost:8000";

export interface ComponentHealth {
  status: "healthy" | "unhealthy" | "warning";
  details?: string;
}

export interface RobustnessHealthCheck {
  name: string;
  status: "healthy" | "unhealthy" | "unknown";
  last_check: string;
  consecutive_failures: number;
  message?: string;
}

export interface CircuitBreakerStatus {
  name: string;
  state: "closed" | "open" | "half_open";
  failure_count: number;
  last_failure?: string;
  opened_at?: string;
}

export interface HealthResponse {
  status: "healthy" | "unhealthy" | "degraded";
  timestamp: string;
  version: string;
  components: {
    api: ComponentHealth;
    postgres?: ComponentHealth & { record_count?: number };
    qdrant?: ComponentHealth;
    embedding_model?: ComponentHealth;
    ml_service?: ComponentHealth;
    robustness?: {
      overall_status: string;
      health_checks: Record<string, RobustnessHealthCheck>;
      circuit_breakers: CircuitBreakerStatus[];
    };
    timestamp: string;
    version: string;
  };
}

export interface RobustnessMetrics {
  health_report: {
    overall_status: string;
    health_checks: Record<string, RobustnessHealthCheck>;
    circuit_breakers: CircuitBreakerStatus[];
  };
  recent_errors: Array<{
    code: string;
    message: string;
    severity: string;
    service: string;
    timestamp: string;
  }>;
  error_log_size: number;
}

export async function getHealth(): Promise<HealthResponse> {
  const r = await fetch(`${KNOWLEDGE_ENGINE_URL}/health`);
  if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`);
  return r.json();
}

export async function getRobustnessMetrics(): Promise<RobustnessMetrics> {
  const r = await fetch(`${KNOWLEDGE_ENGINE_URL}/robustness`);
  if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`);
  return r.json();
}

// ── ML Prediction API ────────────────────────────────────────────────────────

export interface MLPrediction {
  label: string;
  confidence: number;
  rank: number;
}

export interface MLPredictRequest {
  text: string;
  target: string;
  top_k: number;
}

export interface MLPredictResponse {
  text: string;
  target: string;
  predictions: MLPrediction[];
}

export interface MLModelInfo {
  target: string;
  model_type: string;
  num_classes: number;
  accuracy?: number;
  num_samples?: number;
  embedding_method?: string;
  timestamp?: string;
}

export interface MLModelsResponse {
  models: MLModelInfo[];
  available_targets: string[];
}

export interface MLStatus {
  status: "available" | "unavailable";
  models_loaded: number;
  available_targets: string[];
  models_directory: string;
}

export async function getMLModels(): Promise<MLModelsResponse> {
  const r = await fetch(`${KNOWLEDGE_ENGINE_URL}/ml/models`);
  if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`);
  return r.json();
}

export async function getMLModelInfo(targetName: string): Promise<MLModelInfo> {
  const r = await fetch(`${KNOWLEDGE_ENGINE_URL}/ml/models/${encodeURIComponent(targetName)}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`);
  return r.json();
}

export async function predictAttack(request: MLPredictRequest): Promise<MLPredictResponse> {
  const r = await fetch(`${KNOWLEDGE_ENGINE_URL}/ml/predict`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`);
  return r.json();
}

export async function getMLStatus(): Promise<MLStatus> {
  const r = await fetch(`${KNOWLEDGE_ENGINE_URL}/ml/status`);
  if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`);
  return r.json();
}

// ── Plugin Execution API ─────────────────────────────────────────────────────

export interface PluginExecutionRequest {
  plugin_name: string;
  engagement_id?: string;
  target?: string;
  parameters: Record<string, any>;
  timeout?: number;
  metadata?: Record<string, any>;
}

export interface PluginExecutionResult {
  success: boolean;
  output: any;
  error?: string;
  artifacts?: Record<string, any>;
  opsec_context?: any;
  execution_time: number;
}

export async function executePlugin(request: PluginExecutionRequest): Promise<PluginExecutionResult> {
  const r = await fetch(`${INTEGRATION_HUB_URL}/integrations/execute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`);
  return r.json();
}

export async function getPluginInfo(pluginName: string): Promise<PluginInfo> {
  const r = await fetch(`${INTEGRATION_HUB_URL}/api/v1/plugins/${encodeURIComponent(pluginName)}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`);
  return r.json();
}

// ── MITRE ATT&CK API ─────────────────────────────────────────────────────────

export interface MitreTechnique {
  technique_id: string;
  technique_name: string;
  tactic: string;
  attacks: AttackRecord[];
}

export async function listMitreTechniques(): Promise<MitreTechnique[]> {
  const r = await fetch(`${KNOWLEDGE_ENGINE_URL}/mitre`);
  if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`);
  return r.json();
}

export async function getAttacksByMitreTechnique(techniqueId: string): Promise<AttackRecord[]> {
  const r = await fetch(`${KNOWLEDGE_ENGINE_URL}/mitre/${encodeURIComponent(techniqueId)}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`);
  return r.json();
}

// ── OpSec Quick Check API ────────────────────────────────────────────────────

const OPSEC_ANALYZER_URL = process.env.REACT_APP_OPSEC_ANALYZER_URL || "http://localhost:8002";

export interface OpSecQuickCheckRequest {
  description: string;
  tools_used: string[];
  target: string;
  aggression_level: number;
}

export interface OpSecQuickCheckFinding {
  severity: "critical" | "high" | "medium" | "low" | "info";
  title: string;
  description: string;
  recommendation: string;
}

export interface OpSecQuickCheckResponse {
  risk_score: number;
  risk_level: "critical" | "high" | "medium" | "low" | "minimal";
  findings: OpSecQuickCheckFinding[];
  evasion_recommendations: string[];
  detectability_factors: string[];
}

export async function assessOpSec(request: OpSecQuickCheckRequest): Promise<OpSecQuickCheckResponse> {
  const r = await fetch(`${OPSEC_ANALYZER_URL}/assess`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`);
  return r.json();
}

// ── Authentication API ───────────────────────────────────────────────────────

export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token?: string;
  token_type: string;
}

export interface UserProfile {
  id: string;
  username: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at?: string;
}

export async function login(request: LoginRequest): Promise<TokenResponse> {
  const r = await fetch(`${KNOWLEDGE_ENGINE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`);
  return r.json();
}

export async function refreshToken(refreshToken: string): Promise<TokenResponse> {
  const r = await fetch(`${KNOWLEDGE_ENGINE_URL}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`);
  return r.json();
}

export async function getCurrentUser(): Promise<UserProfile> {
  const token = localStorage.getItem("access_token");
  const r = await fetch(`${KNOWLEDGE_ENGINE_URL}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`);
  return r.json();
}

// ── AI Status API ────────────────────────────────────────────────────────────

export interface AIStatus {
  available: boolean;
  model?: string;
  provider?: string;
}

export async function getAIStatus(): Promise<AIStatus> {
  const r = await fetch(`${KNOWLEDGE_ENGINE_URL}/ai/status`);
  if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`);
  return r.json();
}
