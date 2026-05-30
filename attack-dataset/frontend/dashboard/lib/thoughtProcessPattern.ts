/** AI thought-process pattern when facing a target — mirrors backend/orchestrator/reasoning-pattern.js */

import type { CouncilWsEvent, LiveCouncilState, ReasoningTraceEntry } from "@/lib/liveCouncil";
import {
  STAGE_LABELS,
  THOUGHT_PATTERN_STEPS,
  THOUGHT_PROCESS_CYCLE,
  getStageById,
  getStageIndex,
  subtaskId,
  type SubtaskProgress,
  type SubtaskStatus,
  type ThoughtCycleStageId,
} from "@/lib/thoughtProcessCycle";

export {
  THOUGHT_PROCESS_CYCLE,
  THOUGHT_PATTERN_STEPS,
  STAGE_LABELS,
  getStageById,
  getNextStage,
  getStageIndex,
  subtaskId,
} from "@/lib/thoughtProcessCycle";
export type { ThoughtCycleStageId, ThoughtCycleStage, SubtaskProgress, SubtaskStatus } from "@/lib/thoughtProcessCycle";

export type ThoughtPatternStep = ThoughtCycleStageId;

const STEP_ORDER = THOUGHT_PATTERN_STEPS.reduce(
  (acc, step, i) => {
    acc[step] = i;
    return acc;
  },
  {} as Record<ThoughtPatternStep, number>
);

function isValidStep(step: string): step is ThoughtPatternStep {
  return (THOUGHT_PATTERN_STEPS as readonly string[]).includes(step);
}

export function inferPatternStep(entry: ReasoningTraceEntry): ThoughtPatternStep {
  const explicit = entry.pattern_step;
  if (typeof explicit === "string" && isValidStep(explicit)) return explicit;

  const source = String(entry.source || "");
  const action = String(entry.action || "");
  const trigger = String(entry.trigger || entry.event || "");
  const phaseNum = entry.phase_number as number | undefined;
  const phaseKey = String(entry.phase_key || "");

  if (
    action === "pivot_chain" ||
    action === "reinitiate_chain" ||
    trigger.includes("pathway") ||
    entry.pathway_id
  ) {
    return "pivot";
  }
  if (
    action === "patch_chain" ||
    (source === "live_council" && action && action !== "pause" && action !== "abort")
  ) {
    return "commit";
  }
  if (source === "council_turn" || entry.failure_class) return "evaluate";
  if (source === "guided_autonomous" && (entry.narrative || entry.artifact_text)) {
    return "reflect";
  }
  if (phaseKey === "identify" || phaseNum === 1) return "orient";
  if (
    trigger.includes("scan") ||
    entry.scan_type ||
    entry.hub_operation ||
    entry.external_tool ||
    source === "tool_executor" ||
    (source === "guided_autonomous" && phaseNum != null && phaseNum <= 4 && !entry.narrative)
  ) {
    return "probe";
  }
  if (phaseNum != null && phaseNum <= 3) return "hypothesize";
  if (source === "coordinator") return "evaluate";
  return "orient";
}

/** Infer which subtask index an entry most closely maps to (for [think] lines + checklist). */
export function inferSubtaskIndex(
  entry: ReasoningTraceEntry,
  step: ThoughtPatternStep
): number | undefined {
  const explicit = entry.subtask_id;
  if (typeof explicit === "string") {
    const m = explicit.match(/^[^:]+:(\d+)$/);
    if (m) return Number(m[1]);
  }

  const source = String(entry.source || "");
  const action = String(entry.action || "");
  const trigger = String(entry.trigger || entry.event || "");
  const phaseKey = String(entry.phase_key || "");

  switch (step) {
    case "orient":
      if (entry.target || phaseKey === "identify") return 0;
      if (entry.scope || entry.roe) return 2;
      if (entry.objectives) return 3;
      return 0;
    case "hypothesize":
      if (entry.attack_vectors) return 0;
      if (entry.crown_jewels) return 1;
      if (entry.threat_model) return 2;
      if (phaseKey || entry.phase_number != null) return 3;
      return 0;
    case "probe":
      if (entry.external_tool || trigger.includes("tool_executor") || source === "tool_executor") {
        return 2;
      }
      if (trigger.includes("osint") || trigger.includes("passive")) return 0;
      if (entry.scan_type || trigger.includes("scan") || entry.invoke_scan) return 1;
      if (entry.hub_operation || trigger.includes("nmap") || trigger.includes("nuclei")) return 2;
      if (trigger.includes("social") || trigger.includes("influence")) return 3;
      if (entry.ts || entry.note) return 4;
      if (entry.hub_operation) return 2;
      return 1;
    case "evaluate":
      if (source === "council_turn") return 3;
      if (entry.failure_class) return 2;
      if (entry.opsec || trigger.includes("opsec")) return 1;
      if (entry.confidence != null) return 4;
      return 0;
    case "pivot":
      if (action === "pivot_chain" || action === "reinitiate_chain") return 1;
      if (entry.pathway_id) return 1;
      if (entry.scope_adjustment) return 2;
      if (entry.ttp || trigger.includes("retry")) return 3;
      return 0;
    case "commit":
      if (action === "patch_chain") return 0;
      if (entry.persistence) return 1;
      if (entry.lateral || trigger.includes("escalat")) return 2;
      if (entry.exfil) return 3;
      if (action === "continue" || action === "expand" || action === "abort") return 4;
      return 4;
    case "reflect":
      if (entry.lessons_learned) return 1;
      if (entry.playbook || entry.threat_model) return 2;
      if (entry.feed_orient) return 3;
      if (entry.narrative || entry.artifact_text) return 0;
      return 0;
    default:
      return undefined;
  }
}

export function inferSubtaskId(entry: ReasoningTraceEntry, step?: ThoughtPatternStep): string | undefined {
  const stage = step ?? inferPatternStep(entry);
  const idx = inferSubtaskIndex(entry, stage);
  if (idx == null) return undefined;
  return subtaskId(stage, idx);
}

/** Format terminal / panel [think] line with optional subtask id. */
export function formatThinkLine(opts: {
  stage: string;
  rationale?: string;
  subtaskId?: string;
  action?: string;
  fallback?: string;
}): string {
  const { stage, rationale, subtaskId: stId, action, fallback } = opts;
  const prefix = stId ? `[think] ${stage} · ${stId}` : `[think] ${stage}`;
  const actionBit = action ? ` · ${action}` : "";
  if (rationale) return `${prefix}${actionBit} — ${rationale}`;
  return `${prefix}${actionBit} — ${fallback || "reasoning"}`;
}

export function entryStageLabel(entry: ReasoningTraceEntry): string {
  if (typeof entry.stage === "string" && entry.stage) return entry.stage;
  return STAGE_LABELS[inferPatternStep(entry)];
}

export function entryRationale(entry: ReasoningTraceEntry): string {
  if (entry.rationale) return String(entry.rationale);
  if (entry.narrative) return String(entry.narrative);
  if (entry.note) return String(entry.note);
  const steps = entry.rationale_steps as Array<{ step: string; detail: string }> | undefined;
  if (steps?.length) {
    return steps.map((s) => `${s.step}: ${s.detail}`).join(" · ");
  }
  return "";
}

export interface ThoughtStreamItem {
  id: string;
  ts: string;
  step: ThoughtPatternStep;
  stage: string;
  text: string;
  subtaskId?: string;
  source?: string;
  turn?: number;
  alternatePathways?: string[];
}

export function traceToThoughtItems(trace: ReasoningTraceEntry[] | undefined): ThoughtStreamItem[] {
  if (!trace?.length) return [];
  return trace.map((entry, i) => {
    const step = inferPatternStep(entry);
    return {
      id: `${entry.ts || i}-${entry.source}-${entry.turn ?? ""}`,
      ts: entry.ts || new Date().toISOString(),
      step,
      stage: entryStageLabel(entry),
      text: entryRationale(entry) || entryStageLabel(entry),
      subtaskId: inferSubtaskId(entry, step),
      source: entry.source as string | undefined,
      turn: typeof entry.turn === "number" ? entry.turn : undefined,
      alternatePathways: Array.isArray(entry.alternate_pathways)
        ? (entry.alternate_pathways as string[])
        : undefined,
    };
  });
}

export function councilEventToThought(event: CouncilWsEvent): ThoughtStreamItem | null {
  const ts = event.timestamp || new Date().toISOString();
  if (event.type === "reasoning_thought" && event.thought) {
    const t = event.thought;
    const step = inferPatternStep(t);
    return {
      id: `ws-thought-${t.ts}-${step}`,
      ts: t.ts || ts,
      step,
      stage: entryStageLabel(t),
      text: entryRationale(t) || entryStageLabel(t),
      subtaskId:
        typeof t.subtask_id === "string" ? t.subtask_id : inferSubtaskId(t, step),
      source: t.source as string | undefined,
      turn: typeof t.turn === "number" ? t.turn : undefined,
      alternatePathways: Array.isArray(t.alternate_pathways)
        ? (t.alternate_pathways as string[])
        : undefined,
    };
  }
  if (event.type === "council_agent_memo") {
    const memo = event.memo;
    const summary =
      typeof memo?.summary === "string"
        ? memo.summary
        : typeof memo?.recommendation === "string"
          ? memo.recommendation
          : typeof memo?.assessment === "string"
            ? memo.assessment
            : "";
    return {
      id: `memo-${event.turn}-${event.agent}-${ts}`,
      ts,
      step: event.agent === "conductor" ? "commit" : "evaluate",
      stage: event.agent === "conductor" ? "Commit" : "Evaluate",
      text: summary || `${event.agent} memo`,
      subtaskId: subtaskId(event.agent === "conductor" ? "commit" : "evaluate", 3),
      source: `council:${event.agent}`,
      turn: event.turn,
    };
  }
  if (event.type === "live_directive" || event.type === "approval_required") {
    const d = event.directive;
    const step: ThoughtPatternStep =
      d.action === "pivot_chain" || d.action === "reinitiate_chain"
        ? "pivot"
        : d.action === "continue"
          ? "commit"
          : "evaluate";
    return {
      id: `directive-${d.directive_id || d.turn}-${ts}`,
      ts,
      step,
      stage: STAGE_LABELS[step],
      text: d.rationale || d.action || "Council directive",
      subtaskId: subtaskId(step, step === "commit" ? 4 : step === "pivot" ? 1 : 3),
      source: "conductor",
      turn: d.turn,
      alternatePathways: Array.isArray(d.alternate_chain_indices)
        ? d.alternate_chain_indices.map((i) => `chain-${i}`)
        : undefined,
    };
  }
  if (event.type === "pathway_approval_required") {
    return {
      id: `pathway-${ts}`,
      ts,
      step: "pivot",
      stage: "Pivot",
      text:
        event.pathway?.label ||
        `Alternate pathway: ${event.pathway?.method || event.task_kind || "pending"}`,
      subtaskId: subtaskId("pivot", 1),
      source: "pathway",
    };
  }
  return null;
}

/** Heuristic subtask checklist for a stage from trace + run context. */
export function resolveSubtaskProgress(opts: {
  stageId: ThoughtPatternStep;
  reasoningTrace?: ReasoningTraceEntry[];
  currentPhase?: number;
  targetSet?: boolean;
  liveCouncil?: LiveCouncilState;
}): SubtaskProgress[] {
  const { stageId, reasoningTrace, currentPhase, targetSet, liveCouncil } = opts;
  const stage = getStageById(stageId);
  if (!stage) return [];

  const completed = new Set<number>();
  const inProgress = new Set<number>();

  for (const entry of reasoningTrace ?? []) {
    if (inferPatternStep(entry) !== stageId) continue;
    const idx = inferSubtaskIndex(entry, stageId);
    if (idx == null) continue;
    completed.add(idx);
  }

  if (stageId === "orient" && targetSet) {
    completed.add(0);
    inProgress.add(1);
  }
  if (stageId === "hypothesize" && currentPhase != null && currentPhase >= 2) {
    completed.add(0);
    inProgress.add(3);
  }
  if (stageId === "probe") {
    const hasScan = (reasoningTrace ?? []).some(
      (e) => e.scan_type || e.hub_operation || String(e.trigger || "").includes("scan")
    );
    const hasExternalTool = (reasoningTrace ?? []).some(
      (e) =>
        e.external_tool ||
        e.source === "tool_executor" ||
        String(e.plugin || "").length > 0
    );
    if (hasScan) {
      completed.add(1);
      inProgress.add(4);
    }
    if (hasExternalTool) {
      completed.add(2);
      inProgress.add(4);
    }
  }
  if (stageId === "evaluate" && (liveCouncil?.state === "analyzing" || liveCouncil?.analysis_lock)) {
    inProgress.add(3);
  }
  if (stageId === "pivot" && (liveCouncil?.pending_pathway || liveCouncil?.pending_directive?.action === "pivot_chain")) {
    inProgress.add(1);
  }
  if (stageId === "commit" && liveCouncil?.pending_directive && liveCouncil.pending_directive.action !== "pivot_chain") {
    inProgress.add(4);
  }

  return stage.subtasks.map((label, index) => {
    let status: SubtaskStatus = "pending";
    if (completed.has(index)) status = "complete";
    else if (inProgress.has(index)) status = "in_progress";
    return { id: subtaskId(stageId, index), label, status };
  });
}

/** Current pattern step from trace, council state, and guided phase */
export function resolveCurrentPatternStep(opts: {
  reasoningTrace?: ReasoningTraceEntry[];
  liveCouncil?: LiveCouncilState;
  currentPhase?: number;
  targetSet?: boolean;
}): ThoughtPatternStep {
  const { reasoningTrace, liveCouncil, currentPhase, targetSet } = opts;

  if (liveCouncil?.pending_pathway || liveCouncil?.pending_directive?.action === "pivot_chain") {
    return "pivot";
  }
  if (liveCouncil?.pending_directive) return "evaluate";
  if (liveCouncil?.state === "analyzing" || liveCouncil?.analysis_lock) return "evaluate";

  const last = reasoningTrace?.[reasoningTrace.length - 1];
  if (last) return inferPatternStep(last);

  if (currentPhase != null && currentPhase >= 1 && currentPhase <= 3) return "hypothesize";
  if (currentPhase != null && currentPhase >= 4) return "probe";
  if (targetSet) return "orient";
  return "orient";
}

export function stepIndex(step: ThoughtPatternStep): number {
  return STEP_ORDER[step] ?? getStageIndex(step);
}

export function mergeThoughtStream(
  trace: ReasoningTraceEntry[] | undefined,
  councilEvents: CouncilWsEvent[] | undefined
): ThoughtStreamItem[] {
  const fromTrace = traceToThoughtItems(trace);
  const fromWs =
    councilEvents
      ?.map(councilEventToThought)
      .filter((x): x is ThoughtStreamItem => x != null) ?? [];
  const merged = [...fromTrace, ...fromWs];
  const seen = new Set<string>();
  return merged.filter((item) => {
    if (seen.has(item.id)) return false;
    seen.add(item.id);
    return true;
  });
}
