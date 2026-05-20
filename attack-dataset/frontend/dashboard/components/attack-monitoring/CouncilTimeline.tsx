"use client";

import {
  buildCouncilTimeline,
  agentLabel,
  directiveActionLabel,
  parseCouncilGroundingPack,
  type CouncilTimelineTurn,
  type LiveCouncilState,
  type LiveDirective,
  type CouncilWsEvent,
} from "@/lib/liveCouncil";

interface CouncilTimelineProps {
  liveCouncil?: LiveCouncilState;
  wsEvents?: CouncilWsEvent[];
  chainsVersion?: number;
  className?: string;
  engagementId?: string;
  onApprove?: () => void | Promise<void>;
  approving?: boolean;
}

function DirectiveBanner({ directive }: { directive: LiveDirective }) {
  const action = directive.action || "continue";
  const isHold = action === "abort";
  const isPivot = action === "pivot_chain" || action === "patch_chain" || action === "reinitiate_chain";
  return (
    <div
      className={`rounded-lg border px-4 py-3 ${
        isHold
          ? "border-amber-500/30 bg-amber-950/20"
          : action === "pivot_chain"
            ? "border-violet-500/30 bg-violet-950/20"
            : isPivot
              ? "border-cyan-500/30 bg-cyan-950/20"
              : "border-slate-700 bg-slate-950/40"
      }`}
    >
      <div className="mb-1 flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-cyan-400">
          Active directive
        </span>
        <span className="rounded bg-slate-800 px-2 py-0.5 text-[10px] text-slate-300">
          {directiveActionLabel(action)}
        </span>
        {directive.opsec_veto && (
          <span className="rounded bg-slate-700/80 px-2 py-0.5 text-[10px] font-medium text-slate-300">
            OpSec note
          </span>
        )}
        {directive.confidence != null && (
          <span className="text-[10px] text-slate-500">
            confidence {(directive.confidence * 100).toFixed(0)}%
          </span>
        )}
      </div>
      <p className="text-sm text-slate-300">{directive.rationale}</p>
      {directive.rationale_steps && directive.rationale_steps.length > 0 && (
        <ol className="mt-2 list-decimal space-y-1 pl-4 text-xs text-slate-400">
          {directive.rationale_steps.map((s, i) => (
            <li key={i}>
              <span className="text-slate-300">{s.step}</span>: {s.detail}
            </li>
          ))}
        </ol>
      )}
      {directive.failure_class && (
        <p className="mt-2 text-[10px] text-slate-500">Failure class: {directive.failure_class}</p>
      )}
      {directive.dataset_record_ids && directive.dataset_record_ids.length > 0 && (
        <p className="mt-2 text-[10px] text-slate-500">
          Dataset records: {directive.dataset_record_ids.slice(0, 8).join(", ")}
          {directive.dataset_record_ids.length > 8 ? "…" : ""}
        </p>
      )}
    </div>
  );
}

function MemoCard({
  agent,
  memo,
}: {
  agent: string;
  memo: Record<string, unknown>;
}) {
  const summary =
    (memo.assessment as string) ||
    (memo.risk_note as string) ||
    (memo.chain_patch_hint as string) ||
    (memo.timing_advice as string) ||
    JSON.stringify(memo).slice(0, 160);

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
      <p className="mb-1 text-xs font-medium text-purple-400">{agentLabel(agent)}</p>
      <p className="text-xs leading-relaxed text-slate-400">{summary}</p>
      {memo.veto === true && (
        <p className="mt-1 text-[10px] font-medium text-amber-400">Veto recommended</p>
      )}
    </div>
  );
}

function TurnRow({ row }: { row: CouncilTimelineTurn }) {
  return (
    <div className="relative border-l-2 border-cyan-500/30 pl-5 pb-6 last:pb-0">
      <span className="absolute -left-[7px] top-0 h-3 w-3 rounded-full bg-cyan-500 ring-4 ring-[#080c14]" />
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="text-sm font-semibold text-white">Turn {row.turn}</span>
        {row.trigger && (
          <span className="rounded bg-slate-800 px-2 py-0.5 text-[10px] text-slate-400">
            {row.trigger}
          </span>
        )}
        {row.grounding && (
          <span className="text-[10px] text-slate-500">
            {row.grounding.hit_count ?? 0} dataset hits
            {row.grounding.ml_top ? ` · ML: ${row.grounding.ml_top}` : ""}
            {row.chainVersion != null ? ` · replan v${row.chainVersion}` : ""}
          </span>
        )}
      </div>
      {row.grounding?.query_text && (
        <p className="mb-2 truncate text-[10px] font-mono text-slate-600" title={row.grounding.query_text}>
          {row.grounding.query_text}
        </p>
      )}
      <div className="space-y-2">
        {row.memos.map((m, i) => (
          <MemoCard key={`${row.turn}-${m.agent}-${i}`} agent={m.agent} memo={m.memo} />
        ))}
      </div>
      {row.directive && (
        <div className="mt-2">
          <DirectiveBanner directive={row.directive} />
        </div>
      )}
      {row.diffSummary && (
        <p className="mt-2 text-xs text-cyan-400/80">{row.diffSummary}</p>
      )}
    </div>
  );
}

export default function CouncilTimeline({
  liveCouncil,
  wsEvents = [],
  chainsVersion,
  className = "",
  onApprove,
  approving = false,
}: CouncilTimelineProps) {
  const turns = buildCouncilTimeline(liveCouncil, wsEvents);
  const parsedGrounding = liveCouncil?.last_grounding_pack
    ? parseCouncilGroundingPack(liveCouncil.last_grounding_pack)
    : null;
  const lastDirective = liveCouncil?.last_directive;
  const pending = liveCouncil?.pending_directive;
  const enabled = liveCouncil?.enabled;
  const replans = liveCouncil?.replans_used ?? 0;
  const maxReplans = liveCouncil?.max_replans ?? 5;

  if (!enabled && turns.length === 0 && !lastDirective) {
    return null;
  }

  return (
    <div className={`space-y-4 ${className}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-purple-400 animate-pulse" />
          <span className="text-sm font-medium text-purple-300">Live Attack Council</span>
        </div>
        <div className="flex gap-3 text-[10px] text-slate-500">
          <span>Turn {liveCouncil?.turn ?? 0}</span>
          <span>
            Replans {replans}/{maxReplans}
          </span>
          {chainsVersion != null && chainsVersion > 0 && (
            <span>Chain v{chainsVersion}</span>
          )}
        </div>
      </div>

      {parsedGrounding?.success && parsedGrounding.data.query_text && (
        <p className="truncate text-[10px] font-mono text-slate-600" title={parsedGrounding.data.query_text}>
          Latest grounding: {parsedGrounding.data.dataset_hits?.length ?? 0} hits
          {parsedGrounding.data.ml_predictions?.[0]?.label
            ? ` · ML: ${parsedGrounding.data.ml_predictions[0].label}`
            : ""}
        </p>
      )}

      {pending && onApprove && (
        <div className="rounded-lg border border-amber-500/40 bg-amber-950/30 p-4">
          <p className="mb-2 text-sm text-slate-300">Optional council review — execution is not blocked</p>
          <DirectiveBanner directive={pending} />
          <button
            type="button"
            onClick={() => void onApprove()}
            disabled={approving}
            className="mt-3 rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-500 disabled:opacity-50"
          >
            {approving ? "Approving…" : "Approve directive"}
          </button>
        </div>
      )}

      {lastDirective &&
        !turns.some((t) => t.directive?.directive_id === lastDirective.directive_id) && (
          <DirectiveBanner directive={lastDirective} />
        )}

      {turns.length === 0 ? (
        <p className="text-xs text-slate-500">
          Council enabled — waiting for step events during chain execution.
        </p>
      ) : (
        <div className="space-y-0">
          {turns.map((row) => (
            <TurnRow key={row.turn} row={row} />
          ))}
        </div>
      )}
    </div>
  );
}
