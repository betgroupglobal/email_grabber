"use client";

import type { LiveCouncilState } from "@/lib/liveCouncil";
import { cn } from "@/lib/utils";
import {
  deriveSuggestedHotkey,
  hotkeyLegend,
  suggestedFromDirectiveFields,
} from "@/lib/templater/hotkeys";

export interface HotkeyHintBarProps {
  liveCouncil?: LiveCouncilState | null;
  className?: string;
}

export function HotkeyHintBar({ liveCouncil, className }: HotkeyHintBarProps) {
  const pending = liveCouncil?.pending_directive;
  const fromFields =
    pending && typeof pending === "object"
      ? suggestedFromDirectiveFields(pending as { suggested_hotkey?: string; suggested_template_id?: string; action?: string })
      : null;
  const suggested = fromFields ?? deriveSuggestedHotkey(liveCouncil);
  const legend = hotkeyLegend({ liveCouncil, showStageHotkeys: true });

  if (!suggested && !pending && !liveCouncil?.pending_pathway) return null;

  return (
    <div
      className={cn(
        "rounded-lg border border-violet-500/25 bg-violet-950/20 px-2 py-1.5",
        className
      )}
      role="note"
      aria-label="Templater hotkey hints"
    >
      {suggested && (
        <p className="font-mono text-[10px] leading-snug text-violet-200/95">
          <span className="text-violet-400/90">AI suggests:</span> press{" "}
          <kbd className="rounded border border-violet-500/40 bg-violet-950/60 px-1 py-px text-[9px] text-violet-100">
            {suggested.hotkeyLabel}
          </kbd>{" "}
          — {suggested.message}
        </p>
      )}
      <div className="mt-1 flex flex-wrap gap-x-2 gap-y-0.5">
        {legend.slice(0, 6).map((row) => (
          <span key={`${row.keys}-${row.label}`} className="font-mono text-[9px] text-slate-500">
            <kbd className="rounded border border-slate-700 bg-slate-900/80 px-0.5 text-[8px] text-slate-400">
              {row.keys}
            </kbd>{" "}
            {row.label}
          </span>
        ))}
      </div>
    </div>
  );
}
