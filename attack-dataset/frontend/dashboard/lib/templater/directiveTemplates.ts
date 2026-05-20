import { directiveActionLabel, type LiveCouncilState } from "@/lib/liveCouncil";
import type { LiveDirective } from "@/lib/liveCouncilSchema";
import { formatThinkLine, type ThoughtCycleStageId } from "@/lib/thoughtProcessPattern";

export type DirectiveApiAction =
  | "approve"
  | "force_replan"
  | "abort"
  | "continue"
  | "none";

export interface DirectiveTemplate {
  id: string;
  /** Maps to LiveDirective.action or synthetic ops (approve_council, force_replan). */
  directiveAction: string;
  hotkey: string;
  hotkeyLabel: string;
  label: string;
  stage?: ThoughtCycleStageId;
  apiAction: DirectiveApiAction;
  prompt: (ctx?: { directive?: LiveDirective; pathwayLabel?: string }) => string;
}

export const DIRECTIVE_TEMPLATES: DirectiveTemplate[] = [
  {
    id: "approve_council",
    directiveAction: "_approve",
    hotkey: "A",
    hotkeyLabel: "A / Enter",
    label: "Approve council directive",
    stage: "commit",
    apiAction: "approve",
    prompt: ({ directive } = {}) =>
      `Approve ${directiveActionLabel(directive?.action || "continue")} directive`,
  },
  {
    id: "reject_abort",
    directiveAction: "abort",
    hotkey: "Esc",
    hotkeyLabel: "Esc",
    label: "Abort / pause execution",
    stage: "evaluate",
    apiAction: "abort",
    prompt: () => "Abort or pause pending execution",
  },
  {
    id: "force_replan",
    directiveAction: "_force_replan",
    hotkey: "R",
    hotkeyLabel: "R",
    label: "Force council replan",
    stage: "evaluate",
    apiAction: "force_replan",
    prompt: () => "Force council to replan attack chain",
  },
  {
    id: "pivot_chain",
    directiveAction: "pivot_chain",
    hotkey: "P",
    hotkeyLabel: "P",
    label: "Pivot to alternate chain",
    stage: "pivot",
    apiAction: "approve",
    prompt: ({ directive, pathwayLabel } = {}) =>
      `Approve pivot${pathwayLabel ? ` to ${pathwayLabel}` : directive?.pivot_chain_index != null ? ` to chain ${directive.pivot_chain_index}` : ""}`,
  },
  {
    id: "reinitiate_chain",
    directiveAction: "reinitiate_chain",
    hotkey: "P",
    hotkeyLabel: "P",
    label: "Reinitiate attack chain",
    stage: "pivot",
    apiAction: "approve",
    prompt: () => "Approve reinitiated attack chain",
  },
  {
    id: "patch_chain",
    directiveAction: "patch_chain",
    hotkey: "C",
    hotkeyLabel: "C",
    label: "Patch current chain",
    stage: "commit",
    apiAction: "approve",
    prompt: () => "Approve chain patch from council",
  },
  {
    id: "continue",
    directiveAction: "continue",
    hotkey: "C",
    hotkeyLabel: "C",
    label: "Continue execution",
    stage: "commit",
    apiAction: "approve",
    prompt: () => "Continue with current attack path",
  },
  {
    id: "execute_chain",
    directiveAction: "_execute_chain",
    hotkey: "C",
    hotkeyLabel: "C",
    label: "Execute / commit current step",
    stage: "commit",
    apiAction: "continue",
    prompt: () => "Commit and execute current chain step",
  },
  {
    id: "pause",
    directiveAction: "pause",
    hotkey: "Esc",
    hotkeyLabel: "Esc",
    label: "Pause execution",
    stage: "evaluate",
    apiAction: "abort",
    prompt: () => "Pause — review OPSEC hold before approving",
  },
];

export const DIRECTIVE_TEMPLATE_BY_ID = Object.fromEntries(
  DIRECTIVE_TEMPLATES.map((t) => [t.id, t])
) as Record<string, DirectiveTemplate>;

export function templateForDirectiveAction(action: string): DirectiveTemplate | undefined {
  return DIRECTIVE_TEMPLATES.find((t) => t.directiveAction === action);
}

export function thinkLineForDirective(template: DirectiveTemplate, directive?: LiveDirective): string {
  const stage = template.stage ?? "commit";
  const stageLabel =
    stage.charAt(0).toUpperCase() + stage.slice(1);
  return formatThinkLine({
    stage: stageLabel,
    action: template.directiveAction,
    fallback: directive?.rationale || template.label,
  });
}

/** Pick the best template for current council / pathway state. */
export function resolveSuggestedDirectiveTemplate(
  liveCouncil?: LiveCouncilState | null
): DirectiveTemplate | null {
  if (!liveCouncil) return null;

  const pending = liveCouncil.pending_directive;
  const pathway = liveCouncil.pending_pathway;

  if (pathway && !pending) {
    return DIRECTIVE_TEMPLATE_BY_ID.pivot_chain ?? null;
  }

  if (!pending) {
    if (liveCouncil.state === "analyzing" || liveCouncil.analysis_lock) {
      return null;
    }
    return DIRECTIVE_TEMPLATE_BY_ID.force_replan ?? null;
  }

  const action = pending.action || "continue";
  if (pending.opsec_veto || action === "pause") {
    return DIRECTIVE_TEMPLATE_BY_ID.pause ?? null;
  }
  if (action === "abort") {
    return DIRECTIVE_TEMPLATE_BY_ID.reject_abort ?? null;
  }

  const byAction = templateForDirectiveAction(action);
  if (byAction) return byAction;

  return DIRECTIVE_TEMPLATE_BY_ID.approve_council ?? null;
}
