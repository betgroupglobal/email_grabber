"use client";

import { useState } from "react";
import RealTimeAttackMonitor from "@/components/attack-monitoring/RealTimeAttackMonitor";
import AgentStatusMonitor from "@/components/attack-monitoring/AgentStatusMonitor";
import ServicesControlPanel from "@/components/services/ServicesControlPanel";
import SessionManagement from "@/components/attack-monitoring/SessionManagement";
import AlertConfiguration from "@/components/attack-monitoring/AlertConfiguration";
import ExportPanel from "@/components/attack-monitoring/ExportPanel";

type OpsTab = "monitor" | "agents" | "services" | "sessions" | "alerts" | "export";

const tabs: { id: OpsTab; label: string; icon: string }[] = [
  { id: "monitor", label: "Monitor", icon: "📡" },
  { id: "agents", label: "Agents", icon: "👥" },
  { id: "services", label: "Services", icon: "⚙️" },
  { id: "sessions", label: "Sessions", icon: "🗂️" },
  { id: "alerts", label: "Alerts", icon: "🔔" },
  { id: "export", label: "Export", icon: "📤" },
];

interface OperationsCenterProps {
  engagementId?: string | null;
}

export function OperationsCenter({ engagementId }: OperationsCenterProps) {
  const [activeTab, setActiveTab] = useState<OpsTab>("monitor");

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2 border-b border-slate-800 pb-3">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-all ${
              activeTab === tab.id
                ? "bg-cyan-600 text-white"
                : "bg-transparent text-slate-400 hover:bg-slate-800 hover:text-white"
            }`}
          >
            <span>{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === "monitor" && <RealTimeAttackMonitor engagementId={engagementId} />}
      {activeTab === "agents" && <AgentStatusMonitor />}
      {activeTab === "services" && <ServicesControlPanel />}
      {activeTab === "sessions" && <SessionManagement />}
      {activeTab === "alerts" && <AlertConfiguration />}
      {activeTab === "export" && <ExportPanel />}
    </div>
  );
}
