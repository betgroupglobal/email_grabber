"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  AlertTriangle,
  Check,
  ChevronLeft,
  ChevronRight,
  Copy,
  ExternalLink,
  Link2,
  ListChecks,
  RotateCcw,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { analyzerHttp } from "@/lib/config";
import { assessOpsecTarget } from "@/lib/orchestratorClient";
import { normalizeTargetInput } from "@/lib/targetUtils";
import {
  aiChatUrl,
  buildAiPromptForStep,
  buildSynthesisReport,
  defaultGuidedState,
  DEFAULT_GUIDED_TARGET,
  getStepArtifact,
  GUIDED_STORAGE_KEY,
  GUIDED_STEPS,
  loadGuidedState,
  saveGuidedState,
  type GuidedAssessmentState,
  type GuidedChainSummary,
  type GuidedStepNum,
  type GuidedSubstep,
} from "@/lib/guidedAssessment";

const MAX_STEP = 8 as GuidedStepNum;

export function GuidedAssessmentWizard() {
  const router = useRouter();
  const [state, setState] = useState<GuidedAssessmentState>(defaultGuidedState);
  const [hydrated, setHydrated] = useState(false);
  const [assessLoading, setAssessLoading] = useState(false);
  const [scanLoading, setScanLoading] = useState(false);
  const [copyHint, setCopyHint] = useState<string | null>(null);

  useEffect(() => {
    const saved = loadGuidedState();
    if (saved) setState(saved);
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    saveGuidedState(state);
  }, [state, hydrated]);

  const patch = useCallback((partial: Partial<GuidedAssessmentState>) => {
    setState((prev) => ({ ...prev, ...partial }));
  }, []);

  const meta = GUIDED_STEPS.find((s) => s.step === state.currentStep)!;
  const normalizedTarget = normalizeTargetInput(state.targetRaw);

  const canLeaveStep1 =
    state.roeAcknowledged && state.webAssetConfirmed && normalizedTarget.length > 0;

  const canRunAssess =
    state.webAssetConfirmed &&
    normalizedTarget.length > 0 &&
    (state.reconNotes.trim().length > 0 || state.webAppNotes.trim().length > 0);

  const priorStep = state.currentStep > 1 ? ((state.currentStep - 1) as GuidedStepNum) : null;
  const priorArtifact = priorStep ? getStepArtifact(state, priorStep) : "";
  const priorLabel = priorStep
    ? GUIDED_STEPS.find((s) => s.step === priorStep)?.title
    : null;

  const toggleSubstep = (step: GuidedStepNum, id: string) => {
    setState((prev) => {
      const list = prev.substeps[step].map((s) =>
        s.id === id ? { ...s, done: !s.done } : s
      );
      return { ...prev, substeps: { ...prev.substeps, [step]: list } };
    });
  };

  const goStep = (step: GuidedStepNum) => {
    if (step > 1 && !canLeaveStep1) return;
    patch({ currentStep: step });
  };

  const runPassiveScan = async () => {
    if (!normalizedTarget) return;
    setScanLoading(true);
    try {
      const res = await fetch(analyzerHttp("/scan"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          target: normalizedTarget,
          scan_timeout_sec: 45,
          scan_args: ["-p", "80,443", "--open", "-T3", "-sV", "-oX", "-"],
        }),
      });
      if (res.ok) {
        const data = await res.json();
        patch({
          reconNotes: [
            state.reconNotes.trim(),
            `[Analyzer scan — session ${data.session_id || data.id || "pending"}]`,
            "Ports 80/443. View in Scanner.",
          ]
            .filter(Boolean)
            .join("\n"),
        });
      }
    } finally {
      setScanLoading(false);
    }
  };

  const runOpsecAssess = async () => {
    if (!canRunAssess) return;
    setAssessLoading(true);
    try {
      const result = await assessOpsecTarget({
        target: normalizedTarget,
        operation_type: "web_application",
      });
      if (!result.ok) return;
      const data = result.data;
      const chains: GuidedChainSummary[] = (data.attack_chains?.chains || []).map(
        (c, index) => {
          const steps = c.steps || [];
          const first = steps[0] as { attack?: { title?: string }; phase?: string } | undefined;
          const title = first?.attack?.title || first?.phase || `Chain ${index + 1}`;
          return {
            chain_id: c.chain_id,
            index,
            title,
            confidence: c.confidence ?? 0.5,
            stepCount: steps.length || c.steps_count || 0,
            rejected: false,
          };
        }
      );
      const webSeed = chains.length
        ? [
            state.webAppNotes.trim(),
            "",
            "--- OpSec assess (web) ---",
            ...chains.map(
              (c, i) =>
                `${i + 1}. ${c.title} (${c.stepCount} steps, ${Math.round(c.confidence * 100)}%)`
            ),
          ].join("\n")
        : state.webAppNotes;

      patch({
        engagementId: data.engagement_id,
        assessRiskScore: data.overall_score ?? data.risk_score,
        chains,
        webAppNotes: webSeed,
        assessRanAt: new Date().toISOString(),
      });
    } finally {
      setAssessLoading(false);
    }
  };

  const toggleChainRejected = (index: number) => {
    patch({
      chains: state.chains.map((c) =>
        c.index === index ? { ...c, rejected: !c.rejected } : c
      ),
    });
  };

  const copyPrompt = async () => {
    await navigator.clipboard.writeText(buildAiPromptForStep(state.currentStep, state));
    setCopyHint("Copied");
    setTimeout(() => setCopyHint(null), 2000);
  };

  const resetWizard = () => {
    if (!confirm("Clear guided assessment progress?")) return;
    [
      GUIDED_STORAGE_KEY,
      "opsecai_guided_assessment_v3",
      "opsecai_guided_assessment_v2",
      "opsecai_guided_assessment_v1",
    ].forEach((k) => localStorage.removeItem(k));
    setState(defaultGuidedState());
  };

  if (!hydrated) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center text-slate-500">
        Loading wizard…
      </div>
    );
  }

  return (
    <div className="space-y-6 text-white">
      <nav className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 backdrop-blur-sm">
        <ol className="flex flex-wrap gap-1.5">
          {GUIDED_STEPS.map((s) => {
            const active = s.step === state.currentStep;
            const done = s.step < state.currentStep;
            const locked = s.step > 1 && !canLeaveStep1;
            return (
              <li key={s.step}>
                <button
                  type="button"
                  disabled={locked}
                  onClick={() => goStep(s.step)}
                  title={s.title}
                  className={`flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-[10px] font-medium sm:px-3 sm:text-xs ${
                    active
                      ? "bg-cyan-600 text-white"
                      : done
                        ? "bg-slate-800 text-cyan-400"
                        : "bg-slate-950/50 text-slate-500 hover:text-slate-300"
                  } ${locked ? "cursor-not-allowed opacity-40" : ""}`}
                >
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-slate-800 text-[9px] sm:h-6 sm:w-6">
                    {done ? <Check className="h-3 w-3" /> : s.step}
                  </span>
                  <span className="hidden md:inline max-w-[5.5rem] truncate">{s.title}</span>
                </button>
              </li>
            );
          })}
        </ol>
        <p className="mt-3 text-xs text-slate-500">
          Phase {state.currentStep}: {meta.focus}
          {meta.timeBoxMax > 0 && (
            <>
              {" "}
              · Time box{" "}
              <span className="text-cyan-400/80">
                {meta.timeBoxMin}–{meta.timeBoxMax} min
              </span>
            </>
          )}
          {" "}
          · Output: {meta.artifact}
        </p>
      </nav>

      <div className="grid gap-6 lg:grid-cols-3">
        <aside className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 lg:col-span-1">
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold">
            <ListChecks className="h-4 w-4 text-cyan-400" />
            Checklist
          </h2>
          <ul className="space-y-2">
            {state.substeps[state.currentStep].map((sub: GuidedSubstep) => (
              <li key={sub.id}>
                <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-slate-800/80 bg-slate-950/30 px-3 py-2 hover:bg-slate-900/80">
                  <input
                    type="checkbox"
                    checked={sub.done}
                    onChange={() => toggleSubstep(state.currentStep, sub.id)}
                    className="mt-0.5 h-4 w-4 rounded border-slate-600 text-cyan-600"
                  />
                  <span
                    className={`text-sm ${sub.done ? "text-slate-500 line-through" : "text-slate-300"}`}
                  >
                    {sub.label}
                  </span>
                </label>
              </li>
            ))}
          </ul>
        </aside>

        <div className="space-y-4 lg:col-span-2">
          <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
            <label className="mb-1 block text-xs text-slate-500">Target</label>
            <input
              type="text"
              value={state.targetRaw}
              onChange={(e) => patch({ targetRaw: e.target.value })}
              placeholder={DEFAULT_GUIDED_TARGET}
              className="w-full rounded-lg border border-slate-700 bg-slate-950/50 px-4 py-2.5 text-sm focus:border-cyan-500/50 focus:outline-none"
            />
            {normalizedTarget && (
              <p className="mt-1 font-mono text-[11px] text-cyan-500/80">
                Normalized: {normalizedTarget}
              </p>
            )}
          </section>

          {priorArtifact.trim() && priorStep && (
            <section className="rounded-xl border border-dashed border-cyan-800/40 bg-cyan-950/10 p-4">
              <p className="mb-2 flex items-center gap-2 text-xs text-cyan-400">
                <Link2 className="h-3.5 w-3.5" />
                Chained from phase {priorStep}: {priorLabel}
              </p>
              <pre className="max-h-28 overflow-auto whitespace-pre-wrap text-[11px] text-slate-400">
                {priorArtifact.trim()}
              </pre>
            </section>
          )}

          {state.currentStep === 1 && (
            <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-6">
              <h2 className="text-base font-semibold">Identify the target</h2>
              <p className="mt-1 text-xs text-slate-500">
                Example: {DEFAULT_GUIDED_TARGET} — external web asset (ROE required).
              </p>
              <label className="mt-4 flex items-start gap-3 rounded-lg border border-slate-700/80 bg-slate-950/30 p-3">
                <input
                  type="checkbox"
                  checked={state.webAssetConfirmed}
                  onChange={(e) => patch({ webAssetConfirmed: e.target.checked })}
                  className="mt-1 h-4 w-4"
                />
                <span className="text-sm text-slate-300">
                  Asset type: external web application (HTTPS storefront / APIs)
                </span>
              </label>
              <label className="mt-3 flex items-start gap-3 rounded-lg border border-amber-500/20 bg-amber-950/20 p-3">
                <input
                  type="checkbox"
                  checked={state.roeAcknowledged}
                  onChange={(e) => patch({ roeAcknowledged: e.target.checked })}
                  className="mt-1 h-4 w-4"
                />
                <span className="text-sm text-amber-100/90">
                  I have written authorization and will stay within rules of engagement.
                </span>
              </label>
              <textarea
                value={state.identifyNotes}
                onChange={(e) => patch({ identifyNotes: e.target.value })}
                rows={5}
                placeholder={`Objective: web pentest — ${normalizedTarget || DEFAULT_GUIDED_TARGET}\nIn-scope: HTTPS, cart, auth, APIs\nOut-of-scope: DoS, social engineering`}
                className="mt-4 w-full rounded-lg border border-slate-700 bg-slate-950/50 px-4 py-2.5 text-sm focus:border-cyan-500/50 focus:outline-none"
              />
            </section>
          )}

          {state.currentStep === 2 && (
            <>
              <div className="rounded-lg border border-amber-500/30 bg-amber-950/20 p-4 text-sm text-amber-100/90">
                <p className="flex items-center gap-2 font-medium text-amber-300">
                  <AlertTriangle className="h-4 w-4" />
                  Cloudflare / CDN likely
                </p>
                <p className="mt-1 text-xs text-amber-200/80">
                  Prioritize HTTP(S) on 80 and 443 — avoid noisy full-port scans unless ROE allows.
                </p>
              </div>
              <StepTextPanel
                title="Reconnaissance"
                hint="Nmap (-sV -p 80,443), DNS, tech fingerprint."
                value={state.reconNotes}
                onChange={(v) => patch({ reconNotes: v })}
                rows={10}
                extra={
                  <div className="flex flex-wrap gap-2">
                    <Button
                      type="button"
                      onClick={runPassiveScan}
                      disabled={scanLoading || !normalizedTarget}
                      className="h-8 bg-slate-800 text-xs"
                    >
                      {scanLoading ? "Starting…" : "Analyzer scan (80/443)"}
                    </Button>
                    <Link href="/scanner" className="inline-flex h-8 items-center rounded-lg border border-slate-600 px-3 text-xs text-slate-300 hover:bg-slate-800">
                      Scanner
                    </Link>
                  </div>
                }
              />
            </>
          )}

          {state.currentStep === 3 && (
            <>
              <div className="flex flex-wrap gap-2">
                <Link href="/integration-hub" className="inline-flex h-8 items-center rounded-lg border border-slate-600 px-3 text-xs text-slate-300 hover:bg-slate-800">
                  Integration Hub
                </Link>
              </div>
              <StepTextPanel
                title="Vulnerability scanning"
                hint="Nessus / Nikto — paste summaries and CVEs to verify."
                value={state.vulnScanNotes}
                onChange={(v) => patch({ vulnScanNotes: v })}
                rows={10}
              />
            </>
          )}

          {state.currentStep === 4 && (
            <>
              <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h2 className="text-sm font-semibold">OpSec assess (web)</h2>
                    <p className="text-xs text-slate-500">POST /opsec/assess — SQLi, XSS, CSRF context</p>
                  </div>
                  <Button onClick={runOpsecAssess} disabled={assessLoading || !canRunAssess} className="h-9 bg-cyan-600 text-white">
                    {assessLoading ? "Assessing…" : "Run OpSec assess"}
                  </Button>
                </div>
                {!canRunAssess && (
                  <p className="mt-2 text-xs text-amber-400">Complete phase 1 and add recon or web notes.</p>
                )}
                {state.engagementId && (
                  <p className="mt-2 font-mono text-xs text-cyan-400">
                    Engagement: {state.engagementId}
                    {state.assessRiskScore != null && ` · Risk ${state.assessRiskScore}/100`}
                  </p>
                )}
              </section>
              {state.chains.length > 0 && (
                <ul className="space-y-2 rounded-xl border border-slate-800 bg-slate-900/60 p-4">
                  {state.chains.map((c) => (
                    <li key={c.index} className="flex items-center justify-between rounded-lg border border-slate-800 px-3 py-2">
                      <div>
                        <p className="text-sm">{c.title}</p>
                        <p className="text-[11px] text-slate-500">{c.stepCount} steps · {Math.round(c.confidence * 100)}%</p>
                      </div>
                      <button type="button" onClick={() => toggleChainRejected(c.index)} className="text-xs text-red-400">
                        {c.rejected ? "Restore" : "Reject"}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              <StepTextPanel
                title="Web application testing"
                hint="Burp/ZAP — SQLi, XSS, CSRF on cart, auth, APIs."
                value={state.webAppNotes}
                onChange={(v) => patch({ webAppNotes: v })}
                rows={8}
              />
            </>
          )}

          {state.currentStep === 5 && (
            <>
              <section className="rounded-xl border border-cyan-500/20 bg-cyan-950/20 p-4">
                <h2 className="text-sm font-medium">Exploitation</h2>
                <p className="mt-1 text-xs text-slate-400">Metasploit or Attack Dashboard execute-chain.</p>
                {state.engagementId ? (
                  <Button
                    onClick={() => router.push(`/operations?engagement=${state.engagementId}`)}
                    className="mt-3 h-8 bg-gradient-to-r from-cyan-600 to-blue-600 text-xs text-white"
                  >
                    <ExternalLink className="mr-1 h-3 w-3" />
                    Attack Dashboard
                  </Button>
                ) : (
                  <p className="mt-2 text-xs text-amber-400">Run OpSec assess on phase 4 first.</p>
                )}
              </section>
              <StepTextPanel
                title="Exploitation evidence"
                value={state.exploitationNotes}
                onChange={(v) => patch({ exploitationNotes: v })}
                hint="Module, chain, payload, result."
                rows={8}
              />
            </>
          )}

          {state.currentStep === 6 && (
            <section className="rounded-xl border border-slate-700/80 bg-slate-900/40 p-6 opacity-90">
              <h2 className="text-base font-semibold text-slate-400">Privilege escalation</h2>
              <p className="mt-2 text-sm text-slate-500">
                Disabled for external web-only against {normalizedTarget || DEFAULT_GUIDED_TARGET}. No internal foothold — priv esc is out of scope.
              </p>
              <label className="mt-4 flex items-start gap-3 rounded-lg border border-slate-700 p-3">
                <input
                  type="checkbox"
                  checked={state.privEscSkipped}
                  onChange={(e) => {
                    patch({ privEscSkipped: e.target.checked });
                    if (e.target.checked) {
                      setState((prev) => ({
                        ...prev,
                        substeps: {
                          ...prev.substeps,
                          6: prev.substeps[6].map((s) => ({ ...s, done: true })),
                        },
                      }));
                    }
                  }}
                  className="mt-1 h-4 w-4"
                />
                <span className="text-sm text-slate-400">Confirm priv esc N/A — skip phase</span>
              </label>
            </section>
          )}

          {state.currentStep === 7 && (
            <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-6">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={state.postExploitEnabled}
                  onChange={(e) => patch({ postExploitEnabled: e.target.checked })}
                  className="h-4 w-4"
                />
                Foothold obtained — enable post-exploitation
              </label>
              {!state.postExploitEnabled ? (
                <p className="mt-3 text-xs text-slate-500">Default out of scope unless you have shell/access.</p>
              ) : (
                <textarea
                  value={state.postExploitNotes}
                  onChange={(e) => patch({ postExploitNotes: e.target.value })}
                  rows={8}
                  className="mt-4 w-full rounded-lg border border-slate-700 bg-slate-950/50 px-4 py-2.5 text-sm focus:outline-none"
                />
              )}
            </section>
          )}

          {state.currentStep === 8 && (
            <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-6">
              <div className="mb-4 flex flex-wrap justify-between gap-3">
                <h2 className="text-base font-semibold">Covering tracks</h2>
                <div className="flex gap-2">
                  <Button onClick={() => patch({ coveringTracksNotes: buildSynthesisReport(state) })} className="h-8 bg-slate-800 text-xs">
                    Generate report
                  </Button>
                </div>
              </div>
              <textarea
                value={state.coveringTracksNotes}
                onChange={(e) => patch({ coveringTracksNotes: e.target.value })}
                rows={14}
                className="w-full rounded-lg border border-slate-700 bg-slate-950/50 px-4 py-2.5 font-mono text-xs focus:outline-none"
              />
            </section>
          )}

          <section className="rounded-xl border border-dashed border-slate-700 bg-slate-950/30 p-4">
            <div className="flex flex-wrap justify-between gap-2">
              <p className="text-xs text-slate-500">AI prompt (chained)</p>
              <div className="flex gap-2">
                <Button type="button" onClick={copyPrompt} className="h-7 bg-slate-800 px-3 text-[11px]">
                  <Copy className="mr-1 h-3 w-3" />
                  {copyHint || "Copy"}
                </Button>
                <Link
                  href={aiChatUrl(buildAiPromptForStep(state.currentStep, state), state.engagementId)}
                  className="inline-flex h-7 items-center rounded-lg border border-cyan-800/50 px-3 text-[11px] text-cyan-400"
                >
                  AI Chat
                </Link>
              </div>
            </div>
            <pre className="mt-2 max-h-32 overflow-auto whitespace-pre-wrap text-[10px] text-slate-500">
              {buildAiPromptForStep(state.currentStep, state)}
            </pre>
          </section>

          <div className="flex justify-between pt-2">
            <Button
              disabled={state.currentStep <= 1}
              onClick={() => goStep(Math.max(1, state.currentStep - 1) as GuidedStepNum)}
              className="h-9 border border-slate-700 bg-slate-900"
            >
              <ChevronLeft className="mr-1 h-4 w-4" />
              Back
            </Button>
            <Button type="button" onClick={resetWizard} variant="ghost" className="h-9 text-slate-500">
              <RotateCcw className="mr-1 h-4 w-4" />
              Reset
            </Button>
            <Button
              disabled={
                state.currentStep >= MAX_STEP ||
                (state.currentStep === 1 && !canLeaveStep1) ||
                (state.currentStep === 6 && !state.privEscSkipped)
              }
              onClick={() => goStep(Math.min(MAX_STEP, state.currentStep + 1) as GuidedStepNum)}
              className="h-9 bg-cyan-600 text-white"
            >
              Next
              <ChevronRight className="ml-1 h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function StepTextPanel({
  title,
  hint,
  value,
  onChange,
  rows,
  extra,
}: {
  title: string;
  hint: string;
  value: string;
  onChange: (v: string) => void;
  rows: number;
  extra?: ReactNode;
}) {
  return (
    <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-6">
      <h2 className="text-base font-semibold">{title}</h2>
      <p className="mt-1 text-xs text-slate-500">{hint}</p>
      {extra && <div className="mt-3">{extra}</div>}
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={rows}
        className="mt-4 w-full rounded-lg border border-slate-700 bg-slate-950/50 px-4 py-2.5 text-sm focus:outline-none"
      />
    </section>
  );
}
