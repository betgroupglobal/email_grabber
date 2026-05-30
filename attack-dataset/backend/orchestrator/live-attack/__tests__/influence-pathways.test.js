"use strict";

const { describe, it } = require("node:test");
const assert = require("node:assert/strict");

const {
  INFLUENCE_MAX_PATHWAY_ATTEMPTS,
  INFLUENCE_PATHWAY_COOLDOWN_MS,
  buildAlternatePathways,
  buildScanAlternatePathways,
  buildHubAlternatePathways,
  buildWebScannerAlternatePathways,
  buildChainIndexPathways,
  runWithInfluencePathways,
  recordInfluenceAttempt,
  isSuccessOutcome,
  isGuidedPhasePlan,
} = require("../influence-pathways");

describe("influence-pathways policy", () => {
  it("exposes sensible default limits", () => {
    assert.ok(INFLUENCE_MAX_PATHWAY_ATTEMPTS >= 1);
    assert.ok(INFLUENCE_PATHWAY_COOLDOWN_MS >= 0);
  });

  it("buildScanAlternatePathways excludes primary profile", () => {
    const alts = buildScanAlternatePathways("quick");
    assert.ok(alts.length >= 1);
    assert.ok(alts.every((p) => p.params.scan_type !== "quick"));
    assert.equal(alts[0].method, "analyzer_scan_profile");
  });

  it("buildHubAlternatePathways offers recon variants", () => {
    const alts = buildHubAlternatePathways("reconnaissance", {
      scan_type: "quick",
      ports: "80,443",
    });
    assert.ok(alts.length >= 1);
    assert.ok(alts.some((p) => p.params.scan_type === "comprehensive"));
  });

  it("buildWebScannerAlternatePathways offers nuclei template alternates", () => {
    const alts = buildWebScannerAlternatePathways("nuclei", {
      operation: "scan_target",
      severity: "medium,high,critical",
    });
    assert.ok(alts.length >= 1);
    assert.ok(alts.some((p) => p.params.tags || p.params.templates));
  });

  it("buildChainIndexPathways ranks alternate chains by score", () => {
    const eng = {
      attack_chains: {
        chains: [
          { steps: [{ phase: "A" }], confidence: 0.5 },
          { steps: [{ phase: "B" }], confidence: 0.9 },
        ],
        alternate_chain_scores: [0.5, 0.9],
      },
    };
    const alts = buildChainIndexPathways(eng, 0);
    assert.equal(alts[0].params.chain_index, 1);
  });

  it("isSuccessOutcome detects scan and hub shapes", () => {
    assert.equal(isSuccessOutcome({ status: "ready" }), true);
    assert.equal(isSuccessOutcome({ success: false }), false);
    assert.equal(isSuccessOutcome({ output: "ok" }), true);
    assert.equal(isSuccessOutcome(null), false);
  });

  it("isGuidedPhasePlan and isSuccessOutcome accept jailbreak phase plans", () => {
    const plan = {
      narrative: "Run nuclei CVE templates on 443",
      recommended_actions: ["nuclei scan"],
      phase_complete: true,
      source: "jailbreak_api",
      hub_operation: "none",
    };
    assert.equal(isGuidedPhasePlan(plan), true);
    assert.equal(isSuccessOutcome(plan), true);
  });

  it("runWithInfluencePathways stops on first successful alternate", async () => {
    const eng = { influence_attempts: [] };
    const calls = [];

    const result = await runWithInfluencePathways({
      eng,
      engagementId: "e-test",
      task_kind: "scan",
      task_id: "scan_1",
      context: { primary_scan_type: "quick" },
      executePrimary: async () => {
        calls.push("primary");
        return null;
      },
      executeAlternate: async (pathway) => {
        calls.push(pathway.pathway_id);
        if (pathway.pathway_id === "scan_profile_web_application") {
          return { status: "ready", fingerprint: { services: [] } };
        }
        return null;
      },
      buildAlternates: () => buildScanAlternatePathways("quick"),
    });

    assert.equal(result.success, true);
    assert.ok(calls.includes("primary"));
    assert.ok(eng.influence_attempts.length >= 2);
  });

  it("runWithInfluencePathways exhausts max attempts", async () => {
    const eng = { influence_attempts: [] };

    const result = await runWithInfluencePathways({
      eng,
      engagementId: "e-exhaust",
      task_kind: "hub",
      task_id: "recon",
      context: { operation: "reconnaissance", primary_params: {} },
      executePrimary: async () => ({ success: false }),
      executeAlternate: async () => ({ success: false }),
      buildAlternates: () => [
        { pathway_id: "a", method: "m", label: "a", params: {} },
        { pathway_id: "b", method: "m", label: "b", params: {} },
      ],
    });

    assert.equal(result.success, false);
    assert.equal(result.exhausted, true);
    assert.ok(eng.influence_attempts.length <= INFLUENCE_MAX_PATHWAY_ATTEMPTS);
  });

  it("recordInfluenceAttempt caps history", () => {
    const eng = { influence_attempts: [] };
    for (let i = 0; i < 5; i++) {
      recordInfluenceAttempt(eng, {
        pathway_id: `p${i}`,
        method: "test",
        outcome: "failed",
      });
    }
    assert.equal(eng.influence_attempts.length, 5);
  });

  it("buildAlternatePathways returns chain_step tool alternates", () => {
    const alts = buildAlternatePathways("chain_step", {
      step: { tool: "nmap" },
      recommended_tools: ["nuclei", "nmap"],
      eng: { attack_chains: { chains: [] } },
      chain_index: 0,
    });
    assert.ok(alts.some((p) => p.method === "alternate_tool"));
  });
});
