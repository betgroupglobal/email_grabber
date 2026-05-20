"use strict";

const { describe, it } = require("node:test");
const assert = require("node:assert/strict");

const {
  parseMitreJsonFromLLMContent,
  sanitizeMitreAnalyzeResult,
  mitreSuggestFromHeuristic,
  formatMitreUnavailableError,
} = require("../mitre-mapping");

describe("mitre-mapping", () => {
  it("parses JSON from fenced LLM content", () => {
    const raw = 'Here is the map:\n```json\n{"techniques":[],"chains":[],"summary":"ok"}\n```';
    const parsed = parseMitreJsonFromLLMContent(raw);
    assert.equal(parsed.summary, "ok");
  });

  it("sanitizes technique ids to uppercase", () => {
    const out = sanitizeMitreAnalyzeResult({
      techniques: [{ technique_id: "t1190", name: "Exploit", tactic: "Initial Access", confidence: 1.5 }],
      chains: [],
      summary: "",
    });
    assert.equal(out.techniques[0].technique_id, "T1190");
    assert.equal(out.techniques[0].confidence, 1);
  });

  it("builds suggest payload from heuristic analyze shape", () => {
    const suggest = mitreSuggestFromHeuristic({
      techniques: [
        {
          technique_id: "T1595",
          name: "Active Scanning",
          tactic: "Reconnaissance",
          rationale: "Port scan",
          mitigations: [],
        },
      ],
      chains: [
        {
          name: "Recon chain",
          steps: [{ phase: "Recon", technique_id: "T1595", description: "Scan" }],
          confidence: 0.7,
        },
      ],
      summary: "Heuristic summary",
      generated_at: "2026-01-01T00:00:00.000Z",
      ai_model: "heuristic:attack-vector",
      source: "heuristic",
    });
    assert.equal(suggest.source, "heuristic");
    assert.equal(suggest.primary_techniques[0].technique_id, "T1595");
    assert.equal(suggest.recommended_chain.name, "Recon chain");
  });

  it("formatMitreUnavailableError mentions JAILBREAK_API_KEY", () => {
    const msg = formatMitreUnavailableError({ aiDetail: "hub down", heuristicDetail: "ke down" });
    assert.match(msg, /JAILBREAK_API_KEY/);
    assert.match(msg, /hub down/);
    assert.doesNotMatch(msg, /^AI unavailable$/);
  });
});
