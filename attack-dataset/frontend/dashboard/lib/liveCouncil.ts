/** Live Attack Council — types aligned with orchestrator WS + engagement.live_council */

import { parseLiveDirective, type LiveDirective } from "@/lib/liveCouncilSchema";

export type { LiveDirective, AttackChain } from "@/lib/liveCouncilSchema";
export {
  AttackChainSchema,
  LiveDirectiveSchema,
  parseLiveDirective,
} from "@/lib/liveCouncilSchema";
export {
  CouncilGroundingPackSchema,
  parseCouncilGroundingPack,
  type CouncilGroundingPack,
} from "@/lib/councilGroundingSchema";

export type CouncilWsEvent =
  | {
      type: "reasoning_thought";
      thought: ReasoningTraceEntry;
      timestamp?: string;
    }
  | { type: "council_turn_started"; turn: number; trigger?: string; timestamp?: string }
  | {
      type: "council_agent_memo";
      turn: number;
      agent: string;
      memo: Record<string, unknown>;
      timestamp?: string;
    }
  | {
      type: "live_directive";
      directive: LiveDirective;
      timestamp?: string;
    }
  | {
      type: "chain_versioned";
      version: number;
      diff_summary?: string;
      step_count?: number;
      timestamp?: string;
    }
  | { type: "execution_paused"; reason: string; timestamp?: string }
  | { type: "approval_required"; directive: LiveDirective; timestamp?: string }
  | {
      type: "pathway_attempt";
      attempt?: number;
      max_attempts?: number;
      pathway_id?: string;
      method?: string;
      label?: string;
      status?: string;
      task_kind?: string;
      timestamp?: string;
    }
  | {
      type: "pathway_approval_required";
      pathway?: { pathway_id?: string; label?: string; method?: string };
      task_kind?: string;
      timestamp?: string;
    };

export interface ReasoningTraceEntry {
  ts?: string;
  source?: string;
  turn?: number;
  action?: string;
  failure_class?: string;
  rationale?: string;
  rationale_steps?: Array<{ step: string; detail: string }>;
  phase_number?: number;
  phase_key?: string;
  narrative?: string;
  pattern_step?: string;
  stage?: string;
  objective?: string;
  subtasks?: string[];
  subtask_id?: string;
  alternate_pathways?: string[];
  hub_operation?: string;
  invoke_scan?: boolean;
  [key: string]: unknown;
}

export interface LiveCouncilState {
  enabled?: boolean;
  state?: string;
  turn?: number;
  replans_used?: number;
  max_replans?: number;
  analysis_lock?: boolean;
  pending_directive?: LiveDirective | null;
  pending_pathway?: {
    pathway?: { pathway_id?: string; label?: string; method?: string };
    task_kind?: string;
    task_id?: string;
    rationale?: string;
  } | null;
  last_directive?: LiveDirective | null;
  last_grounding_pack?: import("@/lib/councilGroundingSchema").CouncilGroundingPack;
  grounding_history?: Array<{
    turn: number;
    query_text?: string;
    hit_count?: number;
    ml_top?: string;
  }>;
  agent_memos?: Array<{ turn: number; agent: string; [key: string]: unknown }>;
  directives?: LiveDirective[];
}

export interface CouncilTimelineTurn {
  turn: number;
  trigger?: string;
  startedAt?: string;
  memos: Array<{ agent: string; memo: Record<string, unknown> }>;
  directive?: LiveDirective;
  chainVersion?: number;
  diffSummary?: string;
  grounding?: {
    hit_count?: number;
    ml_top?: string;
    query_text?: string;
  };
}

const AGENT_LABELS: Record<string, string> = {
  tactical: "Tactical Analyst",
  opsec: "OPSEC Sentinel",
  architect: "Chain Architect",
  exploit: "Exploit Strategist",
  conductor: "Conductor",
};

function coerceDirective(input: unknown): LiveDirective | undefined {
  return parseLiveDirective(input) ?? (input as LiveDirective | undefined);
}

export function agentLabel(agent: string): string {
  return AGENT_LABELS[agent] || agent;
}

export function directiveActionLabel(action: string): string {
  const labels: Record<string, string> = {
    continue: "Continue",
    patch_chain: "Patch chain",
    reinitiate_chain: "Reinitiate chain",
    pivot_chain: "Pivot chain",
    pause: "Pause",
    abort: "Abort",
  };
  return labels[action] || action;
}

/** Merge persisted engagement council state + live WS events into timeline rows */
export function buildCouncilTimeline(
  liveCouncil: LiveCouncilState | undefined,
  wsEvents: CouncilWsEvent[]
): CouncilTimelineTurn[] {
  const byTurn = new Map<number, CouncilTimelineTurn>();

  const ensure = (turn: number) => {
    if (!byTurn.has(turn)) {
      byTurn.set(turn, { turn, memos: [] });
    }
    return byTurn.get(turn)!;
  };

  if (liveCouncil?.grounding_history) {
    for (const g of liveCouncil.grounding_history) {
      const row = ensure(g.turn);
      row.grounding = {
        hit_count: g.hit_count,
        ml_top: g.ml_top,
        query_text: g.query_text,
      };
    }
  }

  if (liveCouncil?.agent_memos) {
    for (const m of liveCouncil.agent_memos) {
      const row = ensure(m.turn);
      const { turn: _t, agent, ...rest } = m;
      row.memos.push({ agent: String(agent), memo: rest as Record<string, unknown> });
    }
  }

  if (liveCouncil?.directives) {
    for (const d of liveCouncil.directives) {
      const parsed = coerceDirective(d);
      const turn = parsed?.turn ?? (d as LiveDirective).turn ?? 0;
      if (turn && parsed) {
        const row = ensure(turn);
        row.directive = parsed;
      }
    }
  }

  for (const ev of wsEvents) {
    if (ev.type === "council_turn_started") {
      const row = ensure(ev.turn);
      row.trigger = ev.trigger;
      row.startedAt = ev.timestamp;
    } else if (ev.type === "council_agent_memo") {
      const row = ensure(ev.turn);
      const exists = row.memos.some((m) => m.agent === ev.agent);
      if (!exists) row.memos.push({ agent: ev.agent, memo: ev.memo });
    } else if (ev.type === "live_directive") {
      const parsed = coerceDirective(ev.directive) ?? ev.directive;
      const turn = parsed.turn ?? 0;
      if (turn) {
        const row = ensure(turn);
        row.directive = parsed;
      }
    } else if (ev.type === "chain_versioned") {
      const last = [...byTurn.keys()].sort((a, b) => b - a)[0];
      if (last) {
        const row = ensure(last);
        row.chainVersion = ev.version;
        row.diffSummary = ev.diff_summary;
      }
    }
  }

  return [...byTurn.values()].sort((a, b) => a.turn - b.turn);
}

export function isCouncilWsMessage(data: unknown): data is CouncilWsEvent {
  if (!data || typeof data !== "object") return false;
  const t = (data as { type?: string }).type;
  return (
    t === "reasoning_thought" ||
    t === "council_turn_started" ||
    t === "council_agent_memo" ||
    t === "live_directive" ||
    t === "chain_versioned" ||
    t === "execution_paused" ||
    t === "approval_required"
  );
}

export function appendCouncilEvent(
  prev: CouncilWsEvent[],
  data: CouncilWsEvent
): CouncilWsEvent[] {
  if (data.type === "live_directive" || data.type === "approval_required") {
    const parsed = parseLiveDirective(data.directive);
    if (parsed) {
      data = { ...data, directive: parsed };
    }
  }
  return [...prev.slice(-200), data];
}
