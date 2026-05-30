import type { SystemFeedLine } from "@/components/attack-monitoring/TerminalOutput";
import type { LiveCouncilState } from "@/lib/liveCouncil";
import type { ThoughtCycleStageId } from "@/lib/thoughtProcessPattern";
import {
  DIRECTIVE_TEMPLATE_BY_ID,
  thinkLineForDirective,
  type DirectiveTemplate,
} from "./directiveTemplates";
import {
  runStageTransition,
  STAGE_TEMPLATE_BY_ID,
  STAGE_TEMPLATE_BY_STAGE,
  type StageTransitionTemplate,
} from "./stageTransitionTemplates";

export interface TemplaterRunContext {
  engagementId: string;
  currentStage?: ThoughtCycleStageId;
  liveCouncil?: LiveCouncilState | null;
  userNote?: string;
  pathwayLabel?: string;
  onSystemLine?: (line: SystemFeedLine) => void;
  onApprove?: () => void | Promise<void>;
  onForceReplan?: () => void | Promise<void>;
}

export interface TemplaterRunResult {
  templateId: string;
  thinkLines: string[];
  systemLines: string[];
  apiAction?: "approve" | "force_replan" | "abort" | "continue" | "none";
  stageTransition?: { from: ThoughtCycleStageId; to: ThoughtCycleStageId };
}

function pushSystemLines(
  ctx: TemplaterRunContext,
  lines: string[],
  prefix: string,
  type: SystemFeedLine["type"] = "info"
) {
  for (const content of lines) {
    ctx.onSystemLine?.({
      key: `${prefix}-${ctx.engagementId}-${content.slice(0, 48)}-${Date.now()}`,
      type,
      content,
    });
  }
}

async function runDirectiveTemplate(
  template: DirectiveTemplate,
  ctx: TemplaterRunContext
): Promise<TemplaterRunResult> {
  const pending = ctx.liveCouncil?.pending_directive;
  const thinkLines = [thinkLineForDirective(template, pending ?? undefined)];
  const systemLines = [`[think] directive · ${template.label}${ctx.userNote ? ` — ${ctx.userNote}` : ""}`];

  pushSystemLines(ctx, thinkLines, "templater-think", "info");
  pushSystemLines(ctx, systemLines, "templater-sys", "council");

  if (template.apiAction === "approve") {
    await ctx.onApprove?.();
  } else if (template.apiAction === "force_replan") {
    await ctx.onForceReplan?.();
  }

  let stageTransition: TemplaterRunResult["stageTransition"];
  if (template.stage && ctx.currentStage && template.stage !== ctx.currentStage) {
    const tr = runStageTransition(ctx.currentStage, template.stage, {
      trigger: template.id,
      userNote: ctx.userNote,
    });
    pushSystemLines(ctx, tr.systemLines, "templater-stage", "info");
    stageTransition = { from: tr.from, to: tr.to };
  }

  return {
    templateId: template.id,
    thinkLines,
    systemLines,
    apiAction: template.apiAction,
    stageTransition,
  };
}

async function runStageTemplate(
  template: StageTransitionTemplate,
  ctx: TemplaterRunContext,
  targetStage: ThoughtCycleStageId
): Promise<TemplaterRunResult> {
  const from = ctx.currentStage ?? template.stage;
  const tr = runStageTransition(from, targetStage, {
    trigger: template.id,
    userNote: ctx.userNote,
  });

  pushSystemLines(ctx, tr.thinkLines, "templater-think", "info");
  pushSystemLines(ctx, tr.systemLines, "templater-stage", "info");

  return {
    templateId: template.id,
    thinkLines: tr.thinkLines,
    systemLines: tr.systemLines,
    apiAction: "none",
    stageTransition: { from: tr.from, to: tr.to },
  };
}

/** Execute a templater script by id (stage_* or directive template id). */
export async function runTemplate(
  templateId: string,
  ctx: TemplaterRunContext
): Promise<TemplaterRunResult | null> {
  const stageTpl = STAGE_TEMPLATE_BY_ID[templateId];
  if (stageTpl) {
    return runStageTemplate(stageTpl, ctx, stageTpl.stage);
  }

  const directiveTpl = DIRECTIVE_TEMPLATE_BY_ID[templateId];
  if (directiveTpl) {
    return runDirectiveTemplate(directiveTpl, ctx);
  }

  return null;
}

/** Jump between cycle stages — runs onExit/onEnter scripts and emits [think] lines. */
export async function runStageTransitionTemplate(
  from: ThoughtCycleStageId,
  to: ThoughtCycleStageId,
  ctx: TemplaterRunContext
): Promise<TemplaterRunResult> {
  const tr = runStageTransition(from, to, { userNote: ctx.userNote });
  pushSystemLines(ctx, tr.thinkLines, "templater-think", "info");
  pushSystemLines(ctx, tr.systemLines, "templater-stage", "info");

  return {
    templateId: STAGE_TEMPLATE_BY_STAGE[to]?.id ?? `stage_${to}`,
    thinkLines: tr.thinkLines,
    systemLines: tr.systemLines,
    apiAction: "none",
    stageTransition: { from, to },
  };
}
