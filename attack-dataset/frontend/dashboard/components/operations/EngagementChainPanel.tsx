"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ExternalLink, Loader2, Play, Square, Target } from "lucide-react";
import { Button } from "@/components/ui/button";
import { orchestratorFetchInit, orchestratorHttp } from "@/lib/config";
import { executeAttackChain, fetchEngagement } from "@/lib/orchestratorClient";

interface ChainStep {
  tool?: string;
  phase?: string;
  description?: string;
}

interface AttackChain {
  chain_id?: string;
  confidence?: number;
  steps?: ChainStep[];
  steps_count?: number;
}

interface EngagementChainPanelProps {
  engagementId: string;
}

export function EngagementChainPanel({ engagementId }: EngagementChainPanelProps) {
  const [chains, setChains] = useState<AttackChain[]>([]);
  const [chainIdx, setChainIdx] = useState(0);
  const [loading, setLoading] = useState(true);
  const [executing, setExecuting] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [executionId, setExecutionId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await fetchEngagement(engagementId);
      const list = data.attack_chains?.chains || [];
      setChains(list);
      setExecutionId(data.chain_execution?.execution_id ?? null);
    } catch {
      setStatus("Failed to load chains");
    } finally {
      setLoading(false);
    }
  }, [engagementId]);

  useEffect(() => {
    void load();
    const interval = setInterval(() => void load(), 5000);
    return () => clearInterval(interval);
  }, [load]);

  const executeChain = async () => {
    const chain = chains[chainIdx];
    if (!chain) return;
    setExecuting(true);
    setStatus("Executing chain with live council…");
    try {
      const result = await executeAttackChain({
        engagement_id: engagementId,
        chain_index: chainIdx,
        chain,
      });
      if (result.ok) {
        const data = result.data as { success?: boolean };
        setStatus(data.success ? "Chain executed" : "Execution reported failure");
        setTimeout(() => void load(), 1500);
      } else {
        setStatus(String(result.body.error || "Execution failed"));
      }
    } catch {
      setStatus("Execution error");
    } finally {
      setExecuting(false);
    }
  };

  const stopExecution = async () => {
    if (!executionId) return;
    try {
      await fetch(
        orchestratorHttp("/stop-execution"),
        orchestratorFetchInit({
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ execution_id: executionId }),
        })
      );
      setStatus("Stopped");
      setExecuting(false);
      void load();
    } catch {
      setStatus("Stop failed");
    }
  };

  const selected = chains[chainIdx];

  return (
    <div className="rounded-xl border border-cyan-500/20 bg-slate-900/40 p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Target className="h-4 w-4 text-cyan-400" />
          <h3 className="text-sm font-semibold text-white">Attack chains</h3>
        </div>
        <Link
          href={`/engagement/${engagementId}`}
          className="flex items-center gap-1 text-[11px] text-cyan-400 hover:underline"
        >
          Full view <ExternalLink className="h-3 w-3" />
        </Link>
      </div>

      {loading && chains.length === 0 ? (
        <div className="flex items-center gap-2 py-6 text-xs text-slate-500">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading chains…
        </div>
      ) : chains.length === 0 ? (
        <p className="py-4 text-xs text-slate-500">
          Chains appear after recon / OpSec phases complete. The autonomous pipeline builds them
          automatically.
        </p>
      ) : (
        <>
          <div className="mb-3 flex flex-wrap gap-2">
            {chains.map((chain, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => setChainIdx(idx)}
                className={`rounded-lg border px-3 py-2 text-left text-xs transition-all ${
                  chainIdx === idx
                    ? "border-cyan-500/40 bg-cyan-950/30 text-cyan-200"
                    : "border-slate-800 bg-slate-950/40 text-slate-400 hover:border-slate-700"
                }`}
              >
                <span className="font-medium">Chain {idx + 1}</span>
                <span className="ml-2 text-slate-500">
                  {chain.steps?.length ?? chain.steps_count ?? 0} steps
                  {chain.confidence != null && ` · ${Math.round(chain.confidence * 100)}%`}
                </span>
              </button>
            ))}
          </div>

          {selected?.steps && selected.steps.length > 0 && (
            <ol className="mb-3 max-h-40 space-y-1 overflow-y-auto rounded-lg border border-slate-800 bg-slate-950/30 p-2">
              {selected.steps.slice(0, 6).map((step, i) => (
                <li key={i} className="flex gap-2 text-[11px] text-slate-400">
                  <span className="shrink-0 font-mono text-slate-600">{i + 1}.</span>
                  <span className="truncate">
                    {step.description || step.tool || step.phase || "Step"}
                  </span>
                </li>
              ))}
              {selected.steps.length > 6 && (
                <li className="text-[10px] text-slate-600">
                  +{selected.steps.length - 6} more steps
                </li>
              )}
            </ol>
          )}

          <div className="flex flex-wrap items-center gap-2">
            <Button
              size="sm"
              onClick={() => void executeChain()}
              disabled={executing}
              className="h-8 bg-cyan-600 hover:bg-cyan-500"
            >
              {executing ? (
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
              ) : (
                <Play className="mr-1.5 h-3.5 w-3.5" />
              )}
              Execute chain
            </Button>
            {executionId && (
              <Button size="sm" variant="outline" onClick={() => void stopExecution()} className="h-8">
                <Square className="mr-1.5 h-3.5 w-3.5" />
                Stop
              </Button>
            )}
          </div>
        </>
      )}

      {status && <p className="mt-2 text-[11px] text-slate-500">{status}</p>}
    </div>
  );
}
