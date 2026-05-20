import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  hotkeyActionForToken,
  hotkeyToken,
  deriveSuggestedHotkey,
} from "./hotkeys";
import {
  runStageTransition,
  STAGE_TRANSITION_TEMPLATES,
  stageForHotkeyIndex,
} from "./stageTransitionTemplates";
import { DIRECTIVE_TEMPLATE_BY_ID, resolveSuggestedDirectiveTemplate } from "./directiveTemplates";
import { runTemplate } from "./templaterRunner";

describe("templater hotkeys", () => {
  it("maps Shift+1 to orient stage", () => {
    assert.equal(stageForHotkeyIndex(1), "orient");
    assert.equal(stageForHotkeyIndex(7), "reflect");
    assert.equal(stageForHotkeyIndex(0), null);
  });

  it("parses hotkey tokens", () => {
    assert.equal(hotkeyToken({ key: "a", shiftKey: false, metaKey: false, ctrlKey: false, altKey: false } as KeyboardEvent), "A");
    assert.equal(hotkeyToken({ key: "Enter", shiftKey: false, metaKey: false, ctrlKey: false, altKey: false } as KeyboardEvent), "Enter");
    assert.equal(hotkeyToken({ key: "1", shiftKey: true, metaKey: false, ctrlKey: false, altKey: false } as KeyboardEvent), "Shift+1");
  });

  it("resolves approve action when directive pending", () => {
    const action = hotkeyActionForToken("A", {
      liveCouncil: {
        pending_directive: { directive_id: "d1", action: "pivot_chain" },
      },
    });
    assert.equal(action?.kind, "approve");
    assert.equal(action?.templateId, "pivot_chain");
  });

  it("derives pivot suggestion for pending pathway", () => {
    const suggested = deriveSuggestedHotkey({
      pending_pathway: { pathway: { label: "Alternate scanner route" } },
    });
    assert.ok(suggested);
    assert.equal(suggested?.templateId, "pivot_chain");
    assert.match(suggested?.message ?? "", /Alternate scanner route/);
  });
});

describe("stage transition templates", () => {
  it("defines seven stage templates", () => {
    assert.equal(STAGE_TRANSITION_TEMPLATES.length, 7);
  });

  it("runStageTransition emits think lines", () => {
    const result = runStageTransition("orient", "hypothesize", { trigger: "test" });
    assert.equal(result.from, "orient");
    assert.equal(result.to, "hypothesize");
    assert.ok(result.thinkLines.length >= 1);
    assert.ok(result.systemLines.some((l) => l.includes("Orient → Hypothesize")));
  });
});

describe("templater runner", () => {
  it("runs force_replan template", async () => {
    const systemLines: string[] = [];
    let replanned = false;
    await runTemplate("force_replan", {
      engagementId: "eng-1",
      currentStage: "evaluate",
      onSystemLine: (line) => systemLines.push(line.content),
      onForceReplan: async () => {
        replanned = true;
      },
    });
    assert.equal(replanned, true);
    assert.ok(systemLines.some((l) => l.includes("[think]")));
  });

  it("resolves continue template for continue directive", () => {
    const tpl = resolveSuggestedDirectiveTemplate({
      pending_directive: { directive_id: "d2", action: "continue" },
    });
    assert.equal(tpl?.id, "continue");
    assert.equal(DIRECTIVE_TEMPLATE_BY_ID.continue?.hotkey, "C");
  });
});
