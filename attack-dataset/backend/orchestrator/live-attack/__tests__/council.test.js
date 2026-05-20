"use strict";

const { describe, it } = require("node:test");
const assert = require("node:assert/strict");
const { buildDirectiveFromCouncil } = require("../council");

function baseEng(overrides = {}) {
  return {
    live_council: { replans_used: 0, max_replans: 5 },
    attack_chains: {
      active_chain_index: 0,
      chains: [{ steps: [{ phase: "recon" }, { phase: "exploit" }] }],
    },
    ...overrides,
  };
}

function keStep(id, title, tool = "nuclei") {
  return {
    phase: "exploitation",
    attack: { id, title, tools_used: tool, category: "x", attack_type: "exploit" },
    rationale: "test",
    mitre_technique: "T1190",
  };
}

function replanData(chains, scores) {
  return {
    chains,
    alternate_chain_scores: scores,
    dataset_hit_count: 2,
    ml_top_label: "web",
  };
}

describe("buildDirectiveFromCouncil", () => {
  it("returns continue when trigger is step_completed with chains", () => {
    const eng = baseEng();
    const directive = buildDirectiveFromCouncil(
      eng,
      { type: "step_completed", step_number: 2, step: { phase: "exploitation" } },
      { turn: 1, dataset_hits: [{ id: 1, title: "hit" }] },
      [{ agent: "tactical" }, { agent: "opsec", veto: false, risk_score: 0.2 }],
      replanData(
        [{ steps: [keStep(1, "A")], confidence: 0.8 }],
        [0.8]
      ),
      { failure_class: "none" },
      null
    );
    assert.equal(directive.action, "continue");
  });

  it("returns abort when max replans exceeded", () => {
    const eng = baseEng({ live_council: { replans_used: 5, max_replans: 5 } });
    const directive = buildDirectiveFromCouncil(
      eng,
      { type: "step_failed", step_number: 2 },
      { turn: 6 },
      [],
      null,
      { failure_class: "unknown" },
      null
    );
    assert.equal(directive.action, "abort");
  });

  it("returns continue on opsec veto (guardrails disabled)", () => {
    const eng = baseEng();
    const directive = buildDirectiveFromCouncil(
      eng,
      { type: "step_failed", step_number: 2 },
      { turn: 1, dataset_hits: [{ id: 1, detection_method: "IDS alert" }] },
      [{ agent: "opsec", veto: true, risk_score: 0.9, risk_note: "high risk" }],
      replanData([{ steps: [keStep(1, "A")], confidence: 0.8 }], [0.8]),
      { failure_class: "tool_blocked" },
      null
    );
    assert.equal(directive.action, "continue");
    assert.equal(directive.opsec_veto, true);
  });

  it("returns pivot_chain for wrong_vector with alternate chain", () => {
    const eng = baseEng();
    const primary = { steps: [keStep(1, "A", "sqlmap")], confidence: 0.5 };
    const alternate = { steps: [keStep(2, "B", "nuclei")], confidence: 0.85 };
    const directive = buildDirectiveFromCouncil(
      eng,
      { type: "step_failed", step_number: 2 },
      { turn: 1, dataset_hits: [] },
      [{ agent: "exploit", alternate_chain_index: 1 }],
      replanData([primary, alternate], [0.5, 0.85]),
      { failure_class: "wrong_vector" },
      null
    );
    assert.equal(directive.action, "pivot_chain");
    assert.equal(directive.pivot_chain_index, 1);
    assert.ok(directive.updated_steps?.length);
  });

  it("returns patch_chain for auth_failed with small delta", () => {
    const eng = baseEng();
    const directive = buildDirectiveFromCouncil(
      eng,
      { type: "step_failed", step_number: 2 },
      { turn: 1, dataset_hits: [{ id: 3 }] },
      [],
      replanData(
        [{ steps: [keStep(3, "Cred spray"), keStep(4, "Follow-up")], confidence: 0.7 }],
        [0.7]
      ),
      { failure_class: "auth_failed" },
      null
    );
    assert.equal(directive.action, "patch_chain");
    assert.ok(directive.updated_steps);
  });

  it("returns reinitiate_chain for tool_blocked with large delta", () => {
    const eng = baseEng({
      attack_chains: {
        active_chain_index: 0,
        chains: [{ steps: Array.from({ length: 10 }, (_, i) => ({ phase: `p${i}` })) }],
      },
    });
    const manySteps = [keStep(100, "Only replanned step")];
    const directive = buildDirectiveFromCouncil(
      eng,
      { type: "step_failed", step_number: 3 },
      { turn: 1, dataset_hits: [] },
      [],
      replanData([{ steps: manySteps, confidence: 0.75 }], [0.75]),
      { failure_class: "tool_blocked" },
      null
    );
    assert.equal(directive.action, "reinitiate_chain");
  });

  it("honors conductor directive when hub returns one", () => {
    const eng = baseEng();
    const directive = buildDirectiveFromCouncil(
      eng,
      { type: "step_failed", step_number: 2 },
      { turn: 1 },
      [],
      null,
      { failure_class: "unknown" },
      {
        directive: {
          action: "pause",
          rationale: "Hub pause",
          dataset_record_ids: [42],
        },
      }
    );
    assert.equal(directive.action, "pause");
    assert.deepEqual(directive.dataset_record_ids, [42]);
  });
});
