"use strict";

const { describe, it } = require("node:test");
const assert = require("node:assert/strict");
const {
  appendTerminalLine,
  getTerminalHistory,
  MAX_TERMINAL_LINES,
} = require("../terminal-buffer");

describe("terminal-buffer", () => {
  it("appends and returns recent lines", () => {
    const engagements = new Map();
    const engId = "buf12345";
    engagements.set(engId, { id: engId });

    appendTerminalLine(engagements, engId, {
      type: "info",
      content: "line one",
      timestamp: "2026-01-01T00:00:00.000Z",
    });
    appendTerminalLine(engagements, engId, {
      type: "success",
      content: "line two",
      timestamp: "2026-01-01T00:00:01.000Z",
    });

    const lines = getTerminalHistory(engagements, engId);
    assert.equal(lines.length, 2);
    assert.equal(lines[0].content, "line one");
    assert.equal(lines[1].type, "success");
  });

  it("caps history at MAX_TERMINAL_LINES", () => {
    const engagements = new Map();
    const engId = "cap12345";
    engagements.set(engId, { id: engId });

    for (let i = 0; i < MAX_TERMINAL_LINES + 10; i += 1) {
      appendTerminalLine(engagements, engId, {
        type: "info",
        content: `line ${i}`,
        timestamp: new Date().toISOString(),
      });
    }

    const eng = engagements.get(engId);
    assert.equal(eng.terminal_history.length, MAX_TERMINAL_LINES);
    assert.equal(getTerminalHistory(engagements, engId, 5).length, 5);
  });
});
