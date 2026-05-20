"use strict";

const axios = require("axios");

const EMBEDDING_MODEL =
  process.env.EMBEDDING_MODEL || "sentence-transformers/all-MiniLM-L6-v2";

/**
 * Build live query text from engagement + trigger event for KE search/ML.
 */
function buildLiveQuery(eng, trigger) {
  const parts = [eng.target];

  const fp = eng.scan_session?.fingerprint;
  if (fp?.os) parts.push(`OS:${fp.os}`);
  (fp?.services || []).slice(0, 12).forEach((s) => {
    parts.push([s.port, s.name, s.product, s.version].filter(Boolean).join(" "));
  });

  const step = trigger.step || {};
  if (step.phase) parts.push(step.phase);
  if (step.attack?.title) parts.push(step.attack.title);
  if (step.tool) parts.push(`tool:${step.tool}`);
  if (step.command) parts.push(String(step.command).slice(0, 400));

  const result = trigger.step_result || {};
  if (result.output) parts.push(String(result.output).slice(0, 2000));

  const methods = result.chain_attack_methods || [];
  const failed = methods.filter((m) => m.success === false);
  failed.forEach((m) => {
    parts.push(`failed_method:${m.method_name || m.method_id} tool:${m.tool}`);
  });

  const recent = (eng.chain_execution?.steps || []).slice(-3);
  recent.forEach((s) => {
    parts.push(`prior_step:${s.status} ${(s.output || "").slice(0, 120)}`);
  });

  return parts.filter(Boolean).join(" ").trim();
}

/**
 * Fetch CouncilGroundingPack from Knowledge Engine (attack DB + trained model).
 */
async function buildCouncilGroundingPack(eng, trigger, knowledgeEngineUrl, authHeaders) {
  const query_text = buildLiveQuery(eng, trigger);
  const headers = authHeaders || {};

  let dataset_hits = [];
  let ml_predictions = [];
  let searchError = null;
  let mlError = null;

  try {
    const { data } = await axios.post(
      `${knowledgeEngineUrl}/search`,
      { query: query_text, top_k: 15 },
      { timeout: 45000, headers }
    );
    dataset_hits = (data.results || []).map((r) => ({
      id: r.record?.id,
      title: r.record?.title,
      category: r.record?.category,
      attack_type: r.record?.attack_type,
      mitre_technique: r.record?.mitre_technique,
      tools_used: r.record?.tools_used,
      score: r.score,
      ml_category: r.record?.ml_category,
      ml_confidence: r.record?.ml_confidence,
    }));
  } catch (err) {
    searchError = err.message;
  }

  try {
    const { data } = await axios.post(
      `${knowledgeEngineUrl}/ml/predict`,
      { text: query_text, target: "category", top_k: 5 },
      { timeout: 30000, headers }
    );
    ml_predictions = data.predictions || [];
  } catch (err) {
    mlError = err.message;
  }

  const pack = {
    turn: (eng.live_council?.turn || 0) + 1,
    built_at: new Date().toISOString(),
    query_text,
    aggression_level: eng.aggression_level ?? 5,
    boundary_profile: eng.boundary_profile || null,
    dataset_hits,
    ml_predictions,
    model_metadata: {
      embedding_model: EMBEDDING_MODEL,
      ml_model_name: "category",
      dataset_source: "Attack_Dataset.csv",
    },
    errors: {
      search: searchError,
      ml: mlError,
    },
  };

  return pack;
}

module.exports = {
  buildLiveQuery,
  buildCouncilGroundingPack,
};
