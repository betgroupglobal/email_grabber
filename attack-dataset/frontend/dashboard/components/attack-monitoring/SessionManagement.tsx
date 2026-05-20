"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";

interface Session {
  sessionId: string;
  target: string;
  status: "active" | "paused" | "completed" | "failed";
  iterations: number;
  totalFeedbackLoops: number;
  averageAdaptationImprovement: number;
  successRate: number;
  detectionRate: number;
  createdAt: number;
  lastUpdated: number;
  context: {
    os?: string;
    services?: string[];
    attackTypes?: string[];
  };
}

interface CreateSessionDialog {
  isOpen: boolean;
  target: string;
  context: string;
}

export default function SessionManagement() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selectedSession, setSelectedSession] = useState<Session | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [filter, setFilter] = useState<"all" | "active" | "completed" | "failed">("all");
  const [createDialog, setCreateDialog] = useState<CreateSessionDialog>({
    isOpen: false,
    target: "",
    context: ""
  });

  useEffect(() => {
    loadSessions();
  }, []);

  const loadSessions = async () => {
    setIsLoading(true);
    try {
      // TODO: Replace with actual API call
      // const response = await fetch('/api/sessions');
      // const data = await response.json();
      // setSessions(data);
      
      // For now, set empty sessions until API is implemented
      setSessions([]);
    } catch (error) {
      console.error('Failed to load sessions:', error);
      setSessions([]);
    } finally {
      setIsLoading(false);
    }
  };

  const filteredSessions = sessions.filter(session => {
    if (filter === "all") return true;
    return session.status === filter;
  });

  const handleCreateSession = async () => {
    if (!createDialog.target.trim()) return;
    
    const newSession: Session = {
      sessionId: `session_${Date.now()}`,
      target: createDialog.target,
      status: "active",
      iterations: 0,
      totalFeedbackLoops: 0,
      averageAdaptationImprovement: 0,
      successRate: 0,
      detectionRate: 0,
      createdAt: Date.now(),
      lastUpdated: Date.now(),
      context: {
        attackTypes: []
      }
    };
    
    setSessions([newSession, ...sessions]);
    setCreateDialog({ isOpen: false, target: "", context: "" });
  };

  const handlePauseSession = (sessionId: string) => {
    setSessions(sessions.map(s => 
      s.sessionId === sessionId ? { ...s, status: "paused" as const } : s
    ));
  };

  const handleResumeSession = (sessionId: string) => {
    setSessions(sessions.map(s => 
      s.sessionId === sessionId ? { ...s, status: "active" as const } : s
    ));
  };

  const handleDeleteSession = (sessionId: string) => {
    setSessions(sessions.filter(s => s.sessionId !== sessionId));
    if (selectedSession?.sessionId === sessionId) {
      setSelectedSession(null);
    }
  };

  const getStatusBadge = (status: Session["status"]) => {
    const styles = {
      active: "bg-green-900/30 text-green-400 border-green-700",
      paused: "bg-yellow-900/30 text-yellow-400 border-yellow-700",
      completed: "bg-blue-900/30 text-blue-400 border-blue-700",
      failed: "bg-red-900/30 text-red-400 border-red-700"
    };
    
    return (
      <span className={`px-2 py-1 rounded text-xs font-medium border ${styles[status]}`}>
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </span>
    );
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-cyan-400 mx-auto mb-4"></div>
          <p className="text-slate-400">Loading sessions...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">Session Management</h2>
          <p className="text-slate-400 text-sm mt-1">Manage feedback loop sessions and track attack adaptation</p>
        </div>
        <Button
          onClick={() => setCreateDialog({ ...createDialog, isOpen: true })}
          className="bg-cyan-600 hover:bg-cyan-700 text-white"
        >
          + Create Session
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
          <div className="text-sm text-slate-400 mb-1">Total Sessions</div>
          <div className="text-2xl font-bold text-white">{sessions.length}</div>
        </div>
        <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
          <div className="text-sm text-slate-400 mb-1">Active</div>
          <div className="text-2xl font-bold text-green-400">
            {sessions.filter(s => s.status === "active").length}
          </div>
        </div>
        <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
          <div className="text-sm text-slate-400 mb-1">Completed</div>
          <div className="text-2xl font-bold text-blue-400">
            {sessions.filter(s => s.status === "completed").length}
          </div>
        </div>
        <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
          <div className="text-sm text-slate-400 mb-1">Failed</div>
          <div className="text-2xl font-bold text-red-400">
            {sessions.filter(s => s.status === "failed").length}
          </div>
        </div>
      </div>

      {/* Filter */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-slate-400">Filter:</span>
        {(["all", "active", "completed", "failed"] as const).map((f) => (
          <Button
            key={f}
            onClick={() => setFilter(f)}
            variant={filter === f ? "default" : "outline"}
            size="sm"
            className={filter === f ? "bg-cyan-600 hover:bg-cyan-700" : ""}
          >
            {f.charAt(0).toUpperCase() + f.slice(1)}
          </Button>
        ))}
      </div>

      {/* Sessions List */}
      <div className="bg-slate-800/50 rounded-lg border border-slate-700">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-700">
                <th className="text-left py-3 px-4 text-sm font-medium text-slate-400">Session ID</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-slate-400">Target</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-slate-400">Status</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-slate-400">Iterations</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-slate-400">Feedback Loops</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-slate-400">Adaptation</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-slate-400">Success Rate</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-slate-400">Last Updated</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-slate-400">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredSessions.map((session) => (
                <tr 
                  key={session.sessionId}
                  onClick={() => setSelectedSession(session)}
                  className={`border-b border-slate-700 cursor-pointer transition-colors ${
                    selectedSession?.sessionId === session.sessionId ? 'bg-cyan-900/20' : 'hover:bg-slate-700/30'
                  }`}
                >
                  <td className="py-3 px-4 text-sm text-cyan-400 font-mono">{session.sessionId}</td>
                  <td className="py-3 px-4 text-sm text-white">{session.target}</td>
                  <td className="py-3 px-4">{getStatusBadge(session.status)}</td>
                  <td className="py-3 px-4 text-sm text-white">{session.iterations}</td>
                  <td className="py-3 px-4 text-sm text-white">{session.totalFeedbackLoops}</td>
                  <td className="py-3 px-4 text-sm text-green-400">
                    {(session.averageAdaptationImprovement * 100).toFixed(1)}%
                  </td>
                  <td className="py-3 px-4 text-sm text-cyan-400">
                    {(session.successRate * 100).toFixed(1)}%
                  </td>
                  <td className="py-3 px-4 text-sm text-slate-400">
                    {new Date(session.lastUpdated).toLocaleString()}
                  </td>
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-2">
                      {session.status === "active" && (
                        <Button
                          onClick={(e) => { e.stopPropagation(); handlePauseSession(session.sessionId); }}
                          variant="outline"
                          size="sm"
                        >
                          Pause
                        </Button>
                      )}
                      {session.status === "paused" && (
                        <Button
                          onClick={(e) => { e.stopPropagation(); handleResumeSession(session.sessionId); }}
                          variant="outline"
                          size="sm"
                        >
                          Resume
                        </Button>
                      )}
                      <Button
                        onClick={(e) => { e.stopPropagation(); handleDeleteSession(session.sessionId); }}
                        variant="outline"
                        size="sm"
                        className="text-red-400 hover:text-red-300"
                      >
                        Delete
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Selected Session Details */}
      {selectedSession && (
        <div className="bg-slate-800/50 rounded-lg p-6 border border-slate-700">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-white">
              Session Details: {selectedSession.sessionId}
            </h3>
            <Button
              onClick={() => setSelectedSession(null)}
              variant="outline"
              size="sm"
            >
              Close
            </Button>
          </div>
          
          <div className="grid grid-cols-2 gap-6">
            <div className="space-y-4">
              <div>
                <div className="text-sm text-slate-400 mb-1">Target</div>
                <div className="text-white font-medium">{selectedSession.target}</div>
              </div>
              <div>
                <div className="text-sm text-slate-400 mb-1">Status</div>
                <div>{getStatusBadge(selectedSession.status)}</div>
              </div>
              <div>
                <div className="text-sm text-slate-400 mb-1">Created</div>
                <div className="text-white">{new Date(selectedSession.createdAt).toLocaleString()}</div>
              </div>
              <div>
                <div className="text-sm text-slate-400 mb-1">Last Updated</div>
                <div className="text-white">{new Date(selectedSession.lastUpdated).toLocaleString()}</div>
              </div>
            </div>
            
            <div className="space-y-4">
              <div>
                <div className="text-sm text-slate-400 mb-1">Iterations</div>
                <div className="text-white font-medium">{selectedSession.iterations}</div>
              </div>
              <div>
                <div className="text-sm text-slate-400 mb-1">Feedback Loops</div>
                <div className="text-white font-medium">{selectedSession.totalFeedbackLoops}</div>
              </div>
              <div>
                <div className="text-sm text-slate-400 mb-1">Average Adaptation</div>
                <div className="text-green-400 font-medium">
                  {(selectedSession.averageAdaptationImprovement * 100).toFixed(1)}%
                </div>
              </div>
              <div>
                <div className="text-sm text-slate-400 mb-1">Success Rate</div>
                <div className="text-cyan-400 font-medium">
                  {(selectedSession.successRate * 100).toFixed(1)}%
                </div>
              </div>
            </div>
          </div>
          
          {selectedSession.context && (
            <div className="mt-6 pt-6 border-t border-slate-700">
              <div className="text-sm text-slate-400 mb-3">Context</div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {selectedSession.context.os && (
                  <div>
                    <div className="text-xs text-slate-500 mb-1">Operating System</div>
                    <div className="text-sm text-white">{selectedSession.context.os}</div>
                  </div>
                )}
                {selectedSession.context.services && selectedSession.context.services.length > 0 && (
                  <div>
                    <div className="text-xs text-slate-500 mb-1">Services</div>
                    <div className="flex flex-wrap gap-2">
                      {selectedSession.context.services.map((service, idx) => (
                        <span key={idx} className="px-2 py-1 bg-slate-700 rounded text-xs text-white">
                          {service}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {selectedSession.context.attackTypes && selectedSession.context.attackTypes.length > 0 && (
                  <div className="md:col-span-2">
                    <div className="text-xs text-slate-500 mb-1">Attack Types</div>
                    <div className="flex flex-wrap gap-2">
                      {selectedSession.context.attackTypes.map((type, idx) => (
                        <span key={idx} className="px-2 py-1 bg-cyan-900/30 text-cyan-400 border border-cyan-700 rounded text-xs">
                          {type}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Create Session Dialog */}
      {createDialog.isOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold text-white mb-4">Create New Session</h3>
            <div className="space-y-4">
              <div>
                <label className="text-sm text-slate-400 mb-1 block">Target</label>
                <input
                  type="text"
                  value={createDialog.target}
                  onChange={(e) => setCreateDialog({ ...createDialog, target: e.target.value })}
                  className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-white focus:outline-none focus:border-cyan-500"
                  placeholder="e.g., web-server-01.example.com"
                />
              </div>
              <div>
                <label className="text-sm text-slate-400 mb-1 block">Context (optional)</label>
                <textarea
                  value={createDialog.context}
                  onChange={(e) => setCreateDialog({ ...createDialog, context: e.target.value })}
                  className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-white focus:outline-none focus:border-cyan-500 h-24"
                  placeholder="Additional context about the target..."
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-6">
              <Button
                onClick={() => setCreateDialog({ isOpen: false, target: "", context: "" })}
                variant="outline"
              >
                Cancel
              </Button>
              <Button
                onClick={handleCreateSession}
                className="bg-cyan-600 hover:bg-cyan-700"
              >
                Create
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}