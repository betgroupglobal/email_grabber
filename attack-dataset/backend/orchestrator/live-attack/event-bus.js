"use strict";

/**
 * Normalize live council trigger events from execution, scan, and guided flows.
 */
const VALID_TYPES = new Set([
  "step_completed",
  "step_failed",
  "method_failed",
  "scan_session_updated",
  "guided_phase_complete",
  "isolated_retry_exhausted",
  "force_replan",
]);

function normalizeEvent(raw) {
  const type = raw?.type;
  if (!type || !VALID_TYPES.has(type)) {
    throw new Error(`Invalid council event type: ${type}`);
  }
  return {
    type,
    engagement_id: raw.engagement_id,
    chain_index: raw.chain_index ?? 0,
    step: raw.step || null,
    step_number: raw.step_number ?? null,
    step_result: raw.step_result || null,
    method_result: raw.method_result || null,
    scan_delta: raw.scan_delta || null,
    phase: raw.phase || null,
    foothold_detected: Boolean(raw.foothold_detected),
    timestamp: raw.timestamp || new Date().toISOString(),
    meta: raw.meta || {},
  };
}

function createEventBus() {
  const handlers = [];

  function subscribe(handler) {
    handlers.push(handler);
    return () => {
      const idx = handlers.indexOf(handler);
      if (idx >= 0) handlers.splice(idx, 1);
    };
  }

  async function emit(raw) {
    const event = normalizeEvent(raw);
    let lastResult = null;
    for (const handler of handlers) {
      lastResult = await handler(event);
    }
    return lastResult;
  }

  return { subscribe, emit, normalizeEvent };
}

module.exports = {
  VALID_TYPES,
  normalizeEvent,
  createEventBus,
};
