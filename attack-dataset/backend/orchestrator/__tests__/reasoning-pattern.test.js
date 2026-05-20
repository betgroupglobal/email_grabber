"use strict";

const { describe, it } = require("node:test");
const assert = require("node:assert/strict");
const {
  inferPatternStep,
  inferSubtaskId,
  enrichReasoningEntry,
  appendReasoningTrace,
  THOUGHT_PATTERN_STEPS,
  THOUGHT_PROCESS_CYCLE,
  getStageById,
  getNextStage,
  formatThinkLine,
} = require("../reasoning-pattern");

describe("reasoning-pattern", () => {
  it("exports seven pattern steps aligned with cycle", () => {
    assert.equal(THOUGHT_PATTERN_STEPS.length, 7);
    assert.equal(THOUGHT_PROCESS_CYCLE.length, 7);
    assert.ok(THOUGHT_PATTERN_STEPS.includes("orient"));
    assert.ok(THOUGHT_PATTERN_STEPS.includes("reflect"));
  });

  it("cycle stages include objective and subtasks", () => {
    const probe = getStageById("probe");
    assert.equal(probe.stage, "Probe");
    assert.ok(probe.objective.includes("intelligence"));
    assert.ok(probe.subtasks.length >= 4);
  });

  it("getNextStage walks the cycle", () => {
    assert.equal(getNextStage("orient"), "hypothesize");
    assert.equal(getNextStage("reflect"), null);
  });

  it("infers pivot from pivot_chain action", () => {
    assert.equal(
      inferPatternStep({ source: "live_council", action: "pivot_chain" }),
      "pivot"
    );
  });

  it("infers evaluate from council_turn", () => {
    assert.equal(
      inferPatternStep({ source: "council_turn", failure_class: "tool_error" }),
      "evaluate"
    );
  });

  it("infers reflect from guided phase narrative", () => {
    assert.equal(
      inferPatternStep({
        source: "guided_autonomous",
        phase_number: 2,
        narrative: "Recon complete",
      }),
      "reflect"
    );
  });

  it("infers probe subtask from scan metadata", () => {
    const id = inferSubtaskId({
      source: "guided_autonomous",
      trigger: "scan_started",
      scan_type: "nmap",
    });
    assert.equal(id, "probe:1");
  });

  it("enrichReasoningEntry adds stage, objective, subtasks, and rationale", () => {
    const e = enrichReasoningEntry({
      source: "council_turn",
      turn: 2,
      rationale: "Continue after scan delta",
    });
    assert.equal(e.pattern_step, "evaluate");
    assert.equal(e.stage, "Evaluate");
    assert.equal(e.objective, getStageById("evaluate").objective);
    assert.deepEqual(e.subtasks, getStageById("evaluate").subtasks);
    assert.equal(e.rationale, "Continue after scan delta");
    assert.equal(e.subtask_id, "evaluate:3");
  });

  it("formatThinkLine includes subtask id when present", () => {
    const line = formatThinkLine({
      stage: "Probe",
      subtaskId: "probe:2",
      rationale: "Nmap quick scan",
    });
    assert.match(line, /^\[think\] Probe · probe:2 — Nmap quick scan$/);
  });

  it("appendReasoningTrace broadcasts reasoning_thought with cycle fields", () => {
    const eng = { reasoning_trace: [] };
    const sent = [];
    const terminal = [];
    appendReasoningTrace(
      eng,
      { source: "guided_autonomous", phase_number: 1, phase_key: "identify", title: "Identify" },
      {
        engagementId: "abc12345",
        broadcastCouncil: (_id, payload) => sent.push(payload),
        broadcastTerminal: (_id, line) => terminal.push(line),
      }
    );
    assert.equal(eng.reasoning_trace.length, 1);
    assert.equal(eng.reasoning_trace[0].pattern_step, "orient");
    assert.ok(eng.reasoning_trace[0].objective);
    assert.ok(Array.isArray(eng.reasoning_trace[0].subtasks));
    assert.equal(sent.length, 1);
    assert.equal(sent[0].type, "reasoning_thought");
    assert.equal(sent[0].thought.pattern_step, "orient");
    assert.ok(terminal.length >= 0);
  });
});
