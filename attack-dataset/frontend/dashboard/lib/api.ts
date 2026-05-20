/**
 * API integration functions for the OpsecAI dashboard
 * Connects to backend endpoints for attack tree, agents, and feedback loop functionality
 */

import { KNOWLEDGE_ENGINE_URL, ORCHESTRATOR_URL, orchestratorFetchInit } from './config';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || KNOWLEDGE_ENGINE_URL;

export interface AttackTreeRequest {
  target_description: string;
  target_type?: string;
  constraints?: string[];
}

export interface AttackTreeResponse {
  id: string;
  name: string;
  nodes: any[];
  overall_score: number;
  mitre_techniques: string[];
}

export interface AttackPathRequest {
  tree_id: string;
  optimization_criteria?: 'speed' | 'stealth' | 'reliability' | 'balanced';
}

export interface AttackPathResponse {
  paths: any[];
  recommended_path: any;
  analysis: string;
}

export interface AgentStatusResponse {
  agents: any[];
  overall_status: string;
}

export interface AttackPlanRequest {
  target: string;
  plan_type: string;
  parameters?: Record<string, any>;
}

export interface AttackPlanResponse {
  plan_id: string;
  status: string;
  agents_assigned: string[];
  estimated_duration: number;
}

export interface FeedbackLoopRequest {
  session_id: string;
  execution_results: any[];
  environmental_factors?: Record<string, any>;
}

export interface FeedbackLoopResponse {
  session_id: string;
  adaptations: any[];
  recommendations: string;
}

export interface AdaptiveAttackRequest {
  target_description: string;
  previous_results?: any[];
  real_time_constraints?: Record<string, any>;
}

export interface AdaptiveAttackResponse {
  attack_chain: any[];
  confidence_score: number;
  adaptation_strategy: string;
}

/**
 * Build an attack tree from target description
 */
export async function buildAttackTree(request: AttackTreeRequest): Promise<AttackTreeResponse> {
  try {
    const response = await fetch(`${API_BASE_URL}/attack-tree/build`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw new Error(`Failed to build attack tree: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Error building attack tree:', error);
    throw error;
  }
}

/**
 * Generate attack paths from an attack tree
 */
export async function generateAttackPaths(request: AttackPathRequest): Promise<AttackPathResponse> {
  try {
    const response = await fetch(`${API_BASE_URL}/attack-tree/paths`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw new Error(`Failed to generate attack paths: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Error generating attack paths:', error);
    throw error;
  }
}

/**
 * Get status of all agents
 */
export async function getAgentStatus(): Promise<AgentStatusResponse> {
  try {
    const response = await fetch(`${API_BASE_URL}/agents/status`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to get agent status: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Error getting agent status:', error);
    throw error;
  }
}

/**
 * Execute an attack plan via multi-agent orchestrator
 */
export async function executeAttackPlan(request: AttackPlanRequest): Promise<AttackPlanResponse> {
  try {
    const response = await fetch(`${API_BASE_URL}/agents/execute-plan`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw new Error(`Failed to execute attack plan: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Error executing attack plan:', error);
    throw error;
  }
}

/**
 * Create a feedback loop session
 */
export async function createFeedbackSession(): Promise<{ session_id: string }> {
  try {
    const response = await fetch(`${API_BASE_URL}/feedback-loop/create`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to create feedback session: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Error creating feedback session:', error);
    throw error;
  }
}

/**
 * Submit execution results for adaptation
 */
export async function submitFeedbackResults(request: FeedbackLoopRequest): Promise<FeedbackLoopResponse> {
  try {
    const response = await fetch(`${API_BASE_URL}/feedback-loop/submit`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw new Error(`Failed to submit feedback results: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Error submitting feedback results:', error);
    throw error;
  }
}

/**
 * Generate adaptive attack chains
 */
export async function generateAdaptiveAttack(request: AdaptiveAttackRequest): Promise<AdaptiveAttackResponse> {
  try {
    const response = await fetch(`${API_BASE_URL}/adaptive-attack/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw new Error(`Failed to generate adaptive attack: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Error generating adaptive attack:', error);
    throw error;
  }
}

/**
 * Get previous attack results for analysis
 */
export async function getPreviousResults(limit: number = 10): Promise<any[]> {
  try {
    const response = await fetch(`${API_BASE_URL}/attacks/results?limit=${limit}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to get previous results: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Error getting previous results:', error);
    throw error;
  }
}

export async function getServicesStatus(): Promise<{ services: any[] }> {
  try {
    const response = await fetch(`${API_BASE_URL}/services/status`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to get services status: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Error getting services status:', error);
    throw error;
  }
}

export async function startService(serviceId: string): Promise<{ success: boolean; message: string }> {
  try {
    const response = await fetch(`${API_BASE_URL}/services/start`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ serviceId }),
    });

    if (!response.ok) {
      throw new Error(`Failed to start service: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Error starting service:', error);
    throw error;
  }
}

export async function stopService(serviceId: string): Promise<{ success: boolean; message: string }> {
  try {
    const response = await fetch(`${API_BASE_URL}/services/stop`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ serviceId }),
    });

    if (!response.ok) {
      throw new Error(`Failed to stop service: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Error stopping service:', error);
    throw error;
  }
}

// ── AI-Powered MITRE ATT&CK API ────────────────────────────────────────────────

// ORCHESTRATOR_URL from ./config

export interface MitreAnalyzeRequest {
  attack_description: string;
  target_type?: string;
  services?: string[];
  context?: string;
}

export interface MitreTechnique {
  technique_id: string;
  name: string;
  tactic: string;
  confidence: number;
  rationale: string;
  subtechniques: string[];
  detection_methods: string[];
  mitigations: string[];
}

export interface MitreChain {
  name: string;
  steps: Array<{
    phase: string;
    technique_id: string;
    description: string;
  }>;
  confidence: number;
}

export interface MitreAnalyzeResponse {
  techniques: MitreTechnique[];
  chains: MitreChain[];
  summary: string;
  generated_at: string;
  ai_model: string;
  /** openrouter | jailbreak_ai | heuristic */
  source?: string;
}

export interface MitreSuggestRequest {
  target: string;
  services?: string[];
  os?: string;
  aggression_level?: number;
}

export interface MitreSuggestResponse {
  source?: string;
  primary_techniques: Array<{
    technique_id: string;
    name: string;
    tactic: string;
    applicability: string;
    priority: number;
    prerequisites: string[];
    expected_outcome: string;
  }>;
  recommended_chain: {
    name: string;
    steps: Array<{
      order: number;
      phase: string;
      technique_id: string;
      description: string;
    }>;
    estimated_success: number;
  };
  defensive_recommendations: string[];
  analysis: string;
  generated_at: string;
  ai_model: string;
}

export interface MitreEnhanceRequest {
  chain: any;
  target?: string;
  context?: string;
}

export interface MitreEnhanceResponse {
  enhanced_steps: Array<{
    step_index: number;
    confirmed: boolean;
    suggested_technique_id: string;
    suggested_name: string;
    suggested_tactic: string;
    confidence: number;
    rationale: string;
    alternative_techniques: Array<{
      technique_id: string;
      name: string;
      reason: string;
    }>;
  }>;
  missing_techniques: Array<{
    phase: string;
    suggested_technique_id: string;
    reason: string;
  }>;
  overall_assessment: string;
  generated_at: string;
  ai_model: string;
}

function throwMitreApiError(
  body: { error?: string; detail?: string; heuristic_error?: string; code?: string },
  statusText: string
): never {
  const parts = [
    body.error,
    body.detail,
    body.heuristic_error,
  ].filter((p): p is string => Boolean(p && String(p).trim()));
  const message =
    parts[0] ||
    (body.code === 'MITRE_UNAVAILABLE'
      ? 'MITRE mapping unavailable — set JAILBREAK_API_KEY on integration-hub and restart integration-hub'
      : `MITRE request failed: ${statusText}`);
  throw new Error(message);
}

export async function analyzeMitreTechniques(request: MitreAnalyzeRequest): Promise<MitreAnalyzeResponse> {
  try {
    const response = await fetch(
      `${ORCHESTRATOR_URL}/mitre/analyze`,
      orchestratorFetchInit({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      })
    );

    if (!response.ok) {
      const err = await response.json().catch(() => ({ error: response.statusText }));
      throwMitreApiError(err, response.statusText);
    }

    return await response.json();
  } catch (error) {
    console.error('Error analyzing MITRE techniques:', error);
    throw error;
  }
}

export async function suggestMitreTechniques(request: MitreSuggestRequest): Promise<MitreSuggestResponse> {
  try {
    const response = await fetch(
      `${ORCHESTRATOR_URL}/mitre/suggest`,
      orchestratorFetchInit({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      })
    );

    if (!response.ok) {
      const err = await response.json().catch(() => ({ error: response.statusText }));
      throwMitreApiError(err, response.statusText);
    }

    return await response.json();
  } catch (error) {
    console.error('Error suggesting MITRE techniques:', error);
    throw error;
  }
}

export async function enhanceMitreChain(request: MitreEnhanceRequest): Promise<MitreEnhanceResponse> {
  try {
    const response = await fetch(`${ORCHESTRATOR_URL}/mitre/enhance-chain`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({ error: response.statusText }));
      throw new Error(err.error || `MITRE enhance failed: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Error enhancing MITRE chain:', error);
    throw error;
  }
}