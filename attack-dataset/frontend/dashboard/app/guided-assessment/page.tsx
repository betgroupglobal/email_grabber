"use client";

import { useState } from "react";
import { GuidedAssessmentWizard } from "@/components/guided-assessment/GuidedAssessmentWizard";
import { GuidedAutonomousPanel } from "@/components/guided-assessment/GuidedAutonomousPanel";
import { Bot, ListChecks } from "lucide-react";

export default function GuidedAssessmentPage() {
  const [mode, setMode] = useState<"autonomous" | "manual">("autonomous");

  return (
    <div className="min-h-screen bg-[#080c14] text-white -m-6 lg:-m-8">
      <header className="sticky top-0 z-40 border-b border-slate-800/60 bg-[#080c14]/80 backdrop-blur-xl">
        <div className="mx-auto max-w-7xl px-6 py-4">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h1 className="flex items-center gap-2 text-2xl font-bold text-cyan-400">
                <ListChecks className="h-7 w-7" />
                Guided OpSec Assessment
              </h1>
              <p className="text-sm text-slate-500">
                Jailbreak AI autonomous pipeline or manual 8-phase wizard
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex rounded-lg border border-slate-700 p-0.5 text-xs">
                <button
                  type="button"
                  onClick={() => setMode("autonomous")}
                  className={`flex items-center gap-1 rounded-md px-3 py-1.5 ${
                    mode === "autonomous"
                      ? "bg-cyan-600 text-white"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  <Bot className="h-3.5 w-3.5" />
                  Autonomous
                </button>
                <button
                  type="button"
                  onClick={() => setMode("manual")}
                  className={`rounded-md px-3 py-1.5 ${
                    mode === "manual"
                      ? "bg-slate-600 text-white"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  Manual wizard
                </button>
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-8">
        {mode === "autonomous" ? <GuidedAutonomousPanel /> : <GuidedAssessmentWizard />}
      </main>
    </div>
  );
}
