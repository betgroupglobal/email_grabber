import type { LiveCouncilState } from "@/lib/liveCouncil";
import type { ThoughtCycleStageId } from "@/lib/thoughtProcessPattern";
import {
  DIRECTIVE_TEMPLATE_BY_ID,
  resolveSuggestedDirectiveTemplate,
  type DirectiveTemplate,
} from "./directiveTemplates";
import { stageForHotkeyIndex } from "./stageTransitionTemplates";

export type HotkeyActionKind =
  | "approve"
  | "force_replan"
  | "pivot"
  | "continue"
  | "abort"
  | "stage_transition";

export interface HotkeyAction {
  kind: HotkeyActionKind;
  templateId: string;
  hotkey: string;
  label: string;
  targetStage?: ThoughtCycleStageId;
}

export interface SuggestedHotkeyPrompt {
  hotkey: string;
  hotkeyLabel: string;
  templateId: string;
  message: string;
  suggested_hotkey?: string;
  suggested_template_id?: string;
}

function isTypingTarget(target: EventTarget | null): boolean {
  if (!target || !(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || target.isContentEditable;
}

/** Normalize keyboard event to a comparable hotkey token. */
export function hotkeyToken(event: KeyboardEvent): string | null {
  if (event.metaKey || event.ctrlKey || event.altKey) return null;

  if (event.key === "Escape") return "Esc";
  if (event.key === "Enter") return "Enter";

  if (event.shiftKey && event.key >= "1" && event.key <= "7") {
    return `Shift+${event.key}`;
  }

  if (!event.shiftKey && /^[a-zA-Z]$/.test(event.key)) {
    return event.key.toUpperCase();
  }

  return null;
}

export function hotkeyActionForToken(
  token: string,
  opts: {
    liveCouncil?: LiveCouncilState | null;
    currentStage?: ThoughtCycleStageId;
    hasPendingDirective?: boolean;
    hasPendingPathway?: boolean;
  }
): HotkeyAction | null {
  const pending = opts.liveCouncil?.pending_directive;
  const pathway = opts.hasPendingPathway ?? Boolean(opts.liveCouncil?.pending_pathway);

  if (token.startsWith("Shift+")) {
    const idx = Number(token.replace("Shift+", ""));
    const targetStage = stageForHotkeyIndex(idx);
    if (!targetStage) return null;
    return {
      kind: "stage_transition",
      templateId: `stage_${targetStage}`,
      hotkey: token,
      label: `Jump to ${targetStage}`,
      targetStage,
    };
  }

  if (token === "A" || token === "Enter") {
    if (!pending && !pathway) return null;
    const tpl =
      pending?.action === "pivot_chain" || pending?.action === "reinitiate_chain"
        ? DIRECTIVE_TEMPLATE_BY_ID.pivot_chain
        : pending?.action
          ? DIRECTIVE_TEMPLATE_BY_ID[pending.action] ?? DIRECTIVE_TEMPLATE_BY_ID.approve_council
          : DIRECTIVE_TEMPLATE_BY_ID.pivot_chain;
    if (!tpl) return null;
    return {
      kind: "approve",
      templateId: tpl.id,
      hotkey: token,
      label: tpl.label,
    };
  }

  if (token === "R") {
    return {
      kind: "force_replan",
      templateId: "force_replan",
      hotkey: "R",
      label: DIRECTIVE_TEMPLATE_BY_ID.force_replan?.label ?? "Force replan",
    };
  }

  if (token === "P") {
    if (!pending && !pathway) return null;
    const action = pending?.action;
    const tpl =
      action === "reinitiate_chain"
        ? DIRECTIVE_TEMPLATE_BY_ID.reinitiate_chain
        : DIRECTIVE_TEMPLATE_BY_ID.pivot_chain;
    if (!tpl) return null;
    return {
      kind: "pivot",
      templateId: tpl.id,
      hotkey: "P",
      label: tpl.label,
    };
  }

  if (token === "C") {
    if (pending) {
      const tpl =
        pending.action === "patch_chain"
          ? DIRECTIVE_TEMPLATE_BY_ID.patch_chain
          : DIRECTIVE_TEMPLATE_BY_ID.continue;
      if (!tpl) return null;
      return {
        kind: "continue",
        templateId: tpl.id,
        hotkey: "C",
        label: tpl.label,
      };
    }
    return {
      kind: "continue",
      templateId: "execute_chain",
      hotkey: "C",
      label: DIRECTIVE_TEMPLATE_BY_ID.execute_chain?.label ?? "Continue",
    };
  }

  if (token === "Esc") {
    if (!pending) return null;
    const tpl =
      pending.action === "pause" || pending.opsec_veto
        ? DIRECTIVE_TEMPLATE_BY_ID.pause
        : DIRECTIVE_TEMPLATE_BY_ID.reject_abort;
    if (!tpl) return null;
    return {
      kind: "abort",
      templateId: tpl.id,
      hotkey: "Esc",
      label: tpl.label,
    };
  }

  return null;
}

export function resolveHotkeyAction(
  event: KeyboardEvent,
  opts: Parameters<typeof hotkeyActionForToken>[1]
): HotkeyAction | null {
  if (isTypingTarget(event.target)) return null;
  const token = hotkeyToken(event);
  if (!token) return null;
  return hotkeyActionForToken(token, opts);
}

/** AI-facing prompt: which hotkey the operator should press next. */
export function deriveSuggestedHotkey(
  liveCouncil?: LiveCouncilState | null
): SuggestedHotkeyPrompt | null {
  const tpl = resolveSuggestedDirectiveTemplate(liveCouncil);
  if (!tpl) return null;

  const pending = liveCouncil?.pending_directive;
  const pathwayLabel =
    liveCouncil?.pending_pathway?.pathway?.label ||
    liveCouncil?.pending_pathway?.pathway?.method;

  const message = tpl.prompt({ directive: pending ?? undefined, pathwayLabel });
  return {
    hotkey: tpl.hotkey,
    hotkeyLabel: tpl.hotkeyLabel,
    templateId: tpl.id,
    message,
    suggested_hotkey: tpl.hotkey,
    suggested_template_id: tpl.id,
  };
}

/** Compact legend rows for the hotkey hint bar. */
export function hotkeyLegend(opts: {
  liveCouncil?: LiveCouncilState | null;
  showStageHotkeys?: boolean;
}): Array<{ keys: string; label: string }> {
  const rows: Array<{ keys: string; label: string }> = [];
  const suggested = deriveSuggestedHotkey(opts.liveCouncil);

  if (suggested) {
    rows.push({
      keys: suggested.hotkeyLabel,
      label: suggested.message,
    });
  }

  if (opts.liveCouncil?.pending_directive || opts.liveCouncil?.pending_pathway) {
    rows.push({ keys: "A / Enter", label: "Approve pending directive" });
    if (
      opts.liveCouncil.pending_directive?.action === "pivot_chain" ||
      opts.liveCouncil.pending_directive?.action === "reinitiate_chain" ||
      opts.liveCouncil.pending_pathway
    ) {
      rows.push({ keys: "P", label: "Pivot / alternate pathway" });
    }
    rows.push({ keys: "Esc", label: "Abort or pause" });
  }

  rows.push({ keys: "R", label: "Force replan" });
  rows.push({ keys: "C", label: "Continue / commit step" });

  if (opts.showStageHotkeys !== false) {
    rows.push({ keys: "Shift+1–7", label: "Jump thought-cycle stage" });
  }

  return rows;
}

export function suggestedFromDirectiveFields(directive: {
  suggested_hotkey?: string;
  suggested_template_id?: string;
  action?: string;
}): SuggestedHotkeyPrompt | null {
  if (directive.suggested_hotkey && directive.suggested_template_id) {
    const tpl = DIRECTIVE_TEMPLATE_BY_ID[directive.suggested_template_id] as DirectiveTemplate | undefined;
    return {
      hotkey: directive.suggested_hotkey,
      hotkeyLabel: tpl?.hotkeyLabel ?? directive.suggested_hotkey,
      templateId: directive.suggested_template_id,
      message: tpl?.label ?? directiveActionFallback(directive.action),
      suggested_hotkey: directive.suggested_hotkey,
      suggested_template_id: directive.suggested_template_id,
    };
  }
  return null;
}

function directiveActionFallback(action?: string): string {
  if (!action) return "Approve directive";
  return `Approve ${action.replace(/_/g, " ")}`;
}
