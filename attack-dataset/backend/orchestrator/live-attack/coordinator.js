"use strict";

const { createEventBus } = require("./event-bus");
const { classifyFailure } = require("./failure-taxonomy");
const { runCouncilTurn, initLiveCouncil } = require("./council");
const { applyCouncilDirective, appendReasoningTrace } = require("./directive-applier");
const { isLiveCouncilEnabled } = require("./index-utils");
const {
  initInfluenceState,
  emitPathwayTerminal,
  INFLUENCE_MAX_PATHWAY_ATTEMPTS,
} = require("./influence-pathways");

const DEBOUNCE_MS = parseInt(process.env.LIVE_COUNCIL_DEBOUNCE_MS || "2000", 10);
const RATE_LIMIT = parseInt(process.env.LIVE_COUNCIL_RATE_LIMIT || "12", 10);

function createLiveAttackCoordinator(deps) {
  const bus = createEventBus();
  const turnTimestamps = new Map();
  const debounceTimers = new Map();

  function recordTurn(engagementId) {
    const now = Date.now();
    const key = engagementId;
    const arr = turnTimestamps.get(key) || [];
    arr.push(now);
    const cutoff = now - 60000;
    turnTimestamps.set(key, arr.filter((t) => t >= cutoff));
    return (turnTimestamps.get(key) || []).length;
  }

  function isRateLimited(engagementId) {
    return recordTurn(engagementId) > RATE_LIMIT;
  }

  async function processEvent(event, ctx) {
    const { eng, engagementId, reqBody } = ctx;
    if (!eng) return null;
    if (!isLiveCouncilEnabled(eng, reqBody || {})) return null;

    initLiveCouncil(eng);
    const council = eng.live_council;
    council.state = council.state || "idle";

    if (isRateLimited(engagementId)) {
      console.warn(`[coordinator] rate limit exceeded for ${engagementId}`);
      return null;
    }

    if (event.type === "step_completed" && event.step_result?.status !== "success") {
      return null;
    }

    const failureInfo = classifyFailure({
      ...event,
      type: event.type,
    });

    const trigger = {
      type: event.type,
      step: event.step,
      step_number: event.step_number,
      step_result: event.step_result,
      method_result: event.method_result,
      failure_class: failureInfo.failure_class,
      scan_delta: event.scan_delta,
      phase: event.phase,
    };

    if (event.type === "step_completed" && !event.meta?.force_review) {
      appendReasoningTrace(
        eng,
        {
          source: "coordinator",
          event: event.type,
          step_number: event.step_number,
          note: "Step succeeded — lightweight review skipped",
          pattern_step: "evaluate",
        },
        { engagementId, broadcastCouncil, broadcastTerminal }
      );
      council.state = "executing";
      return { action: "continue" };
    }

    if (
      event.type !== "step_failed" &&
      event.type !== "method_failed" &&
      event.type !== "isolated_retry_exhausted" &&
      event.type !== "force_replan" &&
      event.type !== "scan_session_updated" &&
      event.type !== "guided_phase_complete"
    ) {
      return null;
    }

    council.state = "analyzing";

    initInfluenceState(eng);
    emitPathwayTerminal(
      ctx.broadcastTerminal,
      engagementId,
      `failure on ${event.type} — council replan (max ${INFLUENCE_MAX_PATHWAY_ATTEMPTS} pathway attempts per task)`,
      "info"
    );

    const directive = await runCouncilTurn({
      ...ctx,
      engagementId,
      eng,
      trigger,
      failureInfo,
    });

    if (!directive) {
      council.state = "executing";
      return null;
    }

    const applyResult = applyCouncilDirective({
      ...ctx,
      engagementId,
      eng,
      directive,
      chain_index: event.chain_index ?? eng.attack_chains?.active_chain_index ?? 0,
      chain: ctx.chain,
    });

    if (applyResult.action === "abort" || applyResult.action === "pause") {
      council.state = applyResult.action === "abort" ? "aborted" : "paused";
    } else if (applyResult.resume) {
      council.state = "executing";
    } else {
      council.state = "executing";
    }

    return applyResult;
  }

  function emit(raw, ctx) {
    const engagementId = raw.engagement_id || ctx?.engagementId;
    if (!engagementId) return Promise.resolve(null);

    const eventKey = `${engagementId}:${raw.type}:${raw.step_number || raw.phase || ""}`;

    if (DEBOUNCE_MS > 0 && raw.type === "scan_session_updated") {
      return new Promise((resolve) => {
        if (debounceTimers.has(eventKey)) {
          clearTimeout(debounceTimers.get(eventKey));
        }
        debounceTimers.set(
          eventKey,
          setTimeout(async () => {
            debounceTimers.delete(eventKey);
            resolve(await processEvent(raw, { ...ctx, engagementId }));
          }, DEBOUNCE_MS)
        );
      });
    }

    return processEvent(raw, { ...ctx, engagementId });
  }

  bus.subscribe(async (event) => {
    /* default no-op; orchestrator passes ctx per emit call */
    return null;
  });

  return {
    bus,
    emit,
    processEvent,
  };
}

module.exports = {
  createLiveAttackCoordinator,
  DEBOUNCE_MS,
  RATE_LIMIT,
};
