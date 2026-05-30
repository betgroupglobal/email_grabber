/** Guided 8-phase OpSec pentest wizard — types, persistence, prompt chaining. */

export const GUIDED_STORAGE_KEY = "opsecai_guided_assessment_v4";
export const DEFAULT_GUIDED_TARGET = "mobileciti.com.au";

export type GuidedStepNum = 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8;

export interface GuidedSubstep {
  id: string;
  label: string;
  done: boolean;
}

export interface GuidedChainSummary {
  chain_id?: string;
  index: number;
  title: string;
  confidence: number;
  stepCount: number;
  rejected: boolean;
}

/** Autonomous pipeline phase record — links to Live Attack Council turns */
export interface GuidedAutonomousPhaseRecord {
  phase_number: number;
  phase_key: string;
  title: string;
  status: string;
  ai_source?: string;
  narrative?: string;
  artifact_text?: string;
  recommended_actions?: string[];
  hub_results?: unknown[];
  council_turn?: number | null;
  council_turn_id?: string | null;
  completed_at?: string;
}

export interface GuidedAssessmentState {
  version: 4;
  currentStep: GuidedStepNum;
  targetRaw: string;
  roeAcknowledged: boolean;
  webAssetConfirmed: boolean;
  substeps: Record<GuidedStepNum, GuidedSubstep[]>;
  identifyNotes: string;
  reconNotes: string;
  vulnScanNotes: string;
  webAppNotes: string;
  exploitationNotes: string;
  privEscSkipped: boolean;
  postExploitEnabled: boolean;
  postExploitNotes: string;
  coveringTracksNotes: string;
  engagementId?: string;
  assessRiskScore?: number;
  chains: GuidedChainSummary[];
  assessRanAt?: string;
  updatedAt: string;
}

export interface StepMeta {
  step: GuidedStepNum;
  title: string;
  focus: string;
  artifact: string;
  timeBoxMin: number;
  timeBoxMax: number;
  disabled?: boolean;
  substeps: Omit<GuidedSubstep, "done">[];
}

export const STEP_ARTIFACT_KEYS: Record<
  GuidedStepNum,
  keyof Pick<
    GuidedAssessmentState,
    | "identifyNotes"
    | "reconNotes"
    | "vulnScanNotes"
    | "webAppNotes"
    | "exploitationNotes"
    | "postExploitNotes"
    | "coveringTracksNotes"
  >
> = {
  1: "identifyNotes",
  2: "reconNotes",
  3: "vulnScanNotes",
  4: "webAppNotes",
  5: "exploitationNotes",
  6: "identifyNotes",
  7: "postExploitNotes",
  8: "coveringTracksNotes",
};

export const GUIDED_STEPS: StepMeta[] = [
  {
    step: 1,
    title: "Identify target",
    focus: "Authorized target, web asset, ROE",
    artifact: "Target + scope lines",
    timeBoxMin: 10,
    timeBoxMax: 15,
    substeps: [
      { id: "1a", label: "Confirm mobileciti.com.au (or edit) in scope" },
      { id: "1b", label: "Mark asset as external web application" },
      { id: "1c", label: "Acknowledge rules of engagement" },
    ],
  },
  {
    step: 2,
    title: "Reconnaissance",
    focus: "Nmap — emphasize ports 80 & 443",
    artifact: "Recon notes (CDN, paths)",
    timeBoxMin: 20,
    timeBoxMax: 30,
    substeps: [
      { id: "2a", label: "Run or review Nmap (-sV) on 80/443" },
      { id: "2b", label: "Note Cloudflare / WAF in front of origin" },
      { id: "2c", label: "Optional: analyzer scan via Scanner API" },
    ],
  },
  {
    step: 3,
    title: "Vulnerability scanning",
    focus: "Nessus, Nikto, Knowledge Engine",
    artifact: "Scanner findings summary",
    timeBoxMin: 25,
    timeBoxMax: 40,
    substeps: [
      { id: "3a", label: "Run Nessus or Nikto against web surface" },
      { id: "3b", label: "Search Knowledge Engine for matching patterns" },
      { id: "3c", label: "Check Integration Hub for scanner plugins" },
    ],
  },
  {
    step: 4,
    title: "Web app testing",
    focus: "Burp/ZAP — SQLi, XSS, CSRF; OpSec assess",
    artifact: "Web test notes + chains",
    timeBoxMin: 30,
    timeBoxMax: 45,
    substeps: [
      { id: "4a", label: "Map auth, cart, and API flows in proxy" },
      { id: "4b", label: "Test SQLi / XSS / CSRF on high-value inputs" },
      { id: "4c", label: "Run OpSec assess (web context) for attack chains" },
    ],
  },
  {
    step: 5,
    title: "Exploitation",
    focus: "Metasploit or execute-chain",
    artifact: "Exploit evidence / dashboard link",
    timeBoxMin: 20,
    timeBoxMax: 35,
    substeps: [
      { id: "5a", label: "Select chain from OpSec assess (phase 4)" },
      { id: "5b", label: "Execute via Attack Dashboard or Metasploit" },
      { id: "5c", label: "Record outcome (success / blocked / inconclusive)" },
    ],
  },
  {
    step: 6,
    title: "Privilege escalation",
    focus: "N/A — external web-only",
    artifact: "Skipped (documented)",
    timeBoxMin: 0,
    timeBoxMax: 0,
    disabled: true,
    substeps: [
      { id: "6a", label: "Acknowledge: no internal foothold — priv esc N/A" },
      { id: "6b", label: "If foothold obtained, use post-exploitation (phase 7)" },
    ],
  },
  {
    step: 7,
    title: "Post-exploitation",
    focus: "Optional — only with foothold",
    artifact: "Post-exploit notes (if any)",
    timeBoxMin: 0,
    timeBoxMax: 20,
    substeps: [
      { id: "7a", label: "Confirm whether a foothold exists" },
      { id: "7b", label: "If yes: limited actions per ROE" },
      { id: "7c", label: "If no: skip and proceed to covering tracks" },
    ],
  },
  {
    step: 8,
    title: "Covering tracks",
    focus: "OpSec awareness and tool hygiene",
    artifact: "OpSec cleanup checklist",
    timeBoxMin: 10,
    timeBoxMax: 15,
    substeps: [
      { id: "8a", label: "Review tool traces and proxy logs" },
      { id: "8b", label: "Run OpSec audit on chains (OpSec Tools)" },
      { id: "8c", label: "Finalize report and handoff notes" },
    ],
  },
];

export function defaultGuidedState(): GuidedAssessmentState {
  const substeps = {} as Record<GuidedStepNum, GuidedSubstep[]>;
  for (const meta of GUIDED_STEPS) {
    substeps[meta.step] = meta.substeps.map((s) => ({ ...s, done: false }));
  }
  return {
    version: 4,
    currentStep: 1,
    targetRaw: DEFAULT_GUIDED_TARGET,
    roeAcknowledged: false,
    webAssetConfirmed: false,
    substeps,
    identifyNotes: "",
    reconNotes: "",
    vulnScanNotes: "",
    webAppNotes: "",
    exploitationNotes: "",
    privEscSkipped: false,
    postExploitEnabled: false,
    postExploitNotes: "",
    coveringTracksNotes: "",
    chains: [],
    updatedAt: new Date().toISOString(),
  };
}

function migrateLegacy(parsed: Record<string, unknown>): GuidedAssessmentState {
  const base = defaultGuidedState();
  return {
    ...base,
    currentStep: Math.min(8, Math.max(1, Number(parsed.currentStep) || 1)) as GuidedStepNum,
    targetRaw: String(parsed.targetRaw || DEFAULT_GUIDED_TARGET),
    roeAcknowledged: Boolean(parsed.roeAcknowledged),
    webAssetConfirmed: Boolean(
      parsed.webAssetConfirmed ?? parsed.webFocusConfirmed
    ),
    identifyNotes: String(parsed.identifyNotes ?? parsed.scopeDoc ?? ""),
    reconNotes: String(parsed.reconNotes ?? parsed.passiveRecon ?? ""),
    vulnScanNotes: String(parsed.vulnScanNotes ?? parsed.surfaceMap ?? ""),
    webAppNotes: String(
      [parsed.webAppNotes, parsed.threatModel, parsed.testPlan]
        .filter((s) => typeof s === "string" && s.trim())
        .join("\n\n")
    ),
    exploitationNotes: String(
      parsed.exploitationNotes ?? parsed.executeEvidence ?? ""
    ),
    coveringTracksNotes: String(
      parsed.coveringTracksNotes ?? parsed.synthesisReport ?? ""
    ),
    privEscSkipped: Boolean(parsed.privEscSkipped),
    postExploitEnabled: Boolean(parsed.postExploitEnabled),
    postExploitNotes: String(parsed.postExploitNotes ?? ""),
    engagementId: parsed.engagementId as string | undefined,
    assessRiskScore: parsed.assessRiskScore as number | undefined,
    chains: Array.isArray(parsed.chains) ? (parsed.chains as GuidedChainSummary[]) : [],
    assessRanAt: parsed.assessRanAt as string | undefined,
    substeps: (parsed.substeps as GuidedAssessmentState["substeps"]) || base.substeps,
  };
}

export function loadGuidedState(): GuidedAssessmentState | null {
  if (typeof window === "undefined") return null;
  try {
    for (const key of [
      GUIDED_STORAGE_KEY,
      "opsecai_guided_assessment_v3",
      "opsecai_guided_assessment_v2",
      "opsecai_guided_assessment_v1",
    ]) {
      const raw = localStorage.getItem(key);
      if (!raw) continue;
      const parsed = JSON.parse(raw) as Record<string, unknown>;
      if (parsed?.version === 4) return parsed as unknown as GuidedAssessmentState;
      const migrated = migrateLegacy(parsed);
      saveGuidedState(migrated);
      return migrated;
    }
    return null;
  } catch {
    return null;
  }
}

export function saveGuidedState(state: GuidedAssessmentState): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(
    GUIDED_STORAGE_KEY,
    JSON.stringify({ ...state, updatedAt: new Date().toISOString() })
  );
}

export function getStepArtifact(state: GuidedAssessmentState, step: GuidedStepNum): string {
  if (step === 6) {
    return state.privEscSkipped
      ? "Skipped — external web-only (no foothold)."
      : "";
  }
  const key = STEP_ARTIFACT_KEYS[step];
  return String(state[key] ?? "");
}

export function priorContextForStep(
  state: GuidedAssessmentState,
  throughStep: GuidedStepNum
): string {
  const parts: string[] = [];
  if (state.targetRaw.trim()) parts.push(`Target: ${state.targetRaw.trim()}`);
  for (let s = 1 as GuidedStepNum; s <= throughStep; s = (s + 1) as GuidedStepNum) {
    const meta = GUIDED_STEPS.find((m) => m.step === s);
    const text = getStepArtifact(state, s).trim();
    if (text && meta) parts.push(`--- ${meta.title} (phase ${s}) ---\n${text}`);
  }
  return parts.join("\n\n");
}

export function buildAiPromptForStep(
  step: GuidedStepNum,
  state: GuidedAssessmentState
): string {
  const meta = GUIDED_STEPS.find((s) => s.step === step)!;
  const prior =
    step > 1 ? priorContextForStep(state, (step - 1) as GuidedStepNum) : "";
  const instructions: Record<GuidedStepNum, string> = {
    1: "Confirm mobileciti.com.au as external web asset. Draft ROE: objective, in-scope URLs, out-of-scope, stop conditions.",
    2: "Summarize recon for Cloudflare-fronted e-commerce: Nmap 80/443, CDN, tech stack. Max 12 bullets.",
    3: "List vuln scan approach (Nessus/Nikto) and findings to verify. Reference KE / Integration Hub.",
    4: "Plan Burp/ZAP tests: SQLi, XSS, CSRF. Note OpSec assess chains for exploitation.",
    5: "Recommend one exploitation path; Metasploit vs execute-chain; evidence to capture.",
    6: "Explain why privilege escalation is out of scope for external web-only.",
    7: "If foothold exists, outline limited post-exploit per ROE; else state skip.",
    8: "Covering tracks: OpSec hygiene, audit chains, executive summary.",
  };
  return [
    `Guided OpSec pentest — Phase ${step}: ${meta.title}`,
    instructions[step],
    prior ? `\nPrior phases:\n${prior}` : "",
  ]
    .filter(Boolean)
    .join("\n");
}

export function buildSynthesisReport(state: GuidedAssessmentState): string {
  const target = state.targetRaw.trim() || DEFAULT_GUIDED_TARGET;
  const accepted = state.chains.filter((c) => !c.rejected);
  return [
    "# Guided OpSec Pentest Report",
    "",
    `**Target:** ${target}`,
    state.engagementId ? `**Engagement:** ${state.engagementId}` : "",
    state.assessRiskScore != null ? `**OpSec risk:** ${state.assessRiskScore}/100` : "",
    "",
    "## 1. Identify target",
    state.identifyNotes.trim() || "_Not recorded._",
    "",
    "## 2. Reconnaissance",
    state.reconNotes.trim() || "_Not recorded._",
    "",
    "## 3. Vulnerability scanning",
    state.vulnScanNotes.trim() || "_Not recorded._",
    "",
    "## 4. Web application testing",
    state.webAppNotes.trim() || "_Not recorded._",
    "",
    "## 5. Exploitation",
    state.exploitationNotes.trim() || "_Not recorded._",
    "",
    "## 6. Privilege escalation",
    state.privEscSkipped
      ? "_Skipped — external web-only._"
      : "_Not applicable._",
    "",
    "## 7. Post-exploitation",
    state.postExploitEnabled
      ? state.postExploitNotes.trim() || "_Enabled but empty._"
      : "_Skipped — no foothold._",
    "",
    "## 8. Covering tracks",
    state.coveringTracksNotes.trim() || "_Not recorded._",
    "",
    "## Attack chains",
    accepted.length
      ? accepted
          .map(
            (c) =>
              `- ${c.title} (${Math.round(c.confidence * 100)}%, ${c.stepCount} steps)`
          )
          .join("\n")
      : "_Run OpSec assess on phase 4._",
    "",
    `_Generated ${new Date().toLocaleString()}_`,
  ].join("\n");
}

export function aiChatUrl(prompt: string, engagementId?: string): string {
  const params = new URLSearchParams();
  params.set("prompt", prompt);
  if (engagementId) {
    params.set("mode", "engagement");
    params.set("engagement", engagementId);
  }
  return `/ai-chat?${params.toString()}`;
}

/** Resolve council turn label for a guided phase record */
export function councilTurnLabel(phase: GuidedAutonomousPhaseRecord): string | null {
  if (phase.council_turn_id) return phase.council_turn_id.slice(0, 8);
  if (phase.council_turn != null) return `turn-${phase.council_turn}`;
  return null;
}

/** Merge autonomous phase records with council directive IDs for timeline display */
export function linkPhasesToCouncilTurns(
  phases: GuidedAutonomousPhaseRecord[],
  directives?: Array<{ directive_id?: string; turn?: number }>
): GuidedAutonomousPhaseRecord[] {
  if (!directives?.length) return phases;
  const byTurn = new Map<number, string>();
  for (const d of directives) {
    if (d.turn != null && d.directive_id) byTurn.set(d.turn, d.directive_id);
  }
  return phases.map((p) => {
    if (p.council_turn_id) return p;
    const turnId = p.council_turn != null ? byTurn.get(p.council_turn) : undefined;
    return turnId ? { ...p, council_turn_id: turnId } : p;
  });
}
