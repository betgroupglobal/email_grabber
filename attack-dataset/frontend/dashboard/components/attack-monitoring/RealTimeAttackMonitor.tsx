"use client";

import { useState, useEffect, useRef } from "react";
import { orchestratorWs } from "@/lib/config";

interface AttackEvent {
  id: string;
  timestamp: string;
  type: "scan" | "exploit" | "persistence" | "exfiltration" | "detection";
  severity: "low" | "medium" | "high" | "critical";
  source: string;
  target: string;
  description: string;
  details?: Record<string, any>;
}

interface MonitoringStats {
  totalAttacks: number;
  activeSessions: number;
  detectedThreats: number;
  blockedAttacks: number;
  avgResponseTime: number;
}

interface RealTimeAttackMonitorProps {
  engagementId?: string | null;
}

function parseAttackEvent(raw: Record<string, unknown>): AttackEvent | null {
  const event = (raw.event ?? raw) as Record<string, unknown>;
  if (!event || typeof event !== "object") return null;
  const description = String(event.description ?? "");
  if (!description) return null;
  return {
    id: String(event.id ?? `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`),
    timestamp: String(event.timestamp ?? new Date().toISOString()),
    type: (event.type as AttackEvent["type"]) || "detection",
    severity: (event.severity as AttackEvent["severity"]) || "medium",
    source: String(event.source ?? "orchestrator"),
    target: String(event.target ?? "Unknown"),
    description,
    details: (event.details as Record<string, unknown>) || {},
  };
}

export default function RealTimeAttackMonitor({ engagementId }: RealTimeAttackMonitorProps) {
  const [events, setEvents] = useState<AttackEvent[]>([]);
  const [stats, setStats] = useState<MonitoringStats>({
    totalAttacks: 0,
    activeSessions: 0,
    detectedThreats: 0,
    blockedAttacks: 0,
    avgResponseTime: 0,
  });
  const [isLive, setIsLive] = useState(true);
  const [selectedSeverity, setSelectedSeverity] = useState<string>("all");
  const [connectionState, setConnectionState] = useState<"connecting" | "open" | "closing" | "closed">("closed");
  const wsRef = useRef<WebSocket | null>(null);
  const isLiveRef = useRef(isLive);
  isLiveRef.current = isLive;

  useEffect(() => {
    if (!engagementId) {
      setConnectionState("closed");
      return;
    }

    const wsUrl = `${orchestratorWs(`/events/${engagementId}`)}?engagement=${encodeURIComponent(engagementId)}`;
    setConnectionState("connecting");
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    const pushEvent = (newEvent: AttackEvent) => {
      if (!isLiveRef.current) return;
      setEvents((prev) => [newEvent, ...prev].slice(0, 50));
      setStats((prev) => ({
        ...prev,
        totalAttacks: prev.totalAttacks + 1,
        activeSessions: prev.activeSessions + (newEvent.type === "scan" ? 1 : 0),
        detectedThreats: prev.detectedThreats + (newEvent.severity !== "low" ? 1 : 0),
        avgResponseTime:
          typeof newEvent.details?.responseTime === "number"
            ? (newEvent.details.responseTime as number)
            : prev.avgResponseTime,
      }));
    };

    ws.onopen = () => setConnectionState("open");

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data as string) as {
          type?: string;
          data?: Record<string, unknown>;
          message?: string;
        };
        if (msg.type === "attack_event") {
          const parsed = parseAttackEvent(msg.data ?? {});
          if (parsed) pushEvent(parsed);
        } else if (msg.type === "connection" && msg.message) {
          const parsed = parseAttackEvent({
            id: `conn-${Date.now()}`,
            type: "detection",
            severity: "low",
            source: "orchestrator",
            target: engagementId,
            description: msg.message,
          });
          if (parsed) pushEvent(parsed);
        }
      } catch {
        // ignore malformed frames
      }
    };

    ws.onerror = () => setConnectionState("closed");
    ws.onclose = () => setConnectionState("closed");

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [engagementId]);

  

  const filteredEvents = selectedSeverity === "all" 
    ? events 
    : events.filter(e => e.severity === selectedSeverity);

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case "critical": return "bg-red-600 border-red-400";
      case "high": return "bg-orange-600 border-orange-400";
      case "medium": return "bg-yellow-600 border-yellow-400";
      case "low": return "bg-blue-600 border-blue-400";
      default: return "bg-gray-600 border-gray-400";
    }
  };

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case "critical": return "🔴";
      case "high": return "🟠";
      case "medium": return "🟡";
      case "low": return "🔵";
      default: return "⚪";
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-cyan-400">Real-Time Attack Monitor</h2>
          <p className="text-slate-400">Live attack detection and monitoring</p>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className={`w-3 h-3 rounded-full ${isLive ? "bg-green-500 animate-pulse" : "bg-gray-500"}`} />
            <span className="text-sm text-slate-300">
              {isLive ? "Live" : "Paused"}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <div className={`w-3 h-3 rounded-full ${
              connectionState === "open" ? "bg-green-500" :
              connectionState === "connecting" ? "bg-yellow-500 animate-pulse" :
              "bg-red-500"
            }`} />
            <span className="text-sm text-slate-300">
              {connectionState === "open" ? "Connected" :
               connectionState === "connecting" ? "Connecting..." :
               "Disconnected"}
            </span>
          </div>
          <button
            onClick={() => setIsLive(!isLive)}
            className="bg-slate-700 hover:bg-slate-600 text-white px-4 py-2 rounded-lg text-sm transition-colors"
          >
            {isLive ? "Pause" : "Resume"}
          </button>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
          <p className="text-sm text-slate-400">Total Attacks</p>
          <p className="text-2xl font-bold text-white">{stats.totalAttacks}</p>
        </div>
        <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
          <p className="text-sm text-slate-400">Active Sessions</p>
          <p className="text-2xl font-bold text-cyan-400">{stats.activeSessions}</p>
        </div>
        <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
          <p className="text-sm text-slate-400">Detected Threats</p>
          <p className="text-2xl font-bold text-orange-400">{stats.detectedThreats}</p>
        </div>
        <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
          <p className="text-sm text-slate-400">Blocked Attacks</p>
          <p className="text-2xl font-bold text-green-400">{stats.blockedAttacks}</p>
        </div>
        <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
          <p className="text-sm text-slate-400">Avg Response Time</p>
          <p className="text-2xl font-bold text-purple-400">{stats.avgResponseTime}ms</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <label className="text-sm text-slate-400">Filter by severity:</label>
        <select
          value={selectedSeverity}
          onChange={(e) => setSelectedSeverity(e.target.value)}
          className="bg-slate-900 border border-slate-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-cyan-500"
        >
          <option value="all">All Severities</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
      </div>

      {/* Attack Events Feed */}
      <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
        <h3 className="text-lg font-semibold text-slate-200 mb-4">Attack Events Feed</h3>
        <div className="space-y-3 max-h-[600px] overflow-y-auto">
          {!engagementId ? (
            <div className="text-center text-slate-500 py-8">
              Select an engagement to stream live scan and execution events
            </div>
          ) : filteredEvents.length === 0 ? (
            <div className="text-center text-slate-500 py-8">
              No attack events yet — start a scan or chain execution
            </div>
          ) : (
            filteredEvents.map((event) => (
              <div
                key={event.id}
                className={`border-l-4 ${getSeverityColor(event.severity)} bg-slate-900/50 rounded-r-lg p-3 hover:bg-slate-900 transition-colors`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-lg">{getSeverityIcon(event.severity)}</span>
                      <span className="font-medium text-white">{event.type.toUpperCase()}</span>
                      <span className="text-slate-400">•</span>
                      <span className="text-slate-400">{event.source}</span>
                    </div>
                    <p className="text-sm text-slate-300">{event.description}</p>
                    <div className="flex items-center gap-4 mt-2 text-xs text-slate-500">
                      <span>Target: {event.target}</span>
                      <span>Port: {event.details?.port}</span>
                      <span>Protocol: {event.details?.protocol}</span>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-xs text-slate-400">
                      {new Date(event.timestamp).toLocaleTimeString()}
                    </p>
                    <span className={`text-xs px-2 py-1 rounded ${
                      event.severity === "critical" ? "bg-red-900 text-red-200" :
                      event.severity === "high" ? "bg-orange-900 text-orange-200" :
                      event.severity === "medium" ? "bg-yellow-900 text-yellow-200" :
                      "bg-blue-900 text-blue-200"
                    }`}>
                      {event.severity}
                    </span>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}