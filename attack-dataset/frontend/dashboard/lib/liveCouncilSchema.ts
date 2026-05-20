import { z } from "zod";

/** Attack step shape from KE chains and orchestrator `updated_steps`. */
export const AttackStepAttackSchema = z
  .object({
    id: z.number().or(z.string()),
    title: z.string(),
    category: z.string(),
    attack_type: z.string().optional(),
    mitre_technique: z.string().optional(),
    tools_used: z.string().optional(),
    attack_steps: z.string().optional(),
    scenario_description: z.string().optional(),
    detection_method: z.string().optional(),
  })
  .passthrough();

export const AttackChainStepSchema = z
  .object({
    phase: z.string(),
    attack: AttackStepAttackSchema,
    rationale: z.string().optional(),
    mitre_technique: z.string().optional(),
    command: z.string().optional(),
  })
  .passthrough();

export const AttackChainMetaSchema = z
  .object({
    replan_reason: z.string().optional(),
    parent_version: z.number().optional(),
    directive_id: z.string().optional(),
    dataset_record_ids: z.array(z.union([z.string(), z.number()])).optional(),
    failure_class: z.string().optional(),
  })
  .passthrough();

/** Knowledge Engine / orchestrator attack chain (relaxed for runtime variance). */
export const AttackChainSchema = z
  .object({
    chain_id: z.string().optional(),
    target_description: z.string().optional(),
    confidence: z.number().min(0).max(1).optional(),
    steps: z.array(AttackChainStepSchema),
    estimated_impact: z.string().optional(),
    opsec_notes: z.string().optional(),
    meta: AttackChainMetaSchema.optional(),
  })
  .passthrough();

const TradeOffSchema = z.object({
  speed: z.number().min(0).max(1).optional(),
  stealth: z.number().min(0).max(1).optional(),
  reliability: z.number().min(0).max(1).optional(),
});

const RationaleStepSchema = z.object({
  step: z.string(),
  detail: z.string(),
  trade_off: TradeOffSchema.optional(),
});

/** Orchestrator step rows applied by patch/reinitiate/pivot directives. */
export const OrchestratorChainStepSchema = AttackChainStepSchema;

const AgentMemoSchema = z
  .object({
    agent: z.string(),
  })
  .passthrough();

/** Backend emits `{ memos: [...] }`; design doc uses per-agent keys. */
export const AgentConsensusSchema = z.union([
  z
    .object({
      memos: z.array(AgentMemoSchema),
    })
    .passthrough(),
  z
    .object({
      tactical: z.unknown().optional(),
      opsec: z.unknown().optional(),
      architect: z.unknown().optional(),
      exploit: z.unknown().optional(),
      conductor: z.unknown().optional(),
    })
    .passthrough(),
]);

/**
 * Live council directive — aligned with `buildDirectiveFromCouncil` in council.js.
 * Relaxed vs design doc: optional engagement_id, turn, issued_at; priority includes "high".
 */
export const LiveDirectiveSchema = z
  .object({
    directive_id: z.string(),
    engagement_id: z.string().optional(),
    turn: z.number().int().min(0).optional(),
    issued_at: z.string().optional(),
    action: z.enum([
      "continue",
      "patch_chain",
      "reinitiate_chain",
      "pivot_chain",
      "pause",
      "abort",
    ]),
    priority: z.enum(["low", "normal", "high", "critical"]).optional(),
    from_step_index: z.number().int().min(0).optional(),
    rationale: z.string().optional(),
    rationale_steps: z.array(RationaleStepSchema).optional(),
    agent_consensus: AgentConsensusSchema.optional(),
    updated_chain: AttackChainSchema.optional(),
    updated_steps: z.array(OrchestratorChainStepSchema).optional(),
    pivot_chain_index: z.number().int().min(0).optional(),
    dataset_record_ids: z.array(z.union([z.string(), z.number()])).optional(),
    failure_class: z.string().optional(),
    grounding_query: z.string().optional(),
    opsec_veto: z.boolean().optional(),
    confidence: z.number().min(0).max(1).optional(),
    applied: z.boolean().optional(),
    applied_at: z.string().optional(),
    suggested_hotkey: z.string().optional(),
    suggested_template_id: z.string().optional(),
    suggested_action: z.string().optional(),
  })
  .passthrough();

export type AttackChain = z.infer<typeof AttackChainSchema>;
export type AttackChainStep = z.infer<typeof AttackChainStepSchema>;
export type LiveDirective = z.infer<typeof LiveDirectiveSchema>;
export type AgentConsensus = z.infer<typeof AgentConsensusSchema>;
export type OrchestratorChainStep = z.infer<typeof OrchestratorChainStepSchema>;

/** Safe-parse a directive from API/WS; returns undefined when shape is invalid. */
export function parseLiveDirective(input: unknown): LiveDirective | undefined {
  const result = LiveDirectiveSchema.safeParse(input);
  return result.success ? result.data : undefined;
}
