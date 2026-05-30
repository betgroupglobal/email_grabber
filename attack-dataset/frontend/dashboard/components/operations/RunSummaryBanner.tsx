"use client";

import { CheckCircle2, RotateCcw, Target } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { GuidedAutonomousStatus } from "@/lib/orchestratorClient";

export interface RunSummaryBannerProps {
  status: GuidedAutonomousStatus | null;
  onRerun?: () => void | Promise<void>;
  onNewTarget?: () => void;
  rerunning?: boolean;
}

export function RunSummaryBanner({
  status,
  onRerun,
  onNewTarget,
  rerunning = false,
}: RunSummaryBannerProps) {
  const ga = status?.guided_autonomous;
  const runStatus = ga?.status;
  const isDone =
    runStatus === "complete" || runStatus === "stopped" || runStatus === "error";
  if (!isDone) return null;

  const summary = ga?.run_summary;
  const phasesDone =
    summary?.phases_completed ??
    (ga?.phases || []).filter((p) => p.status === "complete" || p.status === "skipped")
      .length;
  const toolsCount = summary?.tools_invoked_count ?? ga?.tools_invoked_count ?? 0;
  const pathways = summary?.pathway_attempts_count ?? ga?.pathway_attempts_count ?? 0;
  const councilTurns = summary?.council_turns ?? status?.live_council?.turn ?? 0;
  const councilApprovals =
    summary?.council_approvals ??
    (status?.live_council?.directives || []).filter(
      (d) => d.approved_at || d.status === "approved"
    ).length;

  const label =
    runStatus === "complete"
      ? "Run complete"
      : runStatus === "stopped"
        ? "Run stopped"
        : "Run ended with error";

  return (
    <div
      className={`flex shrink-0 flex-wrap items-center justify-between gap-3 rounded-lg border px-3 py-2 ${
        runStatus === "complete"
          ? "border-emerald-500/30 bg-emerald-950/25"
          : runStatus === "error"
            ? "border-red-500/30 bg-red-950/25"
            : "border-amber-500/30 bg-amber-950/25"
      }`}
    >
      <div className="flex min-w-0 items-start gap-2">
        <CheckCircle2
          className={`mt-0.5 size-4 shrink-0 ${
            runStatus === "complete"
              ? "text-emerald-400"
              : runStatus === "error"
                ? "text-red-400"
                : "text-amber-400"
          }`}
        />
        <div className="min-w-0">
          <p className="text-xs font-medium text-slate-200">{label}</p>
          <p className="mt-0.5 font-mono text-[10px] text-slate-400">
            Phases {phasesDone}/{summary?.phases_total ?? 8} · tools {toolsCount} · pathways{" "}
            {pathways} · council turns {councilTurns}
            {councilApprovals > 0 ? ` · ${councilApprovals} approved` : ""}
          </p>
          {summary?.tools_used && summary.tools_used.length > 0 && (
            <p className="mt-0.5 line-clamp-1 font-mono text-[10px] text-slate-500">
              {summary.tools_used.join(" · ")}
            </p>
          )}
          {ga?.error && (
            <p className="mt-1 text-[10px] text-red-400">{ga.error}</p>
          )}
        </div>
      </div>
      <div className="flex shrink-0 flex-wrap gap-2">
        {onRerun && (
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={rerunning}
            onClick={() => void onRerun()}
            className="h-7 gap-1 border-cyan-600/40 text-cyan-300"
          >
            <RotateCcw className="size-3" />
            Re-run
          </Button>
        )}
        {onNewTarget && (
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={onNewTarget}
            className="h-7 gap-1 text-slate-400"
          >
            <Target className="size-3" />
            New target
          </Button>
        )}
      </div>
    </div>
  );
}
