"use strict";

const { describe, it } = require("node:test");
const assert = require("node:assert/strict");
const {
  classifyFailure,
  suggestActionForFailure,
} = require("../failure-taxonomy");

describe("failure-taxonomy", () => {
  it("classifies WAF blocks as tool_blocked", () => {
    const result = classifyFailure({
      type: "step_failed",
      step_result: { output: "403 Forbidden — WAF blocked request" },
    });
    assert.equal(result.failure_class, "tool_blocked");
  });

  it("classifies auth failures", () => {
    const result = classifyFailure({
      type: "step_failed",
      step_result: { output: "401 Unauthorized invalid credentials" },
    });
    assert.equal(result.failure_class, "auth_failed");
  });

  it("suggests pivot for wrong_vector", () => {
    assert.equal(suggestActionForFailure("wrong_vector", "step_failed"), "pivot_chain");
  });

  it("suggests continue on success", () => {
    assert.equal(suggestActionForFailure("none", "step_completed"), "continue");
  });
});
