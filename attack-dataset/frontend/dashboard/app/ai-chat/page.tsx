"use client";

import { Suspense, useState, useEffect, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { orchestratorFetchInit, orchestratorHttp } from "@/lib/config";

export default function AIChat() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[40vh] items-center justify-center text-slate-500">
          Loading AI Assistant…
        </div>
      }
    >
      <AIChatContent />
    </Suspense>
  );
}

interface ToolUsedChip {
  plugin?: string;
  tool?: string;
  success?: boolean;
}

interface Message {
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string;
  ai_source?: string;
  latency_ms?: number;
  tools_used?: ToolUsedChip[];
  rounds?: number;
}

interface AIStatus {
  available: boolean;
  model: string;
  provider?: string;
  powered_by?: string;
  jailbreak_api_configured?: boolean;
  unavailable_reason?: string | null;
  rate_limit?: {
    remaining: number;
    reset_at: string;
  };
}

function formatChatError(error: unknown, response?: Response): string {
  if (response?.status === 503) {
    return "AI unavailable — set JAILBREAK_API_KEY on integration-hub and restart the stack.";
  }
  if (response?.status === 504) {
    return "AI request timed out. Try a shorter question or retry in a moment.";
  }
  if (error instanceof TypeError) {
    return "Cannot reach the orchestrator. Check that it is running and NEXT_PUBLIC_ORCHESTRATOR_URL points to http://localhost:3001 (or your host).";
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return "Error communicating with AI service.";
}

function AIChatContent() {
  const searchParams = useSearchParams();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [aiStatus, setAIStatus] = useState<AIStatus | null>(null);
  const [engagementId, setEngagementId] = useState("");
  const [chainIndex, setChainIndex] = useState("");
  const [analysisMode, setAnalysisMode] = useState<"chat" | "engagement" | "chain">("chat");
  const [useTools, setUseTools] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const prompt = searchParams.get("prompt");
    const engagement = searchParams.get("engagement");
    const mode = searchParams.get("mode");
    if (prompt) setInput(prompt);
    if (engagement) setEngagementId(engagement);
    if (mode === "engagement") setAnalysisMode("engagement");
    else if (mode === "chain") setAnalysisMode("chain");
  }, [searchParams]);

  useEffect(() => {
    checkAIStatus();
    const interval = setInterval(checkAIStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const checkAIStatus = async () => {
    try {
      const response = await fetch(orchestratorHttp("/ai/status"), orchestratorFetchInit());
      if (response.ok) {
        const data = await response.json();
        setAIStatus(data);
      }
    } catch (error) {
      console.error("Failed to check AI status:", error);
    }
  };

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      role: "user",
      content: input.trim(),
      timestamp: new Date().toISOString()
    };

    setMessages(prev => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    if (analysisMode === "chat" && aiStatus && !aiStatus.available) {
      const reason = aiStatus.unavailable_reason
        || "Jailbreak AI is not available. Set JAILBREAK_API_KEY on integration-hub.";
      setMessages(prev => [...prev, {
        role: "system",
        content: reason,
        timestamp: new Date().toISOString(),
      }]);
      setIsLoading(false);
      return;
    }

    try {
      let endpoint = "/ai/chat";
      let body: Record<string, unknown> = {
        messages: [...messages, userMessage].map(m => ({
          role: m.role,
          content: m.content
        })),
        stream: false,
        use_rag: true,
        allow_tools: useTools,
      };

      if (analysisMode === "engagement" && engagementId) {
        endpoint = "/ai/analyse/engagement";
        body = {
          engagement_id: engagementId,
          context: input.trim()
        };
      } else if (analysisMode === "chain" && engagementId && chainIndex) {
        endpoint = "/ai/analyse/chain";
        body = {
          engagement_id: engagementId,
          chain_index: parseInt(chainIndex),
          context: input.trim()
        };
      }

      const response = await fetch(orchestratorHttp(endpoint), orchestratorFetchInit({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      }));

      if (response.ok) {
        if (analysisMode === "chat") {
          const contentType = response.headers.get("content-type") || "";
          if (contentType.includes("application/json")) {
            const data = await response.json();
            const text = data.answer || data.response || data.content || data.error || "No response";
            setMessages(prev => [...prev, {
              role: "assistant",
              content: text,
              timestamp: new Date().toISOString(),
              ai_source: data.ai_source || data.source,
              latency_ms: data.latency_ms,
              tools_used: Array.isArray(data.tools_used) ? data.tools_used : undefined,
              rounds: typeof data.rounds === "number" ? data.rounds : undefined,
            }]);
          } else {
            const reader = response.body?.getReader();
            const decoder = new TextDecoder();
            let assistantMessage = "";

            if (reader) {
              while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value);
                const lines = chunk.split("\n");

                for (const line of lines) {
                  if (!line.startsWith("data: ")) continue;
                  const data = line.slice(6).trim();
                  if (data === "[DONE]") continue;

                  try {
                    const parsed = JSON.parse(data);
                    const piece = parsed.content ?? parsed.delta ?? parsed.text ?? "";
                    if (piece) {
                      assistantMessage += piece;
                      setMessages((prev) => {
                        const newMessages = [...prev];
                        const lastMessage = newMessages[newMessages.length - 1];
                        if (lastMessage?.role === "assistant") {
                          lastMessage.content = assistantMessage;
                        } else {
                          newMessages.push({
                            role: "assistant",
                            content: assistantMessage,
                            timestamp: new Date().toISOString(),
                          });
                        }
                        return newMessages;
                      });
                    }
                  } catch {
                    if (data && data !== "[DONE]") {
                      assistantMessage += data;
                    }
                  }
                }
              }
            }
            if (!assistantMessage) {
              setMessages((prev) => [...prev, {
                role: "system",
                content: "AI returned an empty response.",
                timestamp: new Date().toISOString(),
              }]);
            }
          }
        } else {
          // Handle non-streaming response
          const data = await response.json();
          const assistantMessage: Message = {
            role: "assistant",
            content: data.analysis || data.response || "Analysis completed",
            timestamp: new Date().toISOString()
          };
          setMessages(prev => [...prev, assistantMessage]);
        }
      } else {
        const errBody = await response.json().catch(() => ({}));
        const detail = (errBody as { error?: string; detail?: string }).error
          || (errBody as { detail?: string }).detail
          || `HTTP ${response.status}`;
        const errorMessage: Message = {
          role: "system",
          content: `Failed to get AI response: ${detail}`,
          timestamp: new Date().toISOString()
        };
        setMessages(prev => [...prev, errorMessage]);
      }
    } catch (error) {
      const errorMessage: Message = {
        role: "system",
        content: formatChatError(error),
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const clearChat = () => {
    setMessages([]);
  };

  return (
    <div className="min-h-screen bg-[#080c14] text-white">
      {/* Header */}
      <header className="sticky top-0 z-40 border-b border-slate-800/60 bg-[#080c14]/80 backdrop-blur-xl">
        <div className="mx-auto max-w-7xl px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-cyan-400">AI Assistant</h1>
              <p className="text-sm text-slate-500">
                {aiStatus?.available
                  ? "Powered by Jailbreak AI · RAG-grounded security analysis"
                  : aiStatus?.unavailable_reason
                  ? aiStatus.unavailable_reason
                  : "Security analysis assistant"}
              </p>
            </div>
            <div className="flex items-center gap-4">
              {aiStatus && (
                <div className="flex items-center gap-2">
                  <span className={`w-2 h-2 rounded-full ${
                    aiStatus.available ? "bg-emerald-500" : "bg-red-500"
                  }`} />
                  <span className="text-xs text-slate-400">
                    {aiStatus.available
                      ? (aiStatus.provider || "Jailbreak AI")
                      : "AI Unavailable"}
                  </span>
                  {aiStatus.rate_limit && (
                    <span className="text-xs text-slate-500">
                      ({aiStatus.rate_limit.remaining} requests remaining)
                    </span>
                  )}
                </div>
              )}
              <Button
                onClick={clearChat}
                className="h-8 bg-slate-700 hover:bg-slate-600 text-white px-4 py-2 rounded-lg text-sm"
              >
                Clear Chat
              </Button>
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Sidebar */}
          <div className="lg:col-span-1 space-y-4">
            {/* Analysis Mode */}
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 backdrop-blur-sm">
              <h3 className="text-sm font-medium text-white mb-3">Analysis Mode</h3>
              <div className="space-y-2">
                <button
                  onClick={() => setAnalysisMode("chat")}
                  className={`h-8 w-full text-left px-3 rounded-lg text-xs font-medium ${
                    analysisMode === "chat"
                      ? "bg-cyan-950/30 text-cyan-400 border border-cyan-800"
                      : "bg-slate-950/30 text-slate-400 border border-slate-800 hover:bg-slate-900"
                  }`}
                >
                  General Chat
                </button>
                <button
                  onClick={() => setAnalysisMode("engagement")}
                  className={`h-8 w-full text-left px-3 rounded-lg text-xs font-medium ${
                    analysisMode === "engagement"
                      ? "bg-cyan-950/30 text-cyan-400 border border-cyan-800"
                      : "bg-slate-950/30 text-slate-400 border border-slate-800 hover:bg-slate-900"
                  }`}
                >
                  Engagement Analysis
                </button>
                <button
                  onClick={() => setAnalysisMode("chain")}
                  className={`h-8 w-full text-left px-3 rounded-lg text-xs font-medium ${
                    analysisMode === "chain"
                      ? "bg-cyan-950/30 text-cyan-400 border border-cyan-800"
                      : "bg-slate-950/30 text-slate-400 border border-slate-800 hover:bg-slate-900"
                  }`}
                >
                  Chain Analysis
                </button>
              </div>
            </div>

            {/* Context Input */}
            {(analysisMode === "engagement" || analysisMode === "chain") && (
              <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 backdrop-blur-sm">
                <h3 className="text-sm font-medium text-white mb-3">Context</h3>
                <div className="space-y-3">
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">Engagement ID</label>
                    <input
                      type="text"
                      value={engagementId}
                      onChange={(e) => setEngagementId(e.target.value)}
                      placeholder="Enter engagement ID"
                      className="w-full rounded-lg border border-slate-700 bg-slate-950/50 px-4 py-2.5 text-sm text-white placeholder:text-slate-600 focus:border-cyan-500/50 focus:outline-none focus:ring-1 focus:ring-cyan-500/20"
                    />
                  </div>
                  {analysisMode === "chain" && (
                    <div>
                      <label className="block text-xs text-slate-500 mb-1">Chain Index</label>
                      <input
                        type="number"
                        value={chainIndex}
                        onChange={(e) => setChainIndex(e.target.value)}
                        placeholder="Enter chain index"
                        className="w-full rounded-lg border border-slate-700 bg-slate-950/50 px-4 py-2.5 text-sm text-white placeholder:text-slate-600 focus:border-cyan-500/50 focus:outline-none focus:ring-1 focus:ring-cyan-500/20"
                      />
                    </div>
                  )}
                </div>
              </div>
            )}

            {analysisMode === "chat" && (
              <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 backdrop-blur-sm">
                <label className="flex items-center gap-2 cursor-pointer text-sm text-slate-300">
                  <input
                    type="checkbox"
                    checked={useTools}
                    onChange={(e) => setUseTools(e.target.checked)}
                    className="rounded border-slate-600"
                  />
                  Use tools (nuclei, ffuf, analyzer via Jailbreak agent)
                </label>
                <p className="text-xs text-slate-500 mt-2">
                  When enabled, the assistant may run up to 3 tool rounds before answering.
                </p>
              </div>
            )}

            {/* AI Status */}
            {aiStatus && (
              <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 backdrop-blur-sm">
                <h3 className="text-sm font-medium text-white mb-3">AI Status</h3>
                <div className="space-y-2 text-xs">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Status</span>
                    <span className={aiStatus.available ? "text-emerald-400" : "text-red-400"}>
                      {aiStatus.available ? "Available" : "Unavailable"}
                    </span>
                  </div>
                  {aiStatus.provider && (
                    <div className="flex justify-between">
                      <span className="text-slate-500">Provider</span>
                      <span className="text-slate-300">{aiStatus.provider}</span>
                    </div>
                  )}
                  {aiStatus.model && (
                    <div className="flex justify-between">
                      <span className="text-slate-500">Model</span>
                      <span className="text-slate-300">{aiStatus.model}</span>
                    </div>
                  )}
                  {aiStatus.rate_limit && (
                    <div className="flex justify-between">
                      <span className="text-slate-500">Rate Limit</span>
                      <span className="text-slate-300">{aiStatus.rate_limit.remaining} remaining</span>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Chat Area */}
          <div className="lg:col-span-3 rounded-xl border border-slate-800 bg-slate-900/60 flex flex-col h-[600px] backdrop-blur-sm">
            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.length === 0 && (
                <div className="rounded-xl border border-dashed border-slate-800 py-16 text-center">
                  <p className="text-sm text-slate-400">Start a conversation with the AI assistant</p>
                  <p className="text-xs text-slate-500 mt-2">Ask about attack patterns, security concepts, or analysis</p>
                </div>
              )}

              {messages.map((message, idx) => (
                <div
                  key={idx}
                  className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[80%] rounded-lg p-3 ${
                      message.role === "user"
                        ? "bg-cyan-950/30 border border-cyan-800"
                        : message.role === "system"
                        ? "bg-amber-950/30 border border-amber-800"
                        : "rounded-lg border border-slate-800 bg-slate-950/30"
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <span className="text-xs font-medium text-slate-300">
                        {message.role === "user" ? "You" : 
                         message.role === "system" ? "System" : "AI"}
                      </span>
                      <span className="text-xs text-slate-500">
                        {new Date(message.timestamp).toLocaleTimeString()}
                      </span>
                      {message.role === "assistant" && message.ai_source && (
                        <span className="text-[10px] uppercase tracking-wide text-cyan-500/80">
                          {message.ai_source}
                          {message.latency_ms != null ? ` · ${message.latency_ms}ms` : ""}
                        </span>
                      )}
                    </div>
                    <p className="text-sm whitespace-pre-wrap text-slate-300">{message.content}</p>
                    {message.role === "assistant" && message.tools_used && message.tools_used.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {message.tools_used.map((t, i) => (
                          <span
                            key={i}
                            className={`inline-flex items-center rounded px-2 py-0.5 text-[10px] font-medium ${
                              t.success === false
                                ? "bg-amber-950/50 text-amber-300 border border-amber-800"
                                : "bg-emerald-950/40 text-emerald-300 border border-emerald-800"
                            }`}
                          >
                            {t.plugin || "tool"}
                            {t.tool ? `/${t.tool}` : ""}
                          </span>
                        ))}
                        {message.rounds != null && message.rounds > 0 && (
                          <span className="text-[10px] text-slate-500 self-center">
                            {message.rounds} round{message.rounds === 1 ? "" : "s"}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {isLoading && (
                <div className="flex justify-start">
                  <div className="rounded-lg border border-slate-800 bg-slate-950/30 p-3">
                    <div className="flex items-center gap-2">
                      <div className="h-4 w-4 animate-spin rounded-full border-2 border-slate-700 border-t-cyan-500" />
                      <span className="text-sm text-slate-400">AI is thinking...</span>
                    </div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div className="border-t border-slate-800 p-4">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyPress={(e) => e.key === "Enter" && sendMessage()}
                  placeholder={
                    analysisMode === "chat"
                      ? "Ask about security topics, attack patterns, or analysis..."
                      : analysisMode === "engagement"
                      ? "Ask about engagement analysis..."
                      : "Ask about chain analysis..."
                  }
                  disabled={isLoading}
                  className="flex-1 rounded-lg border border-slate-700 bg-slate-950/50 px-4 py-2.5 text-sm text-white placeholder:text-slate-600 focus:border-cyan-500/50 focus:outline-none focus:ring-1 focus:ring-cyan-500/20"
                />
                <Button
                  onClick={sendMessage}
                  disabled={!input.trim() || isLoading}
                  className="h-9 bg-cyan-600 hover:bg-cyan-700 text-white px-6 py-3 rounded-lg"
                >
                  {isLoading ? "..." : "Send"}
                </Button>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
