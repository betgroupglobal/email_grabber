export {
  STAGE_TRANSITION_TEMPLATES,
  STAGE_TEMPLATE_BY_ID,
  STAGE_TEMPLATE_BY_STAGE,
  STAGE_HOTKEY_INDEX,
  runStageTransition,
  stageForHotkeyIndex,
  type StageTransitionTemplate,
  type StageTransitionResult,
  type TemplateScriptAction,
} from "./stageTransitionTemplates";

export {
  DIRECTIVE_TEMPLATES,
  DIRECTIVE_TEMPLATE_BY_ID,
  templateForDirectiveAction,
  resolveSuggestedDirectiveTemplate,
  thinkLineForDirective,
  type DirectiveTemplate,
  type DirectiveApiAction,
} from "./directiveTemplates";

export {
  runTemplate,
  runStageTransitionTemplate,
  type TemplaterRunContext,
  type TemplaterRunResult,
} from "./templaterRunner";

export {
  hotkeyToken,
  hotkeyActionForToken,
  resolveHotkeyAction,
  deriveSuggestedHotkey,
  hotkeyLegend,
  suggestedFromDirectiveFields,
  type HotkeyAction,
  type HotkeyActionKind,
  type SuggestedHotkeyPrompt,
} from "./hotkeys";
