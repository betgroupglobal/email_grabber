"use client";

import { useState, useEffect } from "react";
import { getWebSocket, connectWebSocket, disconnectWebSocket } from "@/lib/websocket";
import { getAgentStatus } from "@/lib/api";

interface AgentCapability {
  id: string;
  name: string;
  description: string;
  successRate: number;
  avgExecutionTime: number;
}

interface Agent {
  id: string;
  type: "RECON" | "EXPLOIT" | "POST_EXPLOITATION" | "CLEANUP";
  name: string;
  status: "idle" | "running" | "waiting" | "completed" | "failed";
  currentTask?: string;
  capabilities: AgentCapability[];
  executionHistory: {
    id: string;
    task: string;
    status: string;
    duration: number;
    timestamp: string;
  }[];
  performance: {
    totalTasks: number;
    successfulTasks: number;
    avgDuration: number;
    lastActive: string;
  };
}

export default function AgentStatusMonitor() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [connectionState, setConnectionState] = useState<"connecting" | "open" | "closing" | "closed">("closed");

  useEffect(() => {
    // Load agent data from API
    const loadAgentData = async () => {
      try {
        const response = await getAgentStatus();
        setAgents(response.agents);
        if (response.agents.length > 0) {
          setSelectedAgent(response.agents[0]);
        }
      } catch (error) {
        console.error("Failed to load agent data:", error);
        // Set empty state if API fails
        setAgents([]);
        setSelectedAgent(null);
      }
    };

    loadAgentData();

    // WebSocket connection for real-time agent status (temporarily disabled)
    const ws = getWebSocket();
    
    // Subscribe to agent status updates
    const unsubscribe = ws.subscribe("agent_status", (message) => {
      if (message.data.agents) {
        setAgents(message.data.agents);
      }
    });

    // Temporarily disable WebSocket connection due to protocol issues
    // connectWebSocket();

    // Update connection state
    const checkConnection = () => {
      setConnectionState(ws.getConnectionState());
    };
    
    const connectionInterval = setInterval(checkConnection, 1000);

    return () => {
      clearInterval(connectionInterval);
      unsubscribe();
      // disconnectWebSocket();
    };
  }, []);

  const getAgentTypeIcon = (type: string) => {
    switch (type) {
      case "RECON": return "🔍";
      case "EXPLOIT": return "💥";
      case "POST_EXPLOITATION": return "🚀";
      case "CLEANUP": return "🧹";
      default: return "🤖";
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "idle": return "bg-slate-600";
      case "running": return "bg-green-600 animate-pulse";
      case "waiting": return "bg-yellow-600";
      case "completed": return "bg-blue-600";
      case "failed": return "bg-red-600";
      default: return "bg-gray-600";
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case "idle": return "Idle";
      case "running": return "Running";
      case "waiting": return "Waiting";
      case "completed": return "Completed";
      case "failed": return "Failed";
      default: return "Unknown";
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-cyan-400">Multi-Agent Status Monitor</h2>
          <p className="text-slate-400">Real-time AI-powered agent coordination</p>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className={`w-3 h-3 rounded-full ${
              connectionState === "open" ? "bg-green-500" :
              connectionState === "connecting" ? "bg-yellow-500 animate-pulse" :
              "bg-red-500"
            }`} />
            <span className="text-sm text-slate-300">
              {connectionState === "open" ? "Live Updates" :
               connectionState === "connecting" ? "Connecting..." :
               "Simulation Mode"}
            </span>
          </div>
          <div className="text-sm text-slate-400">
            Active: {agents.filter(a => a.status === "running").length}/{agents.length}
          </div>
        </div>
      </div>

      {/* Agent Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {agents.map((agent) => (
          <div
            key={agent.id}
            onClick={() => setSelectedAgent(agent)}
            className={`bg-slate-800/50 border rounded-lg p-4 cursor-pointer transition-all hover:shadow-lg ${
              selectedAgent?.id === agent.id ? "border-cyan-500 ring-2 ring-cyan-500/50" : "border-slate-700"
            }`}
          >
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="text-2xl">{getAgentTypeIcon(agent.type)}</span>
                <span className="font-medium text-white">{agent.name}</span>
              </div>
              <div className={`w-3 h-3 rounded-full ${getStatusColor(agent.status)}`} />
            </div>
            
            <p className="text-sm text-slate-400 mb-2">{getStatusText(agent.status)}</p>
            
            {agent.currentTask && (
              <p className="text-xs text-slate-300 mb-3 truncate">{agent.currentTask}</p>
            )}

            <div className="flex items-center justify-between text-xs text-slate-500">
              <span>{agent.performance.totalTasks} tasks</span>
              <span>{((agent.performance.successfulTasks / agent.performance.totalTasks) * 100).toFixed(0)}% success</span>
            </div>
          </div>
        ))}
      </div>

      {/* Selected Agent Details */}
      {selectedAgent && (
        <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <span className="text-3xl">{getAgentTypeIcon(selectedAgent.type)}</span>
              <div>
                <h3 className="text-xl font-bold text-white">{selectedAgent.name}</h3>
                <p className="text-slate-400">{selectedAgent.type}</p>
              </div>
            </div>
            <button
              onClick={() => setSelectedAgent(null)}
              className="text-slate-400 hover:text-white transition-colors"
            >
              ✕
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <div className="bg-slate-900/50 rounded-lg p-3">
              <p className="text-xs text-slate-400">Total Tasks</p>
              <p className="text-2xl font-bold text-white">{selectedAgent.performance?.totalTasks || 0}</p>
            </div>
            <div className="bg-slate-900/50 rounded-lg p-3">
              <p className="text-xs text-slate-400">Success Rate</p>
              <p className="text-2xl font-bold text-green-400">
                {selectedAgent.performance ? ((selectedAgent.performance.successfulTasks / selectedAgent.performance.totalTasks) * 100).toFixed(0) : 0}%
              </p>
            </div>
            <div className="bg-slate-900/50 rounded-lg p-3">
              <p className="text-xs text-slate-400">Avg Duration</p>
              <p className="text-2xl font-bold text-cyan-400">{selectedAgent.performance?.avgDuration || 0}s</p>
            </div>
          </div>

          {/* AI Analysis */}
          <div className="mb-6 p-3 bg-slate-900/50 rounded-lg border border-slate-600">
            <div className="flex items-center gap-2 mb-2">
              <span>🤖</span>
              <span className="font-medium text-cyan-400">AI Agent Analysis</span>
            </div>
            <p className="text-sm text-slate-300">
              Agent performance analysis indicates moderate performance levels. 
              Current success rate of {selectedAgent.performance ? ((selectedAgent.performance.successfulTasks / selectedAgent.performance.totalTasks) * 100).toFixed(0) : 0}% suggests the agent is performing {selectedAgent.performance && (selectedAgent.performance.successfulTasks / selectedAgent.performance.totalTasks > 0.7) ? "within expected parameters" : "below optimal levels"}.
              Consider adjusting task allocation based on current workload and recent performance trends.
            </p>
          </div>

          {/* Capabilities */}
          <div className="mb-6">
            <h4 className="font-medium text-white mb-3">Capabilities</h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {selectedAgent.capabilities?.map((capability) => (
                <div key={capability.id} className="bg-slate-900/50 rounded-lg p-3 border border-slate-600">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium text-white text-sm">{capability.name}</span>
                    <span className={`text-xs px-2 py-1 rounded ${
                      capability.successRate > 0.7 ? "bg-green-900 text-green-300" :
                      capability.successRate > 0.5 ? "bg-yellow-900 text-yellow-300" :
                      "bg-red-900 text-red-300"
                    }`}>
                      {(capability.successRate * 100).toFixed(0)}%
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mb-2">{capability.description}</p>
                  <div className="flex items-center justify-between text-xs text-slate-500">
                    <span>Avg: {capability.avgExecutionTime}s</span>
                  </div>
                </div>
              )) || <div className="text-slate-500 text-sm">No capabilities available</div>}
            </div>
          </div>

          {/* Execution History */}
          <div>
            <h4 className="font-medium text-white mb-3">Recent Execution History</h4>
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {selectedAgent.executionHistory && selectedAgent.executionHistory.length > 0 ? (
                selectedAgent.executionHistory.map((history) => (
                  <div
                    key={history.id}
                    className={`flex items-center justify-between p-2 rounded-lg border ${
                      history.status === "success" ? "border-green-600 bg-green-900/20" :
                      history.status === "failure" ? "border-red-600 bg-red-900/20" :
                      "border-slate-600 bg-slate-900/30"
                    }`}
                  >
                    <div className="flex-1">
                      <p className="text-sm text-white">{history.task}</p>
                      <p className="text-xs text-slate-400">{new Date(history.timestamp).toLocaleString()}</p>
                    </div>
                    <div className="text-right">
                      <span className={`text-xs px-2 py-1 rounded ${
                        history.status === "success" ? "bg-green-600 text-white" :
                        "bg-red-600 text-white"
                      }`}>
                        {history.status}
                      </span>
                      <p className="text-xs text-slate-400 mt-1">{history.duration}s</p>
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-center text-slate-500 py-4">
                  No execution history available
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}