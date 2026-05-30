"use strict";

/**
 * Pure MITRE mapping helpers (testable without Express).
 */

function parseMitreJsonFromLLMContent(content) {
  const jsonMatch =
    content.match(/```json\s*([\s\S]*?)```/) || content.match(/```\s*([\s\S]*?)```/);
  const jsonStr = jsonMatch ? jsonMatch[1].trim() : String(content || "").trim();
  return JSON.parse(jsonStr);
}

function sanitizeMitreAnalyzeResult(result) {
  result.techniques = (result.techniques || []).map((t) => ({
    technique_id: String(t.technique_id || "").toUpperCase(),
    name: String(t.name || ""),
    tactic: String(t.tactic || ""),
    confidence: Math.min(1, Math.max(0, parseFloat(t.confidence) || 0)),
    rationale: String(t.rationale || ""),
    subtechniques: (t.subtechniques || []).map(String),
    detection_methods: (t.detection_methods || []).map(String),
    mitigations: (t.mitigations || []).map(String),
  }));
  result.chains = (result.chains || []).map((c) => ({
    name: String(c.name || ""),
    steps: (c.steps || []).map((s) => ({
      phase: String(s.phase || ""),
      technique_id: String(s.technique_id || "").toUpperCase(),
      description: String(s.description || ""),
    })),
    confidence: Math.min(1, Math.max(0, parseFloat(c.confidence) || 0)),
  }));
  result.summary = String(result.summary || "");
  return result;
}

function mitreSuggestFromHeuristic(heuristic) {
  const primary_techniques = (heuristic.techniques || []).map((t, i) => ({
    technique_id: t.technique_id,
    name: t.name,
    tactic: t.tactic,
    applicability: t.rationale,
    priority: Math.max(1, 10 - i),
    prerequisites: [],
    expected_outcome: t.mitigations?.[0] || "Advance attack chain",
  }));
  const firstChain = heuristic.chains?.[0];
  return {
    primary_techniques,
    recommended_chain: firstChain
      ? {
          name: firstChain.name,
          steps: (firstChain.steps || []).map((s, idx) => ({
            order: idx + 1,
            phase: s.phase,
            technique_id: s.technique_id,
            description: s.description,
          })),
          estimated_success: firstChain.confidence ?? 0.5,
        }
      : { name: "Heuristic chain", steps: [], estimated_success: 0.4 },
    defensive_recommendations: [],
    analysis: heuristic.summary || "Heuristic MITRE suggestions from knowledge engine.",
    generated_at: heuristic.generated_at,
    ai_model: heuristic.ai_model,
    source: heuristic.source || "heuristic",
  };
}

function mitreEnhanceChainHeuristic(chain) {
  const enhanced_steps = (chain.steps || []).map((s, step_index) => {
    const tid = String(s.attack?.mitre_technique || s.mitre_technique || "T1595").toUpperCase();
    return {
      step_index,
      confirmed: Boolean(s.attack?.mitre_technique || s.mitre_technique),
      suggested_technique_id: tid,
      suggested_name: s.attack?.title || s.description || tid,
      suggested_tactic: s.phase || "Unknown",
      confidence: 0.55,
      rationale: "Heuristic confirmation from existing chain step metadata",
      alternative_techniques: [],
    };
  });
  return {
    enhanced_steps,
    missing_techniques: [],
    overall_assessment:
      "Heuristic enhancement — confirm mappings manually or enable Jailbreak AI / OpenRouter for AI refinement.",
    generated_at: new Date().toISOString(),
    ai_model: "heuristic:chain-metadata",
    source: "heuristic",
  };
}

/** Actionable error when AI + heuristic both fail (never bare "AI unavailable"). */
function formatMitreUnavailableError({ aiDetail, heuristicDetail } = {}) {
  const parts = [
    "MITRE mapping unavailable — set JAILBREAK_API_KEY on integration-hub and restart integration-hub",
    "(optional: OPENROUTER_API_KEY on orchestrator for OpenRouter)",
  ];
  if (aiDetail) parts.push(`AI: ${aiDetail}`);
  if (heuristicDetail) parts.push(`heuristic: ${heuristicDetail}`);
  return parts.join(". ");
}

module.exports = {
  parseMitreJsonFromLLMContent,
  sanitizeMitreAnalyzeResult,
  mitreSuggestFromHeuristic,
  mitreEnhanceChainHeuristic,
  formatMitreUnavailableError,
};
