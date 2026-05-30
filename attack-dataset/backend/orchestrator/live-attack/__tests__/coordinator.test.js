"use strict";

const { describe, it } = require("node:test");
const assert = require("node:assert/strict");
const { createEventBus, normalizeEvent } = require("../event-bus");
const { createLiveAttackCoordinator, RATE_LIMIT } = require("../coordinator");
const { isLiveCouncilEnabled } = require("../index-utils");

describe("event-bus", () => {
  it("normalizes valid events", () => {
    const event = normalizeEvent({
      type: "step_failed",
      engagement_id: "abc",
      step_number: 2,
    });
    assert.equal(event.type, "step_failed");
    assert.equal(event.engagement_id, "abc");
  });

  it("rejects invalid event types", () => {
    assert.throws(() => normalizeEvent({ type: "invalid" }));
  });
});

describe("coordinator", () => {
  it("returns null when council disabled", async () => {
    const coordinator = createLiveAttackCoordinator({});
    const eng = { live_council: { enabled: false } };
    const result = await coordinator.emit(
      { type: "step_failed", engagement_id: "e1", step_number: 1 },
      { eng, engagementId: "e1", reqBody: { live_council: false } }
    );
    assert.equal(result, null);
  });

  it("guided autonomous source enables council by default", () => {
    assert.equal(isLiveCouncilEnabled({ source: "guided_autonomous" }, {}), true);
  });
});

describe("coordinator rate limit constant", () => {
  it("has sensible default rate limit", () => {
    assert.ok(RATE_LIMIT >= 1);
  });
});
