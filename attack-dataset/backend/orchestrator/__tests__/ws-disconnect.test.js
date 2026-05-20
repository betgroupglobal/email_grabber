"use strict";

const { describe, it } = require("node:test");
const assert = require("node:assert/strict");
const { createGuidedAutonomousService } = require("../guided-autonomous");

/** Mirrors orchestrator index.js terminal/default ws.on("close") — subscriber cleanup only. */
function simulateWsClose(subscribers, engId, ws) {
  subscribers.get(engId)?.delete(ws);
}

describe("WebSocket disconnect does not stop engagements", () => {
  it("terminal ws close removes subscriber only", () => {
    const terminalSubscribers = new Map();
    const engId = "abc12345";
    const ws = { readyState: 1 };

    terminalSubscribers.set(engId, new Set([ws]));
    simulateWsClose(terminalSubscribers, engId, ws);

    assert.equal(terminalSubscribers.get(engId)?.size ?? 0, 0);
  });

  it("default engagement ws close removes subscriber only", () => {
    const subscribers = new Map();
    const engId = "def67890";
    const ws = { readyState: 1 };

    subscribers.set(engId, new Set([ws]));
    simulateWsClose(subscribers, engId, ws);

    assert.equal(subscribers.get(engId)?.size ?? 0, 0);
  });

  it("requestStop is explicit — not triggered by subscriber cleanup", () => {
    const engagements = new Map();
    const engId = "stop1234";
    engagements.set(engId, {
      id: engId,
      target: "https://example.com",
      status: "running",
      guided_autonomous: { status: "running", phases: [] },
      log: [],
    });

    const service = createGuidedAutonomousService({
      engagements,
      broadcast: () => {},
      broadcastTerminal: () => {},
      axios: {},
      getServiceAuthHeaders: () => ({}),
      normalizeTargetInput: (t) => t,
      isValidTarget: () => true,
      validateAndSanitizeTarget: (t) => t,
      buildBoundaryProfile: () => ({ aggression_level: 5 }),
      KNOWLEDGE_ENGINE: "",
      OPSEC_URL: "",
      INTEGRATION_HUB_URL: "",
      ANALYZER_URL: "",
      PORT: 3000,
      liveAttack: null,
    });

    const terminalSubscribers = new Map();
    const ws = { readyState: 1 };
    terminalSubscribers.set(engId, new Set([ws]));
    simulateWsClose(terminalSubscribers, engId, ws);

    const statusBefore = service.getStatus(engId);
    assert.equal(statusBefore.guided_autonomous.status, "running");

    service.requestStop(engId);
    const statusAfter = service.getStatus(engId);
    assert.equal(statusAfter.guided_autonomous.status, "stopping");
  });
});
