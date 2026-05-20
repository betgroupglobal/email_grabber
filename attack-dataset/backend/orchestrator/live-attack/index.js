"use strict";

const { initLiveCouncil, runCouncilTurn } = require("./council");
const { buildCouncilGroundingPack, buildLiveQuery } = require("./grounding");
const {
  applyDirectiveToEngagement,
  initAttackChainsState,
} = require("./chain-versioning");
const { createLiveAttackCoordinator } = require("./coordinator");
const { applyCouncilDirective } = require("./directive-applier");
const { isLiveCouncilEnabled, LIVE_COUNCIL_DEFAULT } = require("./index-utils");
const { classifyFailure } = require("./failure-taxonomy");
const influencePathways = require("./influence-pathways");

let sharedCoordinator = null;

function getCoordinator(deps) {
  if (!sharedCoordinator) {
    sharedCoordinator = createLiveAttackCoordinator(deps || {});
  }
  return sharedCoordinator;
}

/**
 * Emit council event through coordinator (replaces tryLiveReplanOnFailure).
 */
async function emitCouncilEvent(event, ctx) {
  const coordinator = getCoordinator(ctx);
  return coordinator.emit(event, ctx);
}

/**
 * Legacy wrapper — step failure hook from execute-chain.
 */
async function tryLiveReplanOnFailure(ctx) {
  const {
    eng,
    engagementId,
    chain_index,
    chain,
    step,
    step_result,
    step_number,
    reqBody,
  } = ctx;

  if (!isLiveCouncilEnabled(eng, reqBody || {})) return null;

  initLiveCouncil(eng);
  initAttackChainsState(eng);

  const result = await emitCouncilEvent(
    {
      type: "step_failed",
      engagement_id: engagementId,
      chain_index,
      step,
      step_number,
      step_result,
    },
    ctx
  );

  if (result?.resume) {
    return {
      resume: true,
      from_step_index: result.from_step_index,
      steps: result.steps,
      chain_index: result.chain_index ?? chain_index,
      directive: result.directive,
      abort: result.action === "abort",
    };
  }

  if (result?.action === "abort") {
    return { abort: true, directive: result.directive };
  }

  if (result?.action === "pause") {
    return { pause: true, directive: result.directive };
  }

  return null;
}

function approvePendingDirective(eng) {
  const pending = eng.live_council?.pending_directive;
  if (!pending) return null;
  pending.approved = true;
  eng.live_council.pending_directive = null;
  return pending;
}

module.exports = {
  isLiveCouncilEnabled,
  initLiveCouncil,
  runCouncilTurn,
  tryLiveReplanOnFailure,
  emitCouncilEvent,
  applyCouncilDirective,
  approvePendingDirective,
  buildCouncilGroundingPack,
  buildLiveQuery,
  classifyFailure,
  getCoordinator,
  LIVE_COUNCIL_DEFAULT,
  ...influencePathways,
};
