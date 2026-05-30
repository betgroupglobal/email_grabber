"use strict";

const { initAttackChainsState, mergeChainSteps } = require("./chain-versioning");
const {
  applyDirectiveToEngagement,
  applyPivotDirective,
  applyPatchDirective,
} = require("./chain-versioning");

const LIVE_REQUIRE_APPROVAL =
  process.env.LIVE_REQUIRE_APPROVAL === "true" ||
  process.env.LIVE_REQUIRE_APPROVAL === "1";

/** When true (default), high-risk / OpSec veto / council approval gates do not pause execution. */
const ALLOW_HIGH_RISK =
  process.env.ALLOW_HIGH_RISK !== "false" &&
  process.env.ALLOW_HIGH_RISK !== "0";

const OPSEC_VETO_THRESHOLD = parseFloat(
  process.env.LIVE_OPSEC_VETO_THRESHOLD || "0.75"
);

const {
  appendReasoningTrace: appendReasoningTraceEntry,
} = require("../reasoning-pattern");

function appendReasoningTrace(eng, entry, opts = {}) {
  return appendReasoningTraceEntry(eng, entry, opts);
}

function needsApproval(directive) {
  if (ALLOW_HIGH_RISK) return false;
  if (!LIVE_REQUIRE_APPROVAL) return false;
  if (directive.action === "continue") return false;
  return (
    directive.priority === "high" ||
    ["reinitiate_chain", "pivot_chain", "abort"].includes(directive.action)
  );
}

/** Frontend templater hotkey hints — derived from directive action when not set by conductor. */
function enrichDirectiveHotkeyHints(directive) {
  if (!directive || directive.suggested_hotkey) return directive;
  const action = directive.action || "continue";
  const map = {
    continue: { suggested_hotkey: "C", suggested_template_id: "continue" },
    patch_chain: { suggested_hotkey: "C", suggested_template_id: "patch_chain" },
    reinitiate_chain: { suggested_hotkey: "P", suggested_template_id: "reinitiate_chain" },
    pivot_chain: { suggested_hotkey: "P", suggested_template_id: "pivot_chain" },
    pause: { suggested_hotkey: "Esc", suggested_template_id: "pause" },
    abort: { suggested_hotkey: "Esc", suggested_template_id: "reject_abort" },
  };
  const hints = map[action] || { suggested_hotkey: "A", suggested_template_id: "approve_council" };
  return { ...directive, ...hints, suggested_action: action };
}

/**
 * Apply a council directive to engagement state; return execution control info.
 */
function applyCouncilDirective(ctx) {
  const {
    eng,
    directive,
    chain_index,
    chain,
    normalizeChainSteps,
    broadcast,
    broadcastCouncil,
    broadcastTerminal,
    engagementId,
  } = ctx;

  if (!directive) return { action: "none" };

  initAttackChainsState(eng);
  const council = eng.live_council || {};

  appendReasoningTrace(
    eng,
    {
      source: "live_council",
      turn: directive.turn,
      action: directive.action,
      failure_class: directive.failure_class,
      rationale: directive.rationale,
      rationale_steps: directive.rationale_steps || [],
      directive_id: directive.directive_id,
    },
    {
      engagementId,
      broadcastCouncil,
      broadcastTerminal,
    }
  );

  let effectiveDirective = directive;
  if (effectiveDirective.opsec_veto && ALLOW_HIGH_RISK) {
    if (broadcastTerminal) {
      broadcastTerminal(
        engagementId,
        "[council] high risk noted — continuing",
        "warning"
      );
    }
    if (effectiveDirective.action === "pause") {
      effectiveDirective = { ...effectiveDirective, action: "continue" };
    }
  }

  if (needsApproval(effectiveDirective) && !effectiveDirective.approved) {
    const pendingDirective = enrichDirectiveHotkeyHints(effectiveDirective);
    council.pending_directive = pendingDirective;
    council.state = "paused";
    eng.status = "paused";
    if (broadcastCouncil) {
      broadcastCouncil(engagementId, {
        type: "approval_required",
        directive: pendingDirective,
      });
    }
    if (broadcastTerminal) {
      broadcastTerminal(
        engagementId,
        `⏸️ APPROVAL REQUIRED — ${effectiveDirective.action}: ${(effectiveDirective.rationale || "").slice(0, 160)}`,
        "warning"
      );
    }
    if (broadcast) broadcast(engagementId, eng);
    return { action: "pause", pending: true, directive: effectiveDirective };
  }

  if (effectiveDirective.opsec_veto && !ALLOW_HIGH_RISK) {
    council.state = "paused";
    eng.status = "paused";
    if (broadcastCouncil) {
      broadcastCouncil(engagementId, {
        type: "execution_paused",
        reason: effectiveDirective.rationale || "OpSec veto",
      });
    }
    if (broadcast) broadcast(engagementId, eng);
    return { action: "pause", directive: effectiveDirective };
  }

  switch (effectiveDirective.action) {
    case "abort": {
      council.state = "aborted";
      eng.status = "aborted";
      if (eng.chain_execution) eng.chain_execution.status = "aborted";
      eng.log = eng.log || [];
      eng.log.push({
        ts: new Date().toISOString(),
        msg: `Live council ABORT: ${(effectiveDirective.rationale || "").slice(0, 120)}`,
      });
      if (broadcastCouncil) {
        broadcastCouncil(engagementId, {
          type: "execution_paused",
          reason: effectiveDirective.rationale || "Council abort",
        });
      }
      if (broadcast) broadcast(engagementId, eng);
      return { action: "abort", directive: effectiveDirective };
    }

    case "pause": {
      council.state = "paused";
      eng.status = "paused";
      if (broadcastCouncil) {
        broadcastCouncil(engagementId, {
          type: "execution_paused",
          reason: effectiveDirective.rationale || "Council pause",
        });
      }
      if (broadcast) broadcast(engagementId, eng);
      return { action: "pause", directive: effectiveDirective };
    }

    case "continue": {
      council.state = "executing";
      council.last_directive = effectiveDirective;
      effectiveDirective.applied = true;
      effectiveDirective.applied_at = new Date().toISOString();
      if (broadcast) broadcast(engagementId, eng);
      return { action: "continue", directive: effectiveDirective };
    }

    case "patch_chain":
    case "reinitiate_chain": {
      if (effectiveDirective.opsec_veto && !ALLOW_HIGH_RISK) {
        return { action: "pause", directive: effectiveDirective };
      }

      let steps = effectiveDirective.updated_steps || [];
      if (normalizeChainSteps) steps = normalizeChainSteps(steps);
      effectiveDirective.updated_steps = steps;
      effectiveDirective.applied = true;
      effectiveDirective.applied_at = new Date().toISOString();

      const idx = chain_index ?? eng.attack_chains.active_chain_index ?? 0;
      let result;
      if (effectiveDirective.action === "patch_chain") {
        result = applyPatchDirective(eng, effectiveDirective, idx);
      } else {
        result = applyDirectiveToEngagement(eng, effectiveDirective, idx);
      }

      if (chain) chain.steps = result.merged_steps;

      eng.log = eng.log || [];
      eng.log.push({
        ts: new Date().toISOString(),
        msg: `Live council ${effectiveDirective.action} v${eng.attack_chains.version}: ${(effectiveDirective.rationale || "").slice(0, 120)}`,
      });

      if (broadcastCouncil) {
        broadcastCouncil(engagementId, {
          type: "chain_versioned",
          version: eng.attack_chains.version,
          diff_summary: (effectiveDirective.rationale || "").slice(0, 160),
          step_count: result.merged_steps.length,
        });
      }
      if (broadcast) broadcast(engagementId, eng);

      return {
        action: effectiveDirective.action,
        resume: true,
        from_step_index: effectiveDirective.from_step_index ?? 0,
        steps: result.merged_steps,
        chain_index: result.chain_index,
        directive: effectiveDirective,
      };
    }

    case "pivot_chain": {
      if (effectiveDirective.opsec_veto && !ALLOW_HIGH_RISK) {
        return { action: "pause", directive: effectiveDirective };
      }

      let steps = effectiveDirective.updated_steps || [];
      if (normalizeChainSteps) steps = normalizeChainSteps(steps);
      effectiveDirective.updated_steps = steps;
      effectiveDirective.applied = true;
      effectiveDirective.applied_at = new Date().toISOString();

      const result = applyPivotDirective(eng, effectiveDirective);

      if (chain) {
        const idx = result.chain_index;
        chain.steps = eng.attack_chains.chains[idx]?.steps || steps;
      }

      if (eng.chain_execution) {
        eng.chain_execution.current_step = 0;
        eng.chain_execution.chain_index = result.chain_index;
      }

      eng.log = eng.log || [];
      eng.log.push({
        ts: new Date().toISOString(),
        msg: `Live council pivot v${eng.attack_chains.version} → chain ${result.chain_index}: ${(effectiveDirective.rationale || "").slice(0, 120)}`,
      });

      if (broadcastCouncil) {
        broadcastCouncil(engagementId, {
          type: "chain_versioned",
          version: eng.attack_chains.version,
          diff_summary: (effectiveDirective.rationale || "").slice(0, 160),
          step_count: result.merged_steps.length,
          pivoted: true,
          chain_index: result.chain_index,
        });
      }
      if (broadcast) broadcast(engagementId, eng);

      return {
        action: "pivot_chain",
        resume: true,
        from_step_index: 0,
        steps: result.merged_steps,
        chain_index: result.chain_index,
        directive: effectiveDirective,
      };
    }

    default:
      return { action: "none", directive: effectiveDirective };
  }
}

module.exports = {
  LIVE_REQUIRE_APPROVAL,
  ALLOW_HIGH_RISK,
  OPSEC_VETO_THRESHOLD,
  appendReasoningTrace,
  needsApproval,
  enrichDirectiveHotkeyHints,
  applyCouncilDirective,
};
