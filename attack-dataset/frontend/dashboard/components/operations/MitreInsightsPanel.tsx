"use client";

import { useCallback, useEffect, useState } from "react";
import { Brain, ChevronRight, Loader2, RefreshCw, Shield } from "lucide-react";
import {
  analyzeMitreTechniques,
  suggestMitreTechniques,
  type MitreTechnique,
} from "@/lib/api";

interface MitreInsightsPanelProps {
  target: string;
  aggression: number;
  engagementId?: string | null;
  /** Optional attack narrative from guided phases */
  attackDescription?: string;
}

export function MitreInsightsPanel({
  target,
  aggression,
  engagementId,
  attackDescription,
}: MitreInsightsPanelProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [techniques, setTechniques] = useState<MitreTechnique[]>([]);
  const [summary, setSummary] = useState<string | null>(null);
  const [chainName, setChainName] = useState<string | null>(null);
  const [mode, setMode] = useState<"suggest" | "analyze">("suggest");

  const refresh = useCallback(async () => {
    if (mode === "suggest" && !target.trim()) return;
    if (mode === "analyze" && !attackDescription?.trim()) return;

    setLoading(true);
    setError(null);
    try {
      if (mode === "analyze" && attackDescription?.trim()) {
        const result = await analyzeMitreTechniques({
          attack_description: attackDescription,
          context: engagementId ? `Engagement ${engagementId}` : undefined,
        });
        setTechniques(result.techniques.slice(0, 8));
        setSummary(result.summary || null);
        setChainName(result.chains[0]?.name ?? null);
      } else {
        const result = await suggestMitreTechniques({
          target: target.trim(),
          aggression_level: aggression,
        });
        setTechniques((result.primary_techniques || []).slice(0, 8).map((t) => ({
          technique_id: t.technique_id,
          name: t.name,
          tactic: t.tactic,
          confidence: t.priority / 10,
          rationale: t.applicability,
          subtechniques: t.prerequisites || [],
          detection_methods: [],
          mitigations: [],
        })));
        setSummary(result.analysis || null);
        setChainName(result.recommended_chain?.name ?? null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "MITRE analysis failed");
    } finally {
      setLoading(false);
    }
  }, [target, aggression, engagementId, attackDescription, mode]);

  useEffect(() => {
    if (!target.trim() && !attackDescription?.trim()) return;
    const t = window.setTimeout(() => void refresh(), 600);
    return () => window.clearTimeout(t);
  }, [target, aggression, attackDescription, mode, refresh]);

  return (
    <div className="rounded-xl border border-purple-500/20 bg-slate-900/40 p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Shield className="h-4 w-4 text-purple-400" />
          <h3 className="text-sm font-semibold text-white">MITRE AI</h3>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex rounded-md border border-slate-700 p-0.5 text-[10px]">
            <button
              type="button"
              onClick={() => setMode("suggest")}
              className={`rounded px-2 py-0.5 ${
                mode === "suggest" ? "bg-purple-600 text-white" : "text-slate-400"
              }`}
            >
              Target
            </button>
            <button
              type="button"
              onClick={() => setMode("analyze")}
              disabled={!attackDescription?.trim()}
              className={`rounded px-2 py-0.5 ${
                mode === "analyze" ? "bg-purple-600 text-white" : "text-slate-400"
              } disabled:opacity-40`}
            >
              Live run
            </button>
          </div>
          <button
            type="button"
            onClick={() => void refresh()}
            disabled={loading}
            className="rounded p-1 text-slate-400 hover:bg-slate-800 hover:text-white disabled:opacity-50"
            aria-label="Refresh MITRE analysis"
          >
            {loading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <RefreshCw className="h-3.5 w-3.5" />
            )}
          </button>
        </div>
      </div>

      {error && <p className="mb-2 text-xs text-red-400">{error}</p>}

      {!target.trim() && mode === "suggest" && (
        <p className="text-xs text-slate-500">Enter a target to auto-map MITRE techniques.</p>
      )}

      {summary && (
        <div className="mb-3 rounded-lg border border-purple-500/10 bg-purple-950/20 p-3">
          <p className="flex items-center gap-1.5 text-[11px] font-medium text-purple-300">
            <Brain className="h-3 w-3" />
            {chainName || "Strategic analysis"}
          </p>
          <p className="mt-1 line-clamp-4 text-xs leading-relaxed text-slate-400">{summary}</p>
        </div>
      )}

      {techniques.length > 0 && (
        <ul className="max-h-64 space-y-2 overflow-y-auto pr-1">
          {techniques.map((tech, i) => (
            <li
              key={`${tech.technique_id}-${i}`}
              className="rounded-lg border border-slate-800 bg-slate-950/40 p-2.5"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="shrink-0 rounded bg-purple-500/10 px-1.5 py-0.5 text-[10px] font-bold text-purple-400">
                      {tech.technique_id}
                    </span>
                    <span className="truncate text-xs font-medium text-slate-200">{tech.name}</span>
                  </div>
                  <p className="mt-0.5 text-[10px] text-slate-500">{tech.tactic}</p>
                </div>
                <span className="shrink-0 text-[10px] text-slate-500">
                  {Math.round(tech.confidence * 100)}%
                </span>
              </div>
              {tech.rationale && (
                <p className="mt-1 line-clamp-2 text-[11px] text-slate-500">{tech.rationale}</p>
              )}
            </li>
          ))}
        </ul>
      )}

      {!loading && techniques.length === 0 && target.trim() && !error && (
        <p className="text-xs text-slate-500">No techniques mapped yet.</p>
      )}

      {engagementId && (
        <p className="mt-3 flex items-center gap-1 text-[10px] text-slate-600">
          <ChevronRight className="h-3 w-3" />
          Synced with engagement {engagementId.slice(0, 8)}…
        </p>
      )}
    </div>
  );
}
