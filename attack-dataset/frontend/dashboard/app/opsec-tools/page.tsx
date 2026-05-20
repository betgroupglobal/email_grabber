"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { orchestratorFetchInit, orchestratorHttp } from "@/lib/config";
import { normalizeTargetInput } from "@/lib/targetUtils";
import { startFullEngagementFromOpsec } from "@/lib/orchestratorClient";

interface OpSecAssessment {
  engagement_id?: string;
  target?: string;
  overall_score: number;
  risk_score?: number;
  attack_chains?: {
    chains: Array<{
      chain_id?: string;
      confidence: number;
      estimated_impact?: string;
      opsec_notes?: string;
      steps: Array<{
        phase: string;
        attack: {
          title?: string;
          mitre_technique?: string;
          description?: string;
        } | string;
        rationale?: string;
        mitre_technique?: string;
      }>;
    }>;
  };
  risk_factors: Array<{
    category: string;
    severity: "low" | "medium" | "high" | "critical";
    description: string;
    recommendation: string;
  }>;
  recommendations: string[];
}

interface OpSecAudit {
  audit_id: string;
  timestamp: string;
  chain_summary: string;
  findings: Array<{
    type: string;
    severity: string;
    description: string;
    mitigation: string;
  }>;
  overall_risk: "low" | "medium" | "high" | "critical";
}

interface ToolRecommendation {
  tool_name: string;
  risk_level: "low" | "medium" | "high" | "critical";
  detection_risk: number;
  recommendations: string[];
  alternatives: string[];
  configuration_tips: string[];
}

export default function OpSecTools() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<"assess" | "audit" | "tools">("assess");
  const [targetInput, setTargetInput] = useState("");
  const [chainInput, setChainInput] = useState("");
  const [toolInput, setToolInput] = useState("");
  const [assessment, setAssessment] = useState<OpSecAssessment | null>(null);
  const [audit, setAudit] = useState<OpSecAudit | null>(null);
  const [toolRec, setToolRec] = useState<ToolRecommendation | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [launchingFull, setLaunchingFull] = useState(false);

  const launchFullEngagement = async () => {
    if (!assessment?.engagement_id) return;
    setLaunchingFull(true);
    try {
      const result = await startFullEngagementFromOpsec(assessment.engagement_id);
      if (result.ok) {
        router.push(`/engagement/${result.data.engagement_id}`);
      }
    } catch (error) {
      console.error("Failed to start full engagement:", error);
    } finally {
      setLaunchingFull(false);
    }
  };

  const runAssessment = async () => {
    if (!targetInput.trim()) return;

    setIsLoading(true);
    try {
      const response = await fetch(orchestratorHttp("/opsec/assess"), orchestratorFetchInit({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          target: normalizeTargetInput(targetInput),
          operation_type: "reconnaissance"
        })
      }));

      if (response.ok) {
        const data = await response.json();
        const normalized = {
          overall_score: data.overall_score ?? data.risk_score ?? 0,
          risk_factors: data.risk_factors ?? [],
          recommendations: data.recommendations ?? [],
          ...data,
        };
        setAssessment(normalized);
        // Chains persisted server-side; engagement_id returned from orchestrator
      }
    } catch (error) {
      console.error("Assessment failed:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const runAudit = async () => {
    if (!chainInput.trim()) return;

    setIsLoading(true);
    try {
      const response = await fetch(orchestratorHttp("/opsec/audit"), orchestratorFetchInit({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          attack_chain: JSON.parse(chainInput),
          context: {
            target_type: "internal",
            environment: "production"
          }
        })
      }));

      if (response.ok) {
        const data = await response.json();
        setAudit(data);
      }
    } catch (error) {
      console.error("Audit failed:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const getToolRecommendations = async () => {
    if (!toolInput.trim()) return;

    setIsLoading(true);
    try {
      const response = await fetch(orchestratorHttp(`/opsec/tool/${encodeURIComponent(toolInput.trim())}`), orchestratorFetchInit({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          context: {
            operation_type: "reconnaissance",
            target_environment: "unknown"
          }
        })
      }));

      if (response.ok) {
        const data = await response.json();
        setToolRec(data);
      }
    } catch (error) {
      console.error("Failed to get tool recommendations:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case "critical": return "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium bg-red-500/10 text-red-400";
      case "high": return "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium bg-red-500/10 text-red-400";
      case "medium": return "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium bg-amber-500/10 text-amber-400";
      case "low": return "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium bg-emerald-500/10 text-emerald-400";
      default: return "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium bg-slate-500/10 text-slate-400";
    }
  };

  const getRiskColor = (risk: number) => {
    if (risk >= 80) return "text-red-400";
    if (risk >= 60) return "text-amber-400";
    if (risk >= 40) return "text-amber-400";
    return "text-emerald-400";
  };

  const commonTools = [
    "nmap", "sqlmap", "metasploit", "burpsuite", "nikto",
    "hydra", "john", "gobuster", "dirb", "enum4linux"
  ];

  return (
    <div className="min-h-screen bg-[#080c14] text-white">
      {/* Header */}
      <header className="sticky top-0 z-40 border-b border-slate-800/60 bg-[#080c14]/80 backdrop-blur-xl">
        <div className="mx-auto max-w-7xl px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-cyan-400">OpSec Tools</h1>
              <p className="text-sm text-slate-500">Operational Security Assessment & Auditing</p>
              <button
                type="button"
                onClick={() => router.push("/operations")}
                className="mt-2 text-xs text-cyan-500 hover:text-cyan-400 hover:underline"
              >
                Open 7-step guided assessment →
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-8">
        {/* Tab Navigation */}
        <div className="flex gap-2 mb-6">
          <Button
            onClick={() => setActiveTab("assess")}
            className={`h-8 px-4 py-2 rounded-lg text-sm ${
              activeTab === "assess"
                ? "bg-cyan-600 hover:bg-cyan-700"
                : "bg-slate-700 hover:bg-slate-600"
            }`}
          >
            Risk Assessment
          </Button>
          <Button
            onClick={() => setActiveTab("audit")}
            className={`h-8 px-4 py-2 rounded-lg text-sm ${
              activeTab === "audit"
                ? "bg-cyan-600 hover:bg-cyan-700"
                : "bg-slate-700 hover:bg-slate-600"
            }`}
          >
            Chain Audit
          </Button>
          <Button
            onClick={() => setActiveTab("tools")}
            className={`h-8 px-4 py-2 rounded-lg text-sm ${
              activeTab === "tools"
                ? "bg-cyan-600 hover:bg-cyan-700"
                : "bg-slate-700 hover:bg-slate-600"
            }`}
          >
            Tool Recommendations
          </Button>
        </div>

        {activeTab === "assess" && (
          <div className="space-y-6">
            {/* Target Input */}
            <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-sm">
              <h2 className="text-base font-semibold text-white mb-4">Target Risk Assessment</h2>
              <div className="flex gap-4">
                <input
                  type="text"
                  value={targetInput}
                  onChange={(e) => setTargetInput(e.target.value)}
                  placeholder="Enter target IP, hostname, or network range"
                  className="flex-1 rounded-lg border border-slate-700 bg-slate-950/50 px-4 py-2.5 text-sm text-white placeholder:text-slate-600 focus:border-cyan-500/50 focus:outline-none focus:ring-1 focus:ring-cyan-500/20"
                />
                <Button
                  onClick={runAssessment}
                  disabled={isLoading || !targetInput.trim()}
                  className="h-9 bg-cyan-600 hover:bg-cyan-700 text-white px-6 py-3 rounded-lg"
                >
                  {isLoading ? "Assessing..." : "Assess Risk"}
                </Button>
              </div>
            </section>

            {/* Assessment Results */}
            {assessment && (
              <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-sm">
                <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                  <h2 className="text-base font-semibold text-white">Assessment Results</h2>
                  {assessment.engagement_id && (
                    <Button
                      onClick={() => router.push(`/engagement/${assessment.engagement_id}`)}
                      className="h-8 bg-gradient-to-r from-cyan-600 to-blue-600 px-4 text-xs text-white hover:from-cyan-500 hover:to-blue-500"
                    >
                      View engagement {assessment.engagement_id}
                    </Button>
                  )}
                </div>

                {assessment.engagement_id && (
                  <p className="mb-4 text-xs text-slate-500">
                    Saved as engagement{" "}
                    <button
                      type="button"
                      onClick={() => router.push(`/engagement/${assessment.engagement_id}`)}
                      className="font-mono text-cyan-400 hover:underline"
                    >
                      {assessment.engagement_id}
                    </button>
                    {" "}— chains and OpSec scores are persisted on the server.
                  </p>
                )}

                {/* Overall Score */}
                <div className="mb-6 p-4 rounded-lg border border-slate-800 bg-slate-950/30">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-slate-500">Overall Risk Score</span>
                    <span className={`text-2xl font-bold ${getRiskColor(assessment.overall_score)}`}>
                      {assessment.overall_score}/100
                    </span>
                  </div>
                  <div className="w-full bg-slate-800 rounded-full h-3">
                    <div
                      className={`h-3 rounded-full transition-all ${
                        assessment.overall_score >= 80 ? "bg-red-500" :
                        assessment.overall_score >= 60 ? "bg-amber-500" :
                        assessment.overall_score >= 40 ? "bg-amber-500" :
                        "bg-emerald-500"
                      }`}
                      style={{ width: `${assessment.overall_score}%` }}
                    />
                  </div>
                </div>

                {/* Risk Factors */}
                <div className="space-y-3">
                  <h3 className="text-sm font-medium text-white">Risk Factors</h3>
                  {assessment.risk_factors.map((factor, idx) => (
                    <div
                      key={idx}
                      className="rounded-lg border border-slate-800 bg-slate-950/30 p-4"
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium text-white">{factor.category}</span>
                        <span className={getSeverityColor(factor.severity)}>{factor.severity}</span>
                      </div>
                      <p className="text-sm text-slate-400 mb-2">{factor.description}</p>
                      <p className="text-xs text-slate-500">
                        <strong>Recommendation:</strong> {factor.recommendation}
                      </p>
                    </div>
                  ))}
                </div>

                {/* General Recommendations */}
                {assessment.recommendations.length > 0 && (
                  <div className="mt-6">
                    <h3 className="text-sm font-medium text-white mb-3">General Recommendations</h3>
                    <ul className="space-y-2">
                      {assessment.recommendations.map((rec, idx) => (
                        <li key={idx} className="flex items-start gap-2 text-sm">
                          <span className="text-cyan-400">&bull;</span>
                          <span className="text-slate-400">{rec}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {assessment.attack_chains?.chains?.length ? (
                  <div className="mt-6 rounded-lg border border-cyan-500/20 bg-cyan-950/20 p-4">
                    <div className="flex items-center justify-between gap-4">
                      <div>
                        <h3 className="text-sm font-medium text-white">Structured Attack Chains Ready</h3>
                        <p className="mt-1 text-xs text-slate-400">
                          {assessment.attack_chains.chains.length} chain(s) saved for Attack Dashboard integration.
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Button
                          onClick={() =>
                            router.push(
                              `/operations?engagement=${assessment.engagement_id}`
                            )
                          }
                          className="h-8 bg-gradient-to-r from-cyan-600 to-blue-600 px-4 text-xs text-white hover:from-cyan-500 hover:to-blue-500"
                        >
                          Execute Chains
                        </Button>
                        <Button
                          onClick={launchFullEngagement}
                          disabled={launchingFull}
                          className="h-8 border border-slate-600 bg-slate-900/50 px-4 text-xs text-slate-200 hover:bg-slate-800"
                        >
                          {launchingFull ? "Starting..." : "Start Full Engagement"}
                        </Button>
                      </div>
                    </div>
                  </div>
                ) : null}
              </section>
            )}
          </div>
        )}

        {activeTab === "audit" && (
          <div className="space-y-6">
            {/* Chain Input */}
            <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-sm">
              <h2 className="text-base font-semibold text-white mb-4">Attack Chain Audit</h2>
              <p className="text-xs text-slate-500 mb-4">Paste your attack chain JSON for OpSec auditing</p>
              
              <textarea
                value={chainInput}
                onChange={(e) => setChainInput(e.target.value)}
                placeholder='{"steps": [{"phase": "reconnaissance", "technique": "nmap", ...}]}'
                className="w-full h-40 rounded-lg border border-slate-700 bg-slate-950/50 px-4 py-2.5 text-sm text-white placeholder:text-slate-600 font-mono focus:border-cyan-500/50 focus:outline-none focus:ring-1 focus:ring-cyan-500/20"
              />
              
              <div className="flex gap-2 mt-4">
                <Button
                  onClick={runAudit}
                  disabled={isLoading || !chainInput.trim()}
                  className="h-9 bg-cyan-600 hover:bg-cyan-700 text-white px-6 py-2 rounded-lg"
                >
                  {isLoading ? "Auditing..." : "Audit Chain"}
                </Button>
                <Button
                  onClick={() => setChainInput('')}
                  className="h-8 bg-slate-700 hover:bg-slate-600 text-white px-4 py-2 rounded-lg"
                >
                  Clear
                </Button>
              </div>
            </section>

            {/* Audit Results */}
            {audit && (
              <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-sm">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-base font-semibold text-white">Audit Results</h2>
                  <span className={getSeverityColor(audit.overall_risk)}>
                    {audit.overall_risk.toUpperCase()} RISK
                  </span>
                </div>

                <div className="mb-4 p-3 rounded-lg border border-slate-800 bg-slate-950/30">
                  <p className="text-xs text-slate-500">Summary</p>
                  <p className="text-sm text-slate-300">{audit.chain_summary}</p>
                </div>

                <div className="space-y-3">
                  <h3 className="text-sm font-medium text-white">Findings</h3>
                  {audit.findings.map((finding, idx) => (
                    <div
                      key={idx}
                      className="rounded-lg border border-slate-800 bg-slate-950/30 p-4"
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium text-white">{finding.type}</span>
                        <span className={getSeverityColor(finding.severity)}>{finding.severity}</span>
                      </div>
                      <p className="text-sm text-slate-400 mb-2">{finding.description}</p>
                      <p className="text-xs text-slate-500">
                        <strong>Mitigation:</strong> {finding.mitigation}
                      </p>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </div>
        )}

        {activeTab === "tools" && (
          <div className="space-y-6">
            {/* Tool Input */}
            <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-sm">
              <h2 className="text-base font-semibold text-white mb-4">Tool OpSec Recommendations</h2>
              <p className="text-xs text-slate-500 mb-4">Get OpSec guidance for specific security tools</p>
              
              <div className="flex gap-4 mb-4">
                <input
                  type="text"
                  value={toolInput}
                  onChange={(e) => setToolInput(e.target.value)}
                  placeholder="Enter tool name (e.g., nmap, sqlmap)"
                  className="flex-1 rounded-lg border border-slate-700 bg-slate-950/50 px-4 py-2.5 text-sm text-white placeholder:text-slate-600 focus:border-cyan-500/50 focus:outline-none focus:ring-1 focus:ring-cyan-500/20"
                />
                <Button
                  onClick={getToolRecommendations}
                  disabled={isLoading || !toolInput.trim()}
                  className="h-9 bg-cyan-600 hover:bg-cyan-700 text-white px-6 py-3 rounded-lg"
                >
                  {isLoading ? "Analyzing..." : "Get Recommendations"}
                </Button>
              </div>

              <div className="flex flex-wrap gap-2">
                <span className="text-xs text-slate-500">Common tools:</span>
                {commonTools.map((tool) => (
                  <button
                    key={tool}
                    onClick={() => setToolInput(tool)}
                    className="h-7 text-[11px] bg-slate-800 hover:bg-slate-700 px-2.5 rounded-md text-slate-400 border border-slate-800"
                  >
                    {tool}
                  </button>
                ))}
              </div>
            </section>

            {/* Tool Recommendations */}
            {toolRec && (
              <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-sm">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-base font-semibold text-white">{toolRec.tool_name}</h2>
                  <div className="flex items-center gap-2">
                    <span className={getSeverityColor(toolRec.risk_level)}>
                      {toolRec.risk_level.toUpperCase()} RISK
                    </span>
                    <span className="text-xs text-slate-500">
                      Detection Risk: {toolRec.detection_risk}%
                    </span>
                  </div>
                </div>

                {/* Detection Risk Bar */}
                <div className="mb-6 p-4 rounded-lg border border-slate-800 bg-slate-950/30">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-slate-500">Detection Risk</span>
                    <span className={`text-sm font-bold ${getRiskColor(toolRec.detection_risk)}`}>
                      {toolRec.detection_risk}%
                    </span>
                  </div>
                  <div className="w-full bg-slate-800 rounded-full h-3">
                    <div
                      className={`h-3 rounded-full transition-all ${
                        toolRec.detection_risk >= 80 ? "bg-red-500" :
                        toolRec.detection_risk >= 60 ? "bg-amber-500" :
                        toolRec.detection_risk >= 40 ? "bg-amber-500" :
                        "bg-emerald-500"
                      }`}
                      style={{ width: `${toolRec.detection_risk}%` }}
                    />
                  </div>
                </div>

                {/* Recommendations */}
                {toolRec.recommendations.length > 0 && (
                  <div className="mb-4">
                    <h3 className="text-sm font-medium text-white mb-3">OpSec Recommendations</h3>
                    <ul className="space-y-2">
                      {toolRec.recommendations.map((rec, idx) => (
                        <li key={idx} className="flex items-start gap-2 text-sm">
                          <span className="text-cyan-400">&bull;</span>
                          <span className="text-slate-400">{rec}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Configuration Tips */}
                {toolRec.configuration_tips.length > 0 && (
                  <div className="mb-4">
                    <h3 className="text-sm font-medium text-white mb-3">Configuration Tips</h3>
                    <ul className="space-y-2">
                      {toolRec.configuration_tips.map((tip, idx) => (
                        <li key={idx} className="flex items-start gap-2 text-sm">
                          <span className="text-emerald-400">&bull;</span>
                          <span className="text-slate-400">{tip}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Alternatives */}
                {toolRec.alternatives.length > 0 && (
                  <div>
                    <h3 className="text-sm font-medium text-white mb-3">Stealthier Alternatives</h3>
                    <div className="flex flex-wrap gap-2">
                      {toolRec.alternatives.map((alt, idx) => (
                        <span
                          key={idx}
                          className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium bg-purple-500/10 text-purple-400"
                        >
                          {alt}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </section>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
