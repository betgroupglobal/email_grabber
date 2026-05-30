"use client";

import { useCallback, useEffect } from "react";
import type { LiveCouncilState } from "@/lib/liveCouncil";
import type { ThoughtCycleStageId } from "@/lib/thoughtProcessPattern";
import { resolveHotkeyAction } from "./hotkeys";
import { runTemplate } from "./templaterRunner";
import type { TemplaterRunContext } from "./templaterRunner";

export interface UseTemplaterHotkeysOptions {
  enabled: boolean;
  engagementId: string;
  isActive: boolean;
  currentStage?: ThoughtCycleStageId;
  liveCouncil?: LiveCouncilState | null;
  templaterCtx: Omit<TemplaterRunContext, "engagementId" | "currentStage" | "liveCouncil">;
}

/** Register templater hotkeys while operations run terminal is focused. */
export function useTemplaterHotkeys(opts: UseTemplaterHotkeysOptions) {
  const {
    enabled,
    engagementId,
    isActive,
    currentStage,
    liveCouncil,
    templaterCtx,
  } = opts;

  const handleHotkey = useCallback(
    async (event: KeyboardEvent) => {
      if (!enabled || !isActive || !engagementId) return;

      const action = resolveHotkeyAction(event, {
        liveCouncil,
        currentStage,
        hasPendingDirective: Boolean(liveCouncil?.pending_directive),
        hasPendingPathway: Boolean(liveCouncil?.pending_pathway),
      });

      if (!action) return;

      event.preventDefault();
      event.stopPropagation();

      await runTemplate(action.templateId, {
        engagementId,
        currentStage,
        liveCouncil,
        ...templaterCtx,
      });
    },
    [enabled, isActive, engagementId, currentStage, liveCouncil, templaterCtx]
  );

  useEffect(() => {
    if (!enabled || !isActive) return;
    window.addEventListener("keydown", handleHotkey);
    return () => window.removeEventListener("keydown", handleHotkey);
  }, [enabled, isActive, handleHotkey]);
}
