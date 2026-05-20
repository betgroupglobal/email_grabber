"use strict";

const { describe, it } = require("node:test");
const assert = require("node:assert/strict");
const {
  applyPatchDirective,
  applyPivotDirective,
  mergeChainSteps,
} = require("../chain-versioning");
const {
  applyCouncilDirective,
  enrichDirectiveHotkeyHints,
} = require("../directive-applier");

describe("chain-versioning directives", () => {
  it("mergeChainSteps keeps prefix and appends new steps", () => {
    const merged = mergeChainSteps(
      [{ step: { phase: "recon", attack: { title: "A" } } }],
      [{ phase: "exploit", attack: { title: "B" } }],
      1
    );
    assert.equal(merged.length, 2);
    assert.equal(merged[0].phase, "recon");
    assert.equal(merged[1].phase, "exploit");
  });

  it("applyPivotDirective switches active chain index", () => {
    const eng = {
      attack_chains: {
        version: 0,
        active_chain_index: 0,
        chains: [
          { steps: [{ phase: "a" }] },
          { steps: [{ phase: "b" }] },
        ],
        history: [],
      },
    };
    const directive = {
      directive_id: "d1",
      action: "pivot_chain",
      rationale: "test pivot",
      updated_steps: [{ phase: "exploit", attack: { title: "X", id: 1 } }],
      pivot_chain_index: 1,
    };
    const result = applyPivotDirective(eng, directive);
    assert.equal(result.chain_index, 1);
    assert.equal(eng.attack_chains.active_chain_index, 1);
    assert.equal(eng.attack_chains.version, 1);
  });

  it("applyPatchDirective splices steps at index", () => {
    const eng = {
      attack_chains: {
        version: 0,
        active_chain_index: 0,
        chains: [
          {
            steps: [
              { phase: "recon", attack: { title: "1" } },
              { phase: "exploit", attack: { title: "old" } },
              { phase: "post", attack: { title: "3" } },
            ],
          },
        ],
        history: [],
      },
    };
    const directive = {
      directive_id: "d2",
      action: "patch_chain",
      rationale: "patch",
      from_step_index: 1,
      updated_steps: [{ phase: "exploit", attack: { title: "new", id: 2 } }],
    };
    const result = applyPatchDirective(eng, directive, 0);
    assert.ok(result.merged_steps.some((s) => s.attack?.title === "new"));
  });
});

describe("directive-applier", () => {
  it("enrichDirectiveHotkeyHints maps pivot_chain to P", () => {
    const enriched = enrichDirectiveHotkeyHints({
      directive_id: "d1",
      action: "pivot_chain",
    });
    assert.equal(enriched.suggested_hotkey, "P");
    assert.equal(enriched.suggested_template_id, "pivot_chain");
  });

  it("abort sets engagement status", () => {
    const eng = { status: "executing", attack_chains: { version: 0, chains: [], history: [] } };
    const result = applyCouncilDirective({
      eng,
      directive: {
        directive_id: "x",
        action: "abort",
        rationale: "stop",
      },
      engagementId: "e1",
    });
    assert.equal(result.action, "abort");
    assert.equal(eng.status, "aborted");
  });

  it("continues on opsec veto when ALLOW_HIGH_RISK=true", () => {
    const prev = process.env.ALLOW_HIGH_RISK;
    process.env.ALLOW_HIGH_RISK = "true";
    delete require.cache[require.resolve("../directive-applier")];
    const { applyCouncilDirective: apply } = require("../directive-applier");

    const lines = [];
    const eng = {
      status: "executing",
      live_council: {},
      attack_chains: { version: 0, chains: [], history: [] },
    };
    const result = apply({
      eng,
      directive: {
        directive_id: "v1",
        action: "pause",
        opsec_veto: true,
        rationale: "high risk",
      },
      engagementId: "e1",
      broadcastTerminal: (_id, msg) => lines.push(msg),
    });
    assert.equal(result.action, "continue");
    assert.equal(eng.status, "executing");
    assert.ok(lines.some((l) => l.includes("continuing")));

    process.env.ALLOW_HIGH_RISK = prev;
    delete require.cache[require.resolve("../directive-applier")];
  });
});
