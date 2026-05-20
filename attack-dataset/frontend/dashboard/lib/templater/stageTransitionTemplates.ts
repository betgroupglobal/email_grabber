import {
  STAGE_LABELS,
  THOUGHT_PROCESS_CYCLE,
  formatThinkLine,
  getNextStage,
  getStageById,
  type ThoughtCycleStageId,
} from "@/lib/thoughtProcessPattern";

export interface TemplateScriptAction {
  type: "log_think" | "emit_system";
  message: string;
  stage?: ThoughtCycleStageId;
}

export interface StageTransitionTemplate {
  id: string;
  stage: ThoughtCycleStageId;
  objective: string;
  onEnter: TemplateScriptAction[];
  onExit: TemplateScriptAction[];
  nextStage: ThoughtCycleStageId | null;
}

export const STAGE_TRANSITION_TEMPLATES: StageTransitionTemplate[] = THOUGHT_PROCESS_CYCLE.map(
  (s) => ({
    id: `stage_${s.id}`,
    stage: s.id,
    objective: s.objective,
    onEnter: [
      {
        type: "log_think",
        stage: s.id,
        message: formatThinkLine({
          stage: s.stage,
          subtaskId: `${s.id}:0`,
          fallback: s.objective,
        }),
      },
    ],
    onExit: [
      {
        type: "log_think",
        stage: s.id,
        message: formatThinkLine({
          stage: s.stage,
          action: "complete",
          fallback: `Stage ${s.stage} complete — advancing`,
        }),
      },
    ],
    nextStage: getNextStage(s.id),
  })
);

export const STAGE_TEMPLATE_BY_ID = Object.fromEntries(
  STAGE_TRANSITION_TEMPLATES.map((t) => [t.id, t])
) as Record<string, StageTransitionTemplate>;

export const STAGE_TEMPLATE_BY_STAGE = Object.fromEntries(
  STAGE_TRANSITION_TEMPLATES.map((t) => [t.stage, t])
) as Record<ThoughtCycleStageId, StageTransitionTemplate>;

export interface StageTransitionResult {
  from: ThoughtCycleStageId;
  to: ThoughtCycleStageId;
  thinkLines: string[];
  systemLines: string[];
}

/** Run onExit(from) + onEnter(to) templater scripts for a manual or auto stage jump. */
export function runStageTransition(
  from: ThoughtCycleStageId,
  to: ThoughtCycleStageId,
  opts?: { trigger?: string; userNote?: string }
): StageTransitionResult {
  const fromTpl = STAGE_TEMPLATE_BY_STAGE[from];
  const toTpl = STAGE_TEMPLATE_BY_STAGE[to];
  const fromLabel = STAGE_LABELS[from];
  const toLabel = STAGE_LABELS[to];
  const thinkLines: string[] = [];
  const systemLines: string[] = [];

  if (fromTpl) {
    for (const action of fromTpl.onExit) {
      if (action.type === "log_think") thinkLines.push(action.message);
    }
  }

  if (toTpl) {
    for (const action of toTpl.onEnter) {
      if (action.type === "log_think") thinkLines.push(action.message);
    }
  }

  const trigger = opts?.trigger ? ` · ${opts.trigger}` : "";
  const note = opts?.userNote?.trim();
  systemLines.push(
    `[think] transition · ${fromLabel} → ${toLabel}${trigger}${note ? ` — ${note}` : ""}`
  );

  if (toTpl) {
    thinkLines.push(
      formatThinkLine({
        stage: getStageById(to)?.stage ?? toLabel,
        subtaskId: `${to}:0`,
        action: "enter",
        fallback: toTpl.objective,
      })
    );
  }

  return { from, to, thinkLines, systemLines };
}

/** Map Shift+1…Shift+7 to cycle stage ids (Orient…Reflect). */
export const STAGE_HOTKEY_INDEX: ThoughtCycleStageId[] = THOUGHT_PROCESS_CYCLE.map((s) => s.id);

export function stageForHotkeyIndex(index: number): ThoughtCycleStageId | null {
  if (index < 1 || index > STAGE_HOTKEY_INDEX.length) return null;
  return STAGE_HOTKEY_INDEX[index - 1] ?? null;
}
