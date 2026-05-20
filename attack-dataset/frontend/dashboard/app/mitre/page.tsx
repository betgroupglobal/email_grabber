"use client";

import { useState } from "react";
import { Shield, Brain, Target, Zap, ChevronRight, AlertTriangle, CheckCircle, XCircle } from "lucide-react";
import { analyzeMitreTechniques, suggestMitreTechniques, type MitreTechnique, type MitreChain } from "@/lib/api";

type Tab = "analyze" | "suggest";

export default function MitrePage() {
  const [activeTab, setActiveTab] = useState<Tab>("analyze");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Analyze state
  const [attackDesc, setAttackDesc] = useState("");
  const [targetType, setTargetType] = useState("");
  const [servicesInput, setServicesInput] = useState("");
  const [contextInput, setContextInput] = useState("");
  const [analyzeResult, setAnalyzeResult] = useState<{ techniques: MitreTechnique[]; chains: MitreChain[]; summary: string } | null>(null);

  // Suggest state
  const [suggestTarget, setSuggestTarget] = useState("");
  const [suggestOS, setSuggestOS] = useState("");
  const [suggestServices, setSuggestServices] = useState("");
  const [suggestAggression, setSuggestAggression] = useState(5);
  const [suggestResult, setSuggestResult] = useState<any>(null);

  async function handleAnalyze() {
    if (!attackDesc.trim()) return;
    setLoading(true);
    setError(null);
    setAnalyzeResult(null);
    try {
      const result = await analyzeMitreTechniques({
        attack_description: attackDesc,
        target_type: targetType || undefined,
        services: servicesInput ? servicesInput.split(",").map(s => s.trim()).filter(Boolean) : undefined,
        context: contextInput || undefined,
      });
      setAnalyzeResult(result);
    } catch (err: any) {
      setError(err.message || "Analysis failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleSuggest() {
    if (!suggestTarget.trim()) return;
    setLoading(true);
    setError(null);
    setSuggestResult(null);
    try {
      const result = await suggestMitreTechniques({
        target: suggestTarget,
        os: suggestOS || undefined,
        services: suggestServices ? suggestServices.split(",").map(s => s.trim()).filter(Boolean) : undefined,
        aggression_level: suggestAggression,
      });
      setSuggestResult(result);
    } catch (err: any) {
      setError(err.message || "Suggestion failed");
    } finally {
      setLoading(false);
    }
  }

  function getConfidenceColor(c: number) {
    if (c >= 0.8) return "text-emerald-400";
    if (c >= 0.5) return "text-amber-400";
    return "text-red-400";
  }

  function getConfidenceBg(c: number) {
    if (c >= 0.8) return "bg-emerald-500/10";
    if (c >= 0.5) return "bg-amber-500/10";
    return "bg-red-500/10";
  }

  return (
    <div className="min-h-screen bg-[#080c14] text-slate-200">
      {/* Header */}
      <div className="sticky top-0 z-40 border-b border-slate-800/60 bg-[#080c14]/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-purple-500/10">
              <Shield className="h-5 w-5 text-purple-400" />
            </div>
            <div>
              <h1 className="text-base font-semibold text-white">MITRE ATT&CK AI</h1>
              <p className="text-xs text-slate-500">AI-powered technique mapping and analysis</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex h-8 items-center gap-1.5 rounded-full bg-purple-500/10 px-3 text-xs text-purple-400">
              <Brain className="h-3.5 w-3.5" />
              <span>AI Powered</span>
            </div>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-7xl px-6 py-8">
        {/* Tabs */}
        <div className="mb-8 flex gap-1 rounded-lg border border-slate-800 bg-slate-950/50 p-1">
          <button
            onClick={() => setActiveTab("analyze")}
            className={`flex flex-1 items-center justify-center gap-2 rounded-md px-4 py-2.5 text-sm font-medium transition-all ${
              activeTab === "analyze"
                ? "bg-slate-800 text-white shadow-sm"
                : "text-slate-500 hover:text-slate-300"
            }`}
          >
            <Zap className="h-4 w-4" />
            Analyze Attack
          </button>
          <button
            onClick={() => setActiveTab("suggest")}
            className={`flex flex-1 items-center justify-center gap-2 rounded-md px-4 py-2.5 text-sm font-medium transition-all ${
              activeTab === "suggest"
                ? "bg-slate-800 text-white shadow-sm"
                : "text-slate-500 hover:text-slate-300"
            }`}
          >
            <Target className="h-4 w-4" />
            Suggest for Target
          </button>
        </div>

        {error && (
          <div className="mb-6 flex items-center gap-2 rounded-lg border border-red-500/20 bg-red-500/5 px-4 py-3 text-sm text-red-400">
            <AlertTriangle className="h-4 w-4" />
            {error}
          </div>
        )}

        {/* Analyze Panel */}
        {activeTab === "analyze" && (
          <div className="space-y-6">
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-sm">
              <h2 className="mb-4 text-base font-semibold text-white">Describe the Attack Scenario</h2>
              <div className="space-y-4">
                <div>
                  <label className="mb-1.5 block text-xs text-slate-500">Attack Description</label>
                  <textarea
                    value={attackDesc}
                    onChange={(e) => setAttackDesc(e.target.value)}
                    placeholder="e.g. An attacker gains initial access via a phishing email, then moves laterally through the network using stolen credentials, escalating privileges to domain admin..."
                    className="min-h-[100px] w-full rounded-lg border border-slate-700 bg-slate-950/50 px-4 py-3 text-sm text-white placeholder:text-slate-600 focus:border-purple-500/50 focus:outline-none focus:ring-1 focus:ring-purple-500/20"
                  />
                </div>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                  <div>
                    <label className="mb-1.5 block text-xs text-slate-500">Target Type</label>
                    <input
                      value={targetType}
                      onChange={(e) => setTargetType(e.target.value)}
                      placeholder="e.g. Windows Domain"
                      className="w-full rounded-lg border border-slate-700 bg-slate-950/50 px-4 py-2.5 text-sm text-white placeholder:text-slate-600 focus:border-purple-500/50 focus:outline-none focus:ring-1 focus:ring-purple-500/20"
                    />
                  </div>
                  <div>
                    <label className="mb-1.5 block text-xs text-slate-500">Services (comma separated)</label>
                    <input
                      value={servicesInput}
                      onChange={(e) => setServicesInput(e.target.value)}
                      placeholder="e.g. HTTP, SSH, RDP"
                      className="w-full rounded-lg border border-slate-700 bg-slate-950/50 px-4 py-2.5 text-sm text-white placeholder:text-slate-600 focus:border-purple-500/50 focus:outline-none focus:ring-1 focus:ring-purple-500/20"
                    />
                  </div>
                  <div>
                    <label className="mb-1.5 block text-xs text-slate-500">Additional Context</label>
                    <input
                      value={contextInput}
                      onChange={(e) => setContextInput(e.target.value)}
                      placeholder="e.g. Insider threat scenario"
                      className="w-full rounded-lg border border-slate-700 bg-slate-950/50 px-4 py-2.5 text-sm text-white placeholder:text-slate-600 focus:border-purple-500/50 focus:outline-none focus:ring-1 focus:ring-purple-500/20"
                    />
                  </div>
                </div>
                <button
                  onClick={handleAnalyze}
                  disabled={loading || !attackDesc.trim()}
                  className="flex h-9 items-center gap-2 rounded-lg bg-purple-600 px-5 text-sm font-medium text-white transition-all hover:bg-purple-500 disabled:opacity-50"
                >
                  {loading ? (
                    <div className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                  ) : (
                    <Brain className="h-4 w-4" />
                  )}
                  {loading ? "Analyzing..." : "Analyze with AI"}
                </button>
              </div>
            </div>

            {/* Results */}
            {analyzeResult && (
              <div className="space-y-6">
                {/* Summary */}
                {analyzeResult.summary && (
                  <div className="rounded-xl border border-purple-500/10 bg-purple-950/20 p-5">
                    <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-purple-400">
                      <Brain className="h-4 w-4" />
                      AI Summary
                    </h3>
                    <p className="text-sm leading-relaxed text-slate-300">{analyzeResult.summary}</p>
                  </div>
                )}

                {/* Techniques */}
                {analyzeResult.techniques.length > 0 && (
                  <div>
                    <h3 className="mb-4 text-base font-semibold text-white">
                      Mapped Techniques ({analyzeResult.techniques.length})
                    </h3>
                    <div className="grid gap-3">
                      {analyzeResult.techniques.map((tech, i) => (
                        <div
                          key={i}
                          className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm transition-all hover:border-slate-700"
                        >
                          <div className="mb-3 flex items-start justify-between gap-3">
                            <div className="flex items-center gap-3">
                              <span className="rounded-lg bg-purple-500/10 px-2.5 py-1 text-xs font-bold text-purple-400">
                                {tech.technique_id}
                              </span>
                              <div>
                                <h4 className="text-sm font-medium text-white">{tech.name}</h4>
                                <p className="text-xs text-slate-500">{tech.tactic}</p>
                              </div>
                            </div>
                            <div className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${getConfidenceBg(tech.confidence)} ${getConfidenceColor(tech.confidence)}`}>
                              {tech.confidence >= 0.8 ? <CheckCircle className="h-3 w-3" /> : tech.confidence >= 0.5 ? <AlertTriangle className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
                              {Math.round(tech.confidence * 100)}% confidence
                            </div>
                          </div>
                          <p className="mb-3 text-sm text-slate-400">{tech.rationale}</p>
                          <div className="flex flex-wrap gap-2">
                            {tech.subtechniques.map((st, j) => (
                              <span key={j} className="rounded bg-slate-800 px-2 py-0.5 text-[11px] text-slate-400">
                                {st}
                              </span>
                            ))}
                          </div>
                          {tech.detection_methods.length > 0 && (
                            <div className="mt-3 border-t border-slate-800 pt-3">
                              <p className="mb-1 text-[11px] uppercase tracking-wide text-slate-500">Detection</p>
                              <div className="flex flex-wrap gap-1.5">
                                {tech.detection_methods.map((dm, j) => (
                                  <span key={j} className="rounded bg-cyan-500/5 px-2 py-0.5 text-[11px] text-cyan-400">
                                    {dm}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}
                          {tech.mitigations.length > 0 && (
                            <div className="mt-3 border-t border-slate-800 pt-3">
                              <p className="mb-1 text-[11px] uppercase tracking-wide text-slate-500">Mitigations</p>
                              <div className="flex flex-wrap gap-1.5">
                                {tech.mitigations.map((m, j) => (
                                  <span key={j} className="rounded bg-emerald-500/5 px-2 py-0.5 text-[11px] text-emerald-400">
                                    {m}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Chains */}
                {analyzeResult.chains.length > 0 && (
                  <div>
                    <h3 className="mb-4 text-base font-semibold text-white">AI-Suggested Attack Chains</h3>
                    <div className="space-y-4">
                      {analyzeResult.chains.map((chain, i) => (
                        <div key={i} className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
                          <div className="mb-3 flex items-center justify-between">
                            <h4 className="text-sm font-medium text-white">{chain.name}</h4>
                            <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${getConfidenceBg(chain.confidence)} ${getConfidenceColor(chain.confidence)}`}>
                              {Math.round(chain.confidence * 100)}% confidence
                            </span>
                          </div>
                          <div className="space-y-2">
                            {chain.steps.map((step, j) => (
                              <div key={j} className="flex items-center gap-3 rounded-lg bg-slate-950/30 p-3">
                                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-800 text-[10px] font-bold text-slate-400">
                                  {j + 1}
                                </span>
                                <div className="flex-1">
                                  <p className="text-sm text-slate-200">{step.description}</p>
                                  <div className="mt-1 flex items-center gap-2">
                                    <span className="text-[10px] text-slate-500">{step.phase}</span>
                                    <span className="rounded bg-purple-500/10 px-1.5 py-0.5 text-[10px] text-purple-400">
                                      {step.technique_id}
                                    </span>
                                  </div>
                                </div>
                                <ChevronRight className="h-4 w-4 text-slate-600" />
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Suggest Panel */}
        {activeTab === "suggest" && (
          <div className="space-y-6">
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-sm">
              <h2 className="mb-4 text-base font-semibold text-white">Target Profile</h2>
              <div className="space-y-4">
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div>
                    <label className="mb-1.5 block text-xs text-slate-500">Target</label>
                    <input
                      value={suggestTarget}
                      onChange={(e) => setSuggestTarget(e.target.value)}
                      placeholder="e.g. 192.168.1.10 or corp.internal"
                      className="w-full rounded-lg border border-slate-700 bg-slate-950/50 px-4 py-2.5 text-sm text-white placeholder:text-slate-600 focus:border-purple-500/50 focus:outline-none focus:ring-1 focus:ring-purple-500/20"
                    />
                  </div>
                  <div>
                    <label className="mb-1.5 block text-xs text-slate-500">Operating System</label>
                    <input
                      value={suggestOS}
                      onChange={(e) => setSuggestOS(e.target.value)}
                      placeholder="e.g. Windows Server 2019"
                      className="w-full rounded-lg border border-slate-700 bg-slate-950/50 px-4 py-2.5 text-sm text-white placeholder:text-slate-600 focus:border-purple-500/50 focus:outline-none focus:ring-1 focus:ring-purple-500/20"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div>
                    <label className="mb-1.5 block text-xs text-slate-500">Services (comma separated)</label>
                    <input
                      value={suggestServices}
                      onChange={(e) => setSuggestServices(e.target.value)}
                      placeholder="e.g. HTTP, SSH, RDP, SMB"
                      className="w-full rounded-lg border border-slate-700 bg-slate-950/50 px-4 py-2.5 text-sm text-white placeholder:text-slate-600 focus:border-purple-500/50 focus:outline-none focus:ring-1 focus:ring-purple-500/20"
                    />
                  </div>
                  <div>
                    <label className="mb-1.5 block text-xs text-slate-500">Aggression Level: {suggestAggression}</label>
                    <input
                      type="range"
                      min={1}
                      max={10}
                      value={suggestAggression}
                      onChange={(e) => setSuggestAggression(Number(e.target.value))}
                      className="w-full accent-purple-500"
                    />
                    <div className="mt-1 flex justify-between text-[11px] text-slate-600">
                      <span>Conservative</span>
                      <span>Aggressive</span>
                    </div>
                  </div>
                </div>
                <button
                  onClick={handleSuggest}
                  disabled={loading || !suggestTarget.trim()}
                  className="flex h-9 items-center gap-2 rounded-lg bg-purple-600 px-5 text-sm font-medium text-white transition-all hover:bg-purple-500 disabled:opacity-50"
                >
                  {loading ? (
                    <div className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                  ) : (
                    <Target className="h-4 w-4" />
                  )}
                  {loading ? "Analyzing..." : "Suggest Techniques"}
                </button>
              </div>
            </div>

            {/* Suggest Results */}
            {suggestResult && (
              <div className="space-y-6">
                {/* Analysis */}
                {suggestResult.analysis && (
                  <div className="rounded-xl border border-purple-500/10 bg-purple-950/20 p-5">
                    <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-purple-400">
                      <Brain className="h-4 w-4" />
                      Strategic Analysis
                    </h3>
                    <p className="text-sm leading-relaxed text-slate-300">{suggestResult.analysis}</p>
                  </div>
                )}

                {/* Primary Techniques */}
                {suggestResult.primary_techniques?.length > 0 && (
                  <div>
                    <h3 className="mb-4 text-base font-semibold text-white">
                      Recommended Techniques ({suggestResult.primary_techniques.length})
                    </h3>
                    <div className="grid gap-3">
                      {suggestResult.primary_techniques.map((tech: any, i: number) => (
                        <div
                          key={i}
                          className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm transition-all hover:border-slate-700"
                        >
                          <div className="mb-3 flex items-start justify-between gap-3">
                            <div className="flex items-center gap-3">
                              <span className="rounded-lg bg-purple-500/10 px-2.5 py-1 text-xs font-bold text-purple-400">
                                {tech.technique_id}
                              </span>
                              <div>
                                <h4 className="text-sm font-medium text-white">{tech.name}</h4>
                                <p className="text-xs text-slate-500">{tech.tactic}</p>
                              </div>
                            </div>
                            <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                              tech.priority >= 8 ? "bg-red-500/10 text-red-400" :
                              tech.priority >= 5 ? "bg-amber-500/10 text-amber-400" :
                              "bg-emerald-500/10 text-emerald-400"
                            }`}>
                              Priority {tech.priority}/10
                            </span>
                          </div>
                          <p className="mb-2 text-sm text-slate-400">{tech.applicability}</p>
                          <p className="text-xs text-slate-500">
                            <span className="text-slate-600">Outcome:</span> {tech.expected_outcome}
                          </p>
                          {tech.prerequisites?.length > 0 && (
                            <div className="mt-3 flex flex-wrap gap-1.5">
                              {tech.prerequisites.map((p: string, j: number) => (
                                <span key={j} className="rounded bg-slate-800 px-2 py-0.5 text-[11px] text-slate-400">
                                  {p}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Recommended Chain */}
                {suggestResult.recommended_chain && (
                  <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
                    <div className="mb-4 flex items-center justify-between">
                      <h3 className="text-base font-semibold text-white">Recommended Attack Chain</h3>
                      <span className="rounded-full bg-purple-500/10 px-2.5 py-0.5 text-xs font-medium text-purple-400">
                        {Math.round(suggestResult.recommended_chain.estimated_success * 100)}% estimated success
                      </span>
                    </div>
                    <div className="space-y-2">
                      {suggestResult.recommended_chain.steps.map((step: any, j: number) => (
                        <div key={j} className="flex items-center gap-3 rounded-lg bg-slate-950/30 p-3">
                          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-800 text-[10px] font-bold text-slate-400">
                            {step.order}
                          </span>
                          <div className="flex-1">
                            <p className="text-sm text-slate-200">{step.description}</p>
                            <div className="mt-1 flex items-center gap-2">
                              <span className="text-[10px] text-slate-500">{step.phase}</span>
                              <span className="rounded bg-purple-500/10 px-1.5 py-0.5 text-[10px] text-purple-400">
                                {step.technique_id}
                              </span>
                            </div>
                          </div>
                          <ChevronRight className="h-4 w-4 text-slate-600" />
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Defensive Recommendations */}
                {suggestResult.defensive_recommendations?.length > 0 && (
                  <div className="rounded-xl border border-emerald-500/10 bg-emerald-950/10 p-5">
                    <h3 className="mb-3 text-sm font-semibold text-emerald-400">Defensive Recommendations</h3>
                    <ul className="space-y-2">
                      {suggestResult.defensive_recommendations.map((rec: string, i: number) => (
                        <li key={i} className="flex items-start gap-2 text-sm text-slate-300">
                          <CheckCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-400" />
                          {rec}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
