/** Modular OODA-style thought process cycle — shared stage IDs with backend/orchestrator/reasoning-pattern.js */

export const THOUGHT_PROCESS_CYCLE = [
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
] as const;

export type ThoughtCycleStageId = (typeof THOUGHT_PROCESS_CYCLE)[number]["id"];

export type ThoughtCycleStage = (typeof THOUGHT_PROCESS_CYCLE)[number];

export type SubtaskStatus = "pending" | "in_progress" | "complete";

export interface SubtaskProgress {
  id: string;
  label: string;
  status: SubtaskStatus;
}

/** Stable id for a subtask within a stage (used in trace + terminal [think] lines). */
export function subtaskId(stageId: ThoughtCycleStageId, index: number): string {
  return `${stageId}:${index}`;
}

export function getStageById(id: string): ThoughtCycleStage | undefined {
  return THOUGHT_PROCESS_CYCLE.find((s) => s.id === id);
}

export function getStageIndex(id: ThoughtCycleStageId): number {
  return THOUGHT_PROCESS_CYCLE.findIndex((s) => s.id === id);
}

export function getNextStage(id: ThoughtCycleStageId): ThoughtCycleStageId | null {
  const idx = getStageIndex(id);
  if (idx < 0 || idx >= THOUGHT_PROCESS_CYCLE.length - 1) return null;
  return THOUGHT_PROCESS_CYCLE[idx + 1].id;
}

export const STAGE_LABELS: Record<ThoughtCycleStageId, string> = Object.fromEntries(
  THOUGHT_PROCESS_CYCLE.map((s) => [s.id, s.stage])
) as Record<ThoughtCycleStageId, string>;

export const THOUGHT_PATTERN_STEPS = THOUGHT_PROCESS_CYCLE.map((s) => s.id) as readonly ThoughtCycleStageId[];
