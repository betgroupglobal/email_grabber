"use strict";

/**
 * Apply live directive to attack_chains with version history.
 */
function initAttackChainsState(eng) {
  if (!eng.attack_chains) {
    eng.attack_chains = { version: 0, active_chain_index: 0, chains: [], history: [] };
  }
  if (eng.attack_chains.version == null) {
    eng.attack_chains.version = 0;
  }
  if (!Array.isArray(eng.attack_chains.history)) {
    eng.attack_chains.history = [];
  }
}

function snapshotChains(eng) {
  return JSON.parse(JSON.stringify(eng.attack_chains?.chains || []));
}

function recordChainVersion(eng, directive, reason) {
  initAttackChainsState(eng);
  const prevVersion = eng.attack_chains.version || 0;
  eng.attack_chains.history.push({
    version: prevVersion,
    reason: reason || directive?.rationale || "live_replan",
    directive_id: directive?.directive_id,
    chains_snapshot: snapshotChains(eng),
    created_at: new Date().toISOString(),
  });
  if (eng.attack_chains.history.length > 20) {
    eng.attack_chains.history.shift();
  }
  eng.attack_chains.version = prevVersion + 1;
}

/**
 * Merge completed step prefix with replanned remainder.
 */
function mergeChainSteps(completedSteps, newSteps, fromStepIndex) {
  const prefix = (completedSteps || []).map((s) => s.step || s).filter(Boolean);
  const prefixCount = Math.min(prefix.length, fromStepIndex);
  const kept = prefix.slice(0, prefixCount);
  return [...kept, ...(newSteps || [])];
}

/**
 * Convert KE AttackChain steps to orchestrator step shape.
 */
function keChainToOrchestratorSteps(keChain) {
  return (keChain.steps || []).map((s) => ({
    phase: s.phase,
    attack: {
      id: s.attack?.id,
      title: s.attack?.title,
      attack_type: s.attack?.attack_type,
      category: s.attack?.category,
      mitre_technique: s.mitre_technique || s.attack?.mitre_technique,
      tools_used: s.attack?.tools_used,
      scenario_description: s.attack?.scenario_description,
      detection_method: s.attack?.detection_method,
    },
    rationale: s.rationale,
    command: s.attack?.tools_used
      ? `# ${s.phase}: ${s.attack.title} (${s.attack.tools_used})`
      : undefined,
  }));
}

function extractDatasetRecordIds(steps) {
  const ids = [];
  for (const s of steps || []) {
    const id = s.attack?.id;
    if (id != null) ids.push(id);
  }
  return ids;
}

function buildChainMeta(directive, newSteps, eng) {
  return {
    replan_reason: directive.rationale,
    parent_version: (eng.attack_chains.version || 1) - 1,
    directive_id: directive.directive_id,
    dataset_record_ids: directive.dataset_record_ids || extractDatasetRecordIds(newSteps),
    failure_class: directive.failure_class,
  };
}

function applyDirectiveToEngagement(eng, directive, chainIndex) {
  initAttackChainsState(eng);
  recordChainVersion(eng, directive, directive.rationale);

  const idx = chainIndex ?? eng.attack_chains.active_chain_index ?? 0;
  const chains = [...(eng.attack_chains.chains || [])];
  const newSteps = directive.updated_steps || [];
  const fromIdx = directive.from_step_index ?? 0;

  const currentSteps = chains[idx]?.steps || [];
  const merged = [...currentSteps.slice(0, fromIdx), ...newSteps];

  const updatedChain = {
    ...(chains[idx] || {}),
    steps: merged,
    meta: buildChainMeta(directive, newSteps, eng),
  };

  if (chains[idx]) {
    chains[idx] = updatedChain;
  } else {
    chains.push(updatedChain);
  }

  eng.attack_chains.chains = chains;
  eng.attack_chains.active_chain_index = idx;

  return { merged_steps: merged, chain_index: idx };
}

/**
 * Splice 1–3 replacement steps at from_step_index (patch_chain).
 */
function applyPatchDirective(eng, directive, chainIndex) {
  initAttackChainsState(eng);
  recordChainVersion(eng, directive, directive.rationale);

  const idx = chainIndex ?? eng.attack_chains.active_chain_index ?? 0;
  const chains = [...(eng.attack_chains.chains || [])];
  const newSteps = directive.updated_steps || [];
  const fromIdx = directive.from_step_index ?? 0;
  const currentSteps = chains[idx]?.steps || [];

  const prefix = currentSteps.slice(0, fromIdx);
  const suffix = currentSteps.slice(fromIdx + newSteps.length);
  const merged = mergeChainSteps(
    prefix.map((s) => ({ step: s })),
    [...newSteps, ...suffix],
    fromIdx
  );

  const updatedChain = {
    ...(chains[idx] || {}),
    steps: merged,
    meta: buildChainMeta(directive, newSteps, eng),
  };

  if (chains[idx]) chains[idx] = updatedChain;
  else chains.push(updatedChain);

  eng.attack_chains.chains = chains;
  eng.attack_chains.active_chain_index = idx;

  return { merged_steps: merged, chain_index: idx };
}

/**
 * Switch active chain index and optionally replace chain body (pivot_chain).
 */
function applyPivotDirective(eng, directive) {
  initAttackChainsState(eng);
  recordChainVersion(eng, directive, directive.rationale);

  const chains = [...(eng.attack_chains.chains || [])];
  const pivotIdx =
    directive.pivot_chain_index ??
    directive.updated_chain_index ??
    (chains.length > 1 ? 1 : 0);

  const newSteps = directive.updated_steps || [];
  const fromIdx = 0;

  if (newSteps.length) {
    if (chains[pivotIdx]) {
      chains[pivotIdx] = {
        ...chains[pivotIdx],
        steps: newSteps,
        meta: buildChainMeta(directive, newSteps, eng),
      };
    } else {
      chains[pivotIdx] = {
        steps: newSteps,
        confidence: directive.confidence,
        meta: buildChainMeta(directive, newSteps, eng),
      };
    }
  }

  eng.attack_chains.chains = chains;
  eng.attack_chains.active_chain_index = pivotIdx;

  const merged = chains[pivotIdx]?.steps || newSteps;
  return { merged_steps: merged, chain_index: pivotIdx, from_step_index: fromIdx };
}

module.exports = {
  initAttackChainsState,
  recordChainVersion,
  mergeChainSteps,
  keChainToOrchestratorSteps,
  extractDatasetRecordIds,
  applyDirectiveToEngagement,
  applyPatchDirective,
  applyPivotDirective,
};
