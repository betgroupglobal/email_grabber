"use strict";

/** Recognizable AI thought-process stages when facing a target */
const THOUGHT_PROCESS_CYCLE = [
  {
    id: "orient",
    stage: "Orient",
    objective: "Parse target, scope, ROE, and constraints",
    subtasks: [
      "Extract target URL(s), IP ranges, domains",
      "Identify in-scope vs out-of-scope assets",
      "Note Rules of Engagement, time windows, and legal constraints",
      "Record objectives and success criteria",
      "Map known contact points / defense layers",
    ],
  },
  {
    id: "hypothesize",
    stage: "Hypothesize",
    objective: "Form initial assumptions about attack surface",
    subtasks: [
      "List likely attack vectors (web, API, auth, supply chain, human, etc.)",
      "Identify high-value targets and crown jewels",
      "Create initial threat model",
      "Prioritise assumptions to test first",
    ],
  },
  {
    id: "probe",
    stage: "Probe",
    objective: "Actively gather intelligence and test assumptions",
    subtasks: [
      "Passive recon (OSINT, DNS, certificates, archives)",
      "Active scanning & enumeration",
      "Tool execution (Nmap, nuclei, ffuf, etc.)",
      "Initial influence / social engineering probes",
      "Log all findings with timestamps",
    ],
  },
  {
    id: "evaluate",
    stage: "Evaluate",
    objective: "Assess results and risks",
    subtasks: [
      "Analyse findings for validity and impact",
      "Evaluate OpSec / detection risk",
      "Review failures and unexpected behaviours",
      'Consult "council" / second opinion if high risk',
      "Score confidence and potential value of each lead",
    ],
  },
  {
    id: "pivot",
    stage: "Pivot",
    objective: "Change direction when current path stalls",
    subtasks: [
      "Identify dead ends or blocked paths",
      "Select alternate vectors or chaining opportunities",
      "Adjust scope or depth (deeper on one target vs broader coverage)",
      "Retry with modified TTPs (tools, techniques, procedures)",
    ],
  },
  {
    id: "commit",
    stage: "Commit",
    objective: "Execute decisive action",
    subtasks: [
      "Launch exploit / payload",
      "Establish persistence",
      "Move laterally / escalate",
      "Exfiltrate data (if authorised)",
      "Apply chosen directive (continue, expand, or abort step)",
    ],
  },
  {
    id: "reflect",
    stage: "Reflect",
    objective: "Learn and improve the next loop",
    subtasks: [
      "Document what worked, what failed, and why",
      "Capture lessons learned and new assumptions",
      "Update threat model and playbook",
      "Feed insights into the next Orient phase",
      "Reset or maintain access as required",
    ],
  },
];

const THOUGHT_PATTERN_STEPS = THOUGHT_PROCESS_CYCLE.map((s) => s.id);

const STAGE_LABELS = Object.fromEntries(
  THOUGHT_PROCESS_CYCLE.map((s) => [s.id, s.stage])
);

function getStageById(id) {
  return THOUGHT_PROCESS_CYCLE.find((s) => s.id === id);
}

function getNextStage(id) {
  const idx = THOUGHT_PROCESS_CYCLE.findIndex((s) => s.id === id);
  if (idx < 0 || idx >= THOUGHT_PROCESS_CYCLE.length - 1) return null;
  return THOUGHT_PROCESS_CYCLE[idx + 1].id;
}

function subtaskId(stageId, index) {
  return `${stageId}:${index}`;
}

function isValidStep(step) {
  return THOUGHT_PATTERN_STEPS.includes(step);
}

/**
 * Infer pattern_step from reasoning trace entry metadata.
 */
function inferPatternStep(entry) {
  if (entry?.pattern_step && isValidStep(entry.pattern_step)) {
    return entry.pattern_step;
  }

  const source = String(entry?.source || "");
  const action = String(entry?.action || "");
  const trigger = String(entry?.trigger || entry?.event || "");
  const phaseNum = entry?.phase_number;
  const phaseKey = String(entry?.phase_key || "");

  if (
    action === "pivot_chain" ||
    action === "reinitiate_chain" ||
    trigger.includes("pathway") ||
    entry?.pathway_id
  ) {
    return "pivot";
  }

  if (
    action === "patch_chain" ||
    (source === "live_council" && action && action !== "pause" && action !== "abort")
  ) {
    return "commit";
  }

  if (source === "council_turn" || entry?.failure_class) {
    return "evaluate";
  }

  if (source === "guided_autonomous" && (entry?.narrative || entry?.artifact_text)) {
    return "reflect";
  }

  if (phaseKey === "identify" || phaseNum === 1) {
    return "orient";
  }

  if (
    trigger.includes("scan") ||
    entry?.scan_type ||
    String(entry?.hub_operation || "").length > 0 ||
    (source === "guided_autonomous" && phaseNum != null && phaseNum <= 4 && !entry?.narrative)
  ) {
    return "probe";
  }

  if (phaseNum != null && phaseNum <= 3) {
    return "hypothesize";
  }

  if (source === "coordinator" || trigger.includes("step_completed")) {
    return "evaluate";
  }

  if (entry?.note || entry?.rationale_steps?.length) {
    return "reflect";
  }

  return "orient";
}

function inferSubtaskIndex(entry, step) {
  if (entry?.subtask_id && /^[^:]+:(\d+)$/.test(String(entry.subtask_id))) {
    return Number(String(entry.subtask_id).split(":")[1]);
  }

  const source = String(entry?.source || "");
  const action = String(entry?.action || "");
  const trigger = String(entry?.trigger || entry?.event || "");
  const phaseKey = String(entry?.phase_key || "");

  switch (step) {
    case "orient":
      if (entry?.target || phaseKey === "identify") return 0;
      if (entry?.scope || entry?.roe) return 2;
      if (entry?.objectives) return 3;
      return 0;
    case "hypothesize":
      if (entry?.attack_vectors) return 0;
      if (entry?.crown_jewels) return 1;
      if (entry?.threat_model) return 2;
      if (phaseKey || entry?.phase_number != null) return 3;
      return 0;
    case "probe":
      if (trigger.includes("osint") || trigger.includes("passive")) return 0;
      if (entry?.scan_type || trigger.includes("scan") || entry?.invoke_scan) return 1;
      if (entry?.hub_operation || trigger.includes("nmap") || trigger.includes("nuclei")) return 2;
      if (trigger.includes("social") || trigger.includes("influence")) return 3;
      if (entry?.ts || entry?.note) return 4;
      if (entry?.hub_operation) return 2;
      return 1;
    case "evaluate":
      if (source === "council_turn") return 3;
      if (entry?.failure_class) return 2;
      if (entry?.opsec || trigger.includes("opsec")) return 1;
      if (entry?.confidence != null) return 4;
      return 0;
    case "pivot":
      if (action === "pivot_chain" || action === "reinitiate_chain") return 1;
      if (entry?.pathway_id) return 1;
      if (entry?.scope_adjustment) return 2;
      if (entry?.ttp || trigger.includes("retry")) return 3;
      return 0;
    case "commit":
      if (action === "patch_chain") return 0;
      if (entry?.persistence) return 1;
      if (entry?.lateral || trigger.includes("escalat")) return 2;
      if (entry?.exfil) return 3;
      if (action === "continue" || action === "expand" || action === "abort") return 4;
      return 4;
    case "reflect":
      if (entry?.lessons_learned) return 1;
      if (entry?.playbook || entry?.threat_model) return 2;
      if (entry?.feed_orient) return 3;
      if (entry?.narrative || entry?.artifact_text) return 0;
      return 0;
    default:
      return undefined;
  }
}

function inferSubtaskId(entry, step) {
  const stage = step || inferPatternStep(entry);
  const idx = inferSubtaskIndex(entry, stage);
  if (idx == null) return undefined;
  return subtaskId(stage, idx);
}

function buildRationale(entry) {
  if (entry?.rationale) return String(entry.rationale);
  if (entry?.narrative) return String(entry.narrative);
  if (entry?.note) return String(entry.note);
  if (entry?.rationale_steps?.length) {
    return entry.rationale_steps
      .map((s) => `${s.step}: ${s.detail}`)
      .join(" · ")
      .slice(0, 500);
  }
  const parts = [];
  if (entry?.title) parts.push(entry.title);
  if (entry?.action) parts.push(`action ${entry.action}`);
  if (entry?.failure_class) parts.push(`failure ${entry.failure_class}`);
  if (entry?.trigger) parts.push(`trigger ${entry.trigger}`);
  return parts.join(" — ") || "";
}

function formatThinkLine({ stage, rationale, subtaskId: stId, action, fallback }) {
  const prefix = stId ? `[think] ${stage} · ${stId}` : `[think] ${stage}`;
  const actionBit = action ? ` · ${action}` : "";
  if (rationale) return `${prefix}${actionBit} — ${String(rationale).slice(0, 240)}`;
  return `${prefix}${actionBit} — ${fallback || "reasoning"}`;
}

/**
 * Normalize trace entry with pattern_step, stage, objective, subtasks, and rationale.
 */
function enrichReasoningEntry(entry) {
  const pattern_step = inferPatternStep(entry || {});
  const cycleStage = getStageById(pattern_step);
  const stage = STAGE_LABELS[pattern_step] || pattern_step;
  const rationale = buildRationale(entry || {});
  const subtask_id = inferSubtaskId(entry || {}, pattern_step);
  return {
    ...entry,
    pattern_step,
    stage,
    objective: cycleStage?.objective,
    subtasks: cycleStage?.subtasks ? [...cycleStage.subtasks] : undefined,
    subtask_id,
    rationale: rationale || undefined,
  };
}

/**
 * Append to engagement reasoning_trace and optionally stream via council WS.
 */
function appendReasoningTrace(eng, entry, opts = {}) {
  const enriched = enrichReasoningEntry({
    ...entry,
    ts: entry?.ts || new Date().toISOString(),
  });
  eng.reasoning_trace = eng.reasoning_trace || [];
  eng.reasoning_trace.push(enriched);
  if (eng.reasoning_trace.length > 100) eng.reasoning_trace.shift();

  const { broadcastCouncil, engagementId, broadcastTerminal } = opts;
  if (broadcastCouncil && engagementId) {
    broadcastCouncil(engagementId, {
      type: "reasoning_thought",
      thought: enriched,
    });
  }
  if (broadcastTerminal && engagementId && enriched.rationale) {
    const label = STAGE_LABELS[enriched.pattern_step] || enriched.pattern_step;
    broadcastTerminal(
      engagementId,
      formatThinkLine({
        stage: label,
        rationale: enriched.rationale,
        subtaskId: enriched.subtask_id,
        action: enriched.action,
      }),
      "info"
    );
  }
  return enriched;
}

module.exports = {
  THOUGHT_PROCESS_CYCLE,
  THOUGHT_PATTERN_STEPS,
  STAGE_LABELS,
  getStageById,
  getNextStage,
  subtaskId,
  inferPatternStep,
  inferSubtaskId,
  enrichReasoningEntry,
  appendReasoningTrace,
  formatThinkLine,
};
