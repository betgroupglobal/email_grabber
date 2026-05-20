"use strict";

const { describe, it, before, after } = require("node:test");
const assert = require("node:assert/strict");

const POSTGRES_DSN = process.env.POSTGRES_DSN;
const canRun = Boolean(POSTGRES_DSN);

describe("engagement persistence", { skip: !canRun ? "POSTGRES_DSN not set" : false }, () => {
  let EngagementStore;
  let store;
  const testId = `test-${Date.now().toString(36)}`;

  before(async () => {
    EngagementStore = require("../engagement-store");
    store = new EngagementStore();
    await store.ready;
  });

  after(async () => {
    if (store) {
      await store.deleteEngagement(testId);
      await store.close();
    }
  });

  it("upserts and reloads full engagement payload", async () => {
    const doc = {
      id: testId,
      target: "example.com",
      status: "complete",
      source: "opsec_assessment",
      attack_chains: { chains: [{ id: "c1" }] },
      opsec_reports: { risk_score: 42 },
      chain_execution: { status: "completed", steps: [] },
      guided_autonomous: { status: "done", phases: [] },
      log: [{ ts: new Date().toISOString(), msg: "test" }],
      started_at: new Date().toISOString(),
    };

    await store.upsertEngagement(doc);
    const loaded = await store.getEngagement(testId);
    assert.equal(loaded.id, testId);
    assert.equal(loaded.target, "example.com");
    assert.equal(loaded.source, "opsec_assessment");
    assert.deepEqual(loaded.attack_chains, doc.attack_chains);
    assert.deepEqual(loaded.chain_execution, doc.chain_execution);
    assert.equal(loaded.log.length, 1);
  });
});
