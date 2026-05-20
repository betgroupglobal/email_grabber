"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  Clock,
  Copy,
  Download,
  Pause,
  Play,
  Search,
  Wifi,
  WifiOff,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { orchestratorWs } from "@/lib/config";
import { fetchTerminalHistory } from "@/lib/orchestratorClient";
import type { CouncilWsEvent, ReasoningTraceEntry } from "@/lib/liveCouncil";
import { cn } from "@/lib/utils";

const LONG_LINE_THRESHOLD = 280;
const SCROLL_PAUSE_THRESHOLD = 48;

export interface SystemFeedLine {
  key: string;
  content: string;
  type?: LineType;
  timestamp?: string;
}

export interface TerminalOutputProps {
  engagementId: string;
  isActive: boolean;
  className?: string;
  /** Fill parent height instead of fixed 384px */
  fillHeight?: boolean;
  /** Dense typography for unified operations view */
  compact?: boolean;
  councilEvents?: CouncilWsEvent[];
  reasoningTrace?: ReasoningTraceEntry[];
  /** MITRE, chain status, and other orchestration feed lines */
  systemLines?: SystemFeedLine[];
}

type LineType =
  | "info"
  | "success"
  | "error"
  | "warning"
  | "command"
  | "output"
  | "council"
  | "think"
  | "hub"
  | "jailbreak"
  | "scan"
  | "chain"
  | "mitre"
  | "opsec"
  | "pathway"
  | "tool";

type FilterCategory =
  | "all"
  | "scan"
  | "mitre"
  | "hub"
  | "msf"
  | "burp"
  | "mcp"
  | "chain"
  | "council"
  | "think"
  | "jailbreak"
  | "pathway"
  | "tool"
  | "errors";

interface TerminalLine {
  id: string;
  timestamp: string;
  type: LineType;
  content: string;
  command?: string;
  duration?: number;
  category: FilterCategory | "general";
  councilBadge?: {
    kind: "turn" | "memo" | "directive" | "reasoning";
    turn?: number;
    agent?: string;
    action?: string;
  };
  source?: "ws" | "council" | "reasoning";
}

const FILTER_OPTIONS: { value: FilterCategory; label: string }[] = [
  { value: "all", label: "All" },
  { value: "scan", label: "Scan" },
  { value: "mitre", label: "Mitre" },
  { value: "hub", label: "Hub" },
  { value: "msf", label: "MSF" },
  { value: "burp", label: "Burp" },
  { value: "mcp", label: "MCP" },
  { value: "tool", label: "Tool" },
  { value: "chain", label: "Chain" },
  { value: "council", label: "Council" },
  { value: "think", label: "Think" },
  { value: "jailbreak", label: "JB" },
  { value: "pathway", label: "Path" },
  { value: "errors", label: "Err" },
];

function prefixCategory(content: string): FilterCategory | "general" | null {
  const match = content.match(/^\[(\w+)\]/i);
  if (!match) return null;
  const tag = match[1].toLowerCase();
  if (tag === "scan") return "scan";
  if (tag === "mitre") return "mitre";
  if (tag === "hub") return "hub";
  if (tag === "chain") return "chain";
  if (tag === "council") return "council";
  if (tag === "opsec") return "general";
  if (tag === "pathway") return "pathway";
  if (tag === "msf") return "tool";
  if (tag === "burp") return "burp";
  if (tag === "mcp") return "mcp";
  if (tag === "nuclei" || tag === "ffuf" || tag === "sqlmap") return "tool";
  if (tag === "tool") return "tool";
  if (tag === "think") return "think";
  return null;
}

function inferCategory(type: string, content: string): FilterCategory | "general" {
  const prefixed = prefixCategory(content);
  if (prefixed) return prefixed;

  const lower = content.toLowerCase();
  if (type === "error" || type === "warning") return "errors";
  if (
    lower.includes("[council]") ||
    lower.includes("live council") ||
    lower.includes("directive:") ||
    lower.includes("council turn") ||
    content.includes("🧠")
  ) {
    return "council";
  }
  if (lower.includes("[scan]") || lower.includes("nmap") || lower.includes("analyzer")) {
    return "scan";
  }
  if (lower.includes("[mitre]")) return "mitre";
  if (lower.includes("[chain]")) return "chain";
  if (lower.includes("[msf]") || lower.includes("msfconsole") || lower.includes("msfvenom")) {
    return "msf";
  }
  if (lower.includes("[burp]")) return "burp";
  if (lower.includes("[mcp]")) return "mcp";
  if (lower.includes("[tool]")) return "tool";
  if (lower.includes("[hub]") || lower.includes("hub") || content.includes("📤")) return "hub";
  if (lower.includes("[opsec]")) return "general";
  if (
    lower.includes("jailbreak") ||
    content.includes("🤖") ||
    lower.includes("jailbreak ai")
  ) {
    return "jailbreak";
  }
  if (lower.includes("[pathway]")) return "pathway";
  if (
    lower.includes("[tool]") ||
    lower.includes("[nuclei]") ||
    lower.includes("[ffuf]") ||
    lower.includes("[sqlmap]") ||
    lower.includes("[msf]") ||
    lower.includes("[burp]") ||
    lower.includes("[mcp]")
  ) {
    return "tool";
  }
  if (lower.includes("[think]")) return "think";
  return "general";
}

function normalizeLineType(raw: string, content: string): LineType {
  const prefixed = prefixCategory(content);
  if (prefixed === "scan") return "scan";
  if (prefixed === "mitre") return "mitre";
  if (prefixed === "chain") return "chain";
  if (prefixed === "council") return "council";
  if (prefixed === "hub") return "hub";
  if (prefixed === "pathway") return "pathway";
  if (prefixed === "tool") return "tool";
  if (prefixed === "think") return "think";
  if (content.toLowerCase().startsWith("[opsec]")) return "opsec";

  const category = inferCategory(raw, content);
  if (category === "council") return "council";
  if (category === "hub") return "hub";
  if (category === "jailbreak") return "jailbreak";
  if (category === "scan") return "scan";
  if (category === "mitre") return "mitre";
  if (category === "chain") return "chain";
  if (category === "msf") return "output";
  if (category === "tool") return "tool";
  if (category === "think") return "think";
  if (
    raw === "info" ||
    raw === "success" ||
    raw === "error" ||
    raw === "warning" ||
    raw === "command" ||
    raw === "output"
  ) {
    return raw;
  }
  return "info";
}

function lineMatchesFilter(line: TerminalLine, filter: FilterCategory): boolean {
  if (filter === "all") return true;
  if (filter === "errors") return line.type === "error" || line.type === "warning";
  return line.category === filter || line.type === filter;
}

function formatLineForExport(line: TerminalLine, showTimestamps: boolean): string {
  const ts = showTimestamps ? `[${new Date(line.timestamp).toISOString()}] ` : "";
  const badge = line.councilBadge
    ? `[${line.councilBadge.kind}${line.councilBadge.turn != null ? `#${line.councilBadge.turn}` : ""}] `
    : "";
  const cmd = line.command ? `$ ${line.command}\n` : "";
  return `${ts}${badge}[${line.type.toUpperCase()}] ${cmd}${line.content}`;
}

function councilEventToLine(event: CouncilWsEvent, id: string): TerminalLine | null {
  const timestamp = event.timestamp || new Date().toISOString();
  if (event.type === "reasoning_thought") {
    const line = reasoningToLine(event.thought, id);
    return line;
  }
  if (event.type === "council_turn_started") {
    return {
      id,
      timestamp,
      type: "council",
      category: "council",
      source: "council",
      content: `[council] Turn ${event.turn} started${event.trigger ? ` · ${event.trigger}` : ""}`,
      councilBadge: { kind: "turn", turn: event.turn },
    };
  }
  if (event.type === "council_agent_memo") {
    const summary =
      typeof event.memo?.summary === "string"
        ? event.memo.summary
        : typeof event.memo?.recommendation === "string"
          ? event.memo.recommendation
          : JSON.stringify(event.memo).slice(0, 200);
    return {
      id,
      timestamp,
      type: "council",
      category: "council",
      source: "council",
      content: `[council] ${event.agent}: ${summary}`,
      councilBadge: { kind: "memo", turn: event.turn, agent: event.agent },
    };
  }
  if (event.type === "live_directive" || event.type === "approval_required") {
    const d = event.directive;
    return {
      id,
      timestamp,
      type: "council",
      category: "council",
      source: "council",
      content: `[council] Directive · ${d.action}${d.rationale ? `: ${d.rationale.slice(0, 240)}` : ""}`,
      councilBadge: { kind: "directive", turn: d.turn, action: d.action },
    };
  }
  return null;
}

function reasoningToLine(entry: ReasoningTraceEntry, id: string): TerminalLine | null {
  const ts = entry.ts || new Date().toISOString();
  const stage =
    typeof entry.stage === "string"
      ? entry.stage
      : typeof entry.pattern_step === "string"
        ? String(entry.pattern_step)
        : "Reasoning";
  const rationale = entry.rationale
    ? String(entry.rationale).slice(0, 240)
    : entry.narrative
      ? String(entry.narrative).slice(0, 240)
      : entry.note
        ? String(entry.note).slice(0, 240)
        : "";
  const subtaskId =
    typeof entry.subtask_id === "string" ? entry.subtask_id : undefined;
  const text = rationale
    ? subtaskId
      ? `[think] ${stage} · ${subtaskId}${entry.action ? ` · ${entry.action}` : ""} — ${rationale}`
      : `[think] ${stage}${entry.action ? ` · ${entry.action}` : ""} — ${rationale}`
    : subtaskId
      ? `[think] ${stage} · ${subtaskId} — ${entry.source || "reasoning"}`
      : `[think] ${stage}${entry.action ? ` · ${entry.action}` : ""} — ${entry.source || "reasoning"}`;
  if (!text.trim()) return null;
  return {
    id,
    timestamp: ts,
    type: "think",
    category: "think",
    source: "reasoning",
    content: text,
    councilBadge: {
      kind: "reasoning",
      turn: typeof entry.turn === "number" ? entry.turn : undefined,
      action: typeof entry.action === "string" ? entry.action : undefined,
    },
  };
}

const LINE_STYLES: Record<
  LineType,
  { text: string; bg: string; icon: string; label: string }
> = {
  success: {
    text: "text-emerald-400",
    bg: "bg-emerald-950/40 border-l-2 border-emerald-500/80",
    icon: "✓",
    label: "OK",
  },
  error: {
    text: "text-red-400",
    bg: "bg-red-950/40 border-l-2 border-red-500/80",
    icon: "✕",
    label: "ERR",
  },
  warning: {
    text: "text-amber-400",
    bg: "bg-amber-950/35 border-l-2 border-amber-500/70",
    icon: "!",
    label: "WARN",
  },
  command: {
    text: "text-cyan-300",
    bg: "bg-cyan-950/45 border-l-2 border-cyan-400/80",
    icon: "$",
    label: "CMD",
  },
  output: {
    text: "text-slate-300",
    bg: "bg-slate-900/60 border-l-2 border-slate-600/80",
    icon: "›",
    label: "OUT",
  },
  council: {
    text: "text-violet-300",
    bg: "bg-violet-950/40 border-l-2 border-violet-500/80",
    icon: "◈",
    label: "CNL",
  },
  hub: {
    text: "text-sky-300",
    bg: "bg-sky-950/35 border-l-2 border-sky-500/70",
    icon: "⬡",
    label: "HUB",
  },
  jailbreak: {
    text: "text-fuchsia-300",
    bg: "bg-fuchsia-950/35 border-l-2 border-fuchsia-500/70",
    icon: "⚡",
    label: "JB",
  },
  scan: {
    text: "text-teal-300",
    bg: "bg-teal-950/35 border-l-2 border-teal-500/70",
    icon: "◎",
    label: "SCN",
  },
  chain: {
    text: "text-orange-300",
    bg: "bg-orange-950/35 border-l-2 border-orange-500/70",
    icon: "⛓",
    label: "CHN",
  },
  mitre: {
    text: "text-purple-300",
    bg: "bg-purple-950/35 border-l-2 border-purple-500/70",
    icon: "◆",
    label: "MTR",
  },
  opsec: {
    text: "text-emerald-300",
    bg: "bg-emerald-950/35 border-l-2 border-emerald-500/70",
    icon: "🛡",
    label: "OPS",
  },
  pathway: {
    text: "text-cyan-200",
    bg: "bg-cyan-950/30 border-l-2 border-cyan-400/60",
    icon: "↻",
    label: "PATH",
  },
  tool: {
    text: "text-lime-300",
    bg: "bg-lime-950/35 border-l-2 border-lime-500/70",
    icon: "⚙",
    label: "TOL",
  },
  think: {
    text: "text-violet-200",
    bg: "bg-violet-950/30 border-l-2 border-violet-400/60",
    icon: "◇",
    label: "THK",
  },
  info: {
    text: "text-slate-400",
    bg: "bg-transparent border-l-2 border-transparent",
    icon: "·",
    label: "INFO",
  },
};

function CouncilBadge({ badge }: { badge: NonNullable<TerminalLine["councilBadge"]> }) {
  const labels: Record<string, string> = {
    turn: "Turn",
    memo: "Memo",
    directive: "Directive",
    reasoning: "Trace",
  };
  return (
    <span className="inline-flex items-center gap-1 rounded border border-violet-500/40 bg-violet-950/60 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-violet-200">
      {labels[badge.kind]}
      {badge.turn != null && <span className="text-violet-400">#{badge.turn}</span>}
      {badge.agent && <span className="normal-case text-violet-300/90">· {badge.agent}</span>}
      {badge.action && <span className="normal-case text-amber-300/90">· {badge.action}</span>}
    </span>
  );
}

function TerminalLineRow({
  line,
  showTimestamps,
  compact = false,
}: {
  line: TerminalLine;
  showTimestamps: boolean;
  compact?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const style = LINE_STYLES[line.type];
  const isLong = line.content.length > LONG_LINE_THRESHOLD;
  const displayContent =
    isLong && !expanded ? `${line.content.slice(0, LONG_LINE_THRESHOLD)}…` : line.content;

  return (
    <div
      className={cn(
        "group flex gap-1.5 rounded font-mono leading-snug",
        compact ? "px-1.5 py-0.5 text-[10px]" : "gap-2 px-2 py-1.5 text-xs leading-relaxed",
        style.bg,
        style.text
      )}
    >
      {showTimestamps && (
        <span
          className={cn(
            "shrink-0 select-none text-slate-600 tabular-nums",
            compact ? "text-[9px]" : "text-[10px]"
          )}
        >
          {new Date(line.timestamp).toLocaleTimeString()}
        </span>
      )}
      <span
        className="shrink-0 w-8 select-none text-center text-[10px] font-bold opacity-70"
        title={style.label}
      >
        {style.icon}
      </span>
      <div className="min-w-0 flex-1">
        <div className="mb-0.5 flex flex-wrap items-center gap-2">
          {line.councilBadge && <CouncilBadge badge={line.councilBadge} />}
          {line.source === "reasoning" && (
            <span className="rounded bg-slate-800/80 px-1 text-[10px] text-slate-400">reasoning</span>
          )}
        </div>
        {line.command && (
          <div className="mb-1 font-bold text-cyan-200">
            <span className="text-emerald-500/90">$ </span>
            {line.command}
          </div>
        )}
        <pre className="whitespace-pre-wrap break-words font-mono">{displayContent}</pre>
        {isLong && (
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="mt-1 inline-flex items-center gap-0.5 text-[10px] text-slate-500 hover:text-slate-300"
          >
            {expanded ? (
              <>
                <ChevronDown className="size-3" /> Collapse
              </>
            ) : (
              <>
                <ChevronRight className="size-3" /> Show {line.content.length - LONG_LINE_THRESHOLD} more chars
              </>
            )}
          </button>
        )}
      </div>
    </div>
  );
}

export default function TerminalOutput({
  engagementId,
  isActive,
  className,
  fillHeight = false,
  compact = false,
  councilEvents,
  reasoningTrace,
  systemLines,
}: TerminalOutputProps) {
  const [lines, setLines] = useState<TerminalLine[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const [showTimestamps, setShowTimestamps] = useState(true);
  const [filter, setFilter] = useState<FilterCategory>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [copyFeedback, setCopyFeedback] = useState<string | null>(null);

  const terminalRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const lineCounter = useRef(0);
  const seenCouncilIds = useRef(new Set<string>());
  const seenReasoningIds = useRef(new Set<string>());
  const seenSystemKeys = useRef(new Set<string>());

  const addLine = useCallback((line: Omit<TerminalLine, "id">) => {
    lineCounter.current += 1;
    setLines((prev) => [...prev, { ...line, id: `${Date.now()}-${lineCounter.current}` }]);
  }, []);

  useEffect(() => {
    if (!isActive || !engagementId) return;

    let cancelled = false;
    setIsConnected(false);
    seenCouncilIds.current.clear();
    seenReasoningIds.current.clear();
    seenSystemKeys.current.clear();

    let intentionalClose = false;

    const connect = async () => {
      const history = await fetchTerminalHistory(engagementId);
      if (cancelled) return;

      if (history.length > 0) {
        lineCounter.current = history.length;
        setLines(
          history.map((entry, index) => {
            const content = entry.content ?? "";
            const rawType = entry.type || "info";
            const lineType = normalizeLineType(rawType, content);
            const category = inferCategory(rawType, content);
            const isThink =
              content.toLowerCase().startsWith("[think]") || lineType === "think";
            return {
              id: `hist-${index}-${entry.timestamp || index}`,
              timestamp: entry.timestamp || new Date().toISOString(),
              type: isThink ? "think" : lineType,
              category: isThink ? "think" : category,
              content,
              source: "ws" as const,
            };
          })
        );
      } else {
        lineCounter.current = 0;
        setLines([]);
      }

      const wsUrl = `${orchestratorWs(`/terminal/${engagementId}`)}?engagement=${engagementId}`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!cancelled) setIsConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as {
            type?: string;
            content?: string;
            command?: string;
            timestamp?: string;
          };
          const content = data.content ?? event.data;
          const rawType = data.type || "info";
          const lineType = normalizeLineType(rawType, String(content));
          const category = inferCategory(rawType, String(content));
          const isThink =
            String(content).toLowerCase().startsWith("[think]") || lineType === "think";

          addLine({
            timestamp: data.timestamp || new Date().toISOString(),
            type: isThink ? "think" : lineType,
            category: isThink ? "think" : category,
            content: String(content),
            command: data.command,
            source: "ws",
            councilBadge:
              category === "council" && String(content).includes("DIRECTIVE")
                ? { kind: "directive", action: String(content).match(/DIRECTIVE:\s*(\w+)/i)?.[1] }
                : category === "council" && String(content).includes("COUNCIL TURN")
                  ? {
                      kind: "turn",
                      turn: Number(String(content).match(/TURN\s+(\d+)/i)?.[1]) || undefined,
                    }
                  : undefined,
          });
        } catch {
          addLine({
            timestamp: new Date().toISOString(),
            type: "info",
            category: "general",
            content: event.data,
            source: "ws",
          });
        }
      };

      ws.onerror = () => {};

      ws.onclose = () => {
        setIsConnected(false);
        if (!intentionalClose && !cancelled) {
          addLine({
            timestamp: new Date().toISOString(),
            type: "warning",
            category: "errors",
            content: "Terminal disconnected — run continues server-side; reconnecting…",
            source: "ws",
          });
        }
      };
    };

    void connect();

    return () => {
      cancelled = true;
      intentionalClose = true;
      // Intentional: close WS only — never stop server-side execution on unmount.
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      setIsConnected(false);
    };
  }, [engagementId, isActive, addLine]);

  useEffect(() => {
    if (!councilEvents?.length) return;
    for (const event of councilEvents) {
      const key = JSON.stringify(event);
      if (seenCouncilIds.current.has(key)) continue;
      seenCouncilIds.current.add(key);
      const line = councilEventToLine(event, `council-${seenCouncilIds.current.size}`);
      if (line) addLine(line);
    }
  }, [councilEvents, addLine]);

  useEffect(() => {
    if (!reasoningTrace?.length) return;
    const recent = reasoningTrace.slice(-8);
    for (const entry of recent) {
      const key = `${entry.ts}-${entry.source}-${entry.turn}-${entry.action}`;
      if (seenReasoningIds.current.has(key)) continue;
      seenReasoningIds.current.add(key);
      const line = reasoningToLine(entry, `reasoning-${seenReasoningIds.current.size}`);
      if (line) addLine(line);
    }
  }, [reasoningTrace, addLine]);

  useEffect(() => {
    if (!systemLines?.length) return;
    for (const feed of systemLines) {
      if (seenSystemKeys.current.has(feed.key)) continue;
      seenSystemKeys.current.add(feed.key);
      const lineType = feed.type || "info";
      addLine({
        timestamp: feed.timestamp || new Date().toISOString(),
        type: lineType,
        category: lineType === "council" ? "council" : lineType === "hub" ? "hub" : "general",
        content: feed.content,
        source: "ws",
      });
    }
  }, [systemLines, addLine]);

  const filteredLines = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return lines.filter((line) => {
      if (!lineMatchesFilter(line, filter)) return false;
      if (!q) return true;
      const haystack = [line.content, line.command, line.type, line.councilBadge?.agent]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(q);
    });
  }, [lines, filter, searchQuery]);

  const handleScroll = useCallback(() => {
    const el = terminalRef.current;
    if (!el) return;
    const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    setAutoScroll(distFromBottom <= SCROLL_PAUSE_THRESHOLD);
  }, []);

  useEffect(() => {
    if (!autoScroll || !terminalRef.current) return;
    terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
  }, [filteredLines, autoScroll]);

  const exportText = useCallback(() => {
    return filteredLines.map((l) => formatLineForExport(l, showTimestamps)).join("\n");
  }, [filteredLines, showTimestamps]);

  const handleCopy = async () => {
    const text = exportText();
    try {
      await navigator.clipboard.writeText(text);
      setCopyFeedback("Copied");
      setTimeout(() => setCopyFeedback(null), 2000);
    } catch {
      setCopyFeedback("Failed");
      setTimeout(() => setCopyFeedback(null), 2000);
    }
  };

  const handleExport = (format: "txt" | "json" = "txt") => {
    if (format === "json") {
      const payload = {
        engagement_id: engagementId,
        exported_at: new Date().toISOString(),
        line_count: filteredLines.length,
        lines: filteredLines.map((l) => ({
          timestamp: l.timestamp,
          type: l.type,
          category: l.category,
          content: l.content,
          command: l.command,
          source: l.source,
        })),
      };
      const blob = new Blob([JSON.stringify(payload, null, 2)], {
        type: "application/json;charset=utf-8",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `terminal-${engagementId.slice(0, 8)}-${Date.now()}.json`;
      a.click();
      URL.revokeObjectURL(url);
      return;
    }
    const blob = new Blob([exportText()], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `terminal-${engagementId.slice(0, 8)}-${Date.now()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleClearSearch = () => setSearchQuery("");

  if (!isActive) {
    return (
      <div
        className={cn(
          "flex h-64 flex-col rounded-lg border border-slate-700/80 bg-[#0a0e14] p-4",
          className
        )}
      >
        <div className="mb-2 flex items-center gap-2">
          <div className="size-3 rounded-full bg-slate-600" />
          <span className="font-mono text-sm text-slate-400">Jailbreak AI Terminal</span>
        </div>
        <div className="flex flex-1 items-center justify-center text-center text-sm text-slate-500">
          Terminal will activate during attack execution
        </div>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "flex flex-col overflow-hidden rounded-lg border border-slate-700/80 bg-[#0a0e14] shadow-inner",
        fillHeight ? "h-full" : "h-96",
        className
      )}
    >
      {/* Header */}
      <div
        className={cn(
          "flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-slate-800 bg-[#0d1117]",
          compact ? "px-2 py-1" : "px-3 py-2"
        )}
      >
        <div className="flex min-w-0 items-center gap-2">
          <div className="flex gap-1.5">
            <div className="size-2.5 rounded-full bg-red-500/90" />
            <div className="size-2.5 rounded-full bg-amber-500/90" />
            <div className="size-2.5 rounded-full bg-emerald-500/90" />
          </div>
          <span
            className={cn(
              "truncate font-mono text-slate-400",
              compact ? "text-[10px]" : "text-xs"
            )}
          >
            Jailbreak AI Terminal
          </span>
          <span
            className={cn(
              "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium",
              isConnected
                ? "bg-emerald-950/60 text-emerald-400 ring-1 ring-emerald-500/30"
                : "bg-red-950/60 text-red-400 ring-1 ring-red-500/30"
            )}
          >
            {isConnected ? (
              <>
                <Wifi className="size-3" /> Live
              </>
            ) : (
              <>
                <WifiOff className="size-3" /> Offline
              </>
            )}
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          <div className="relative">
            <Search className="pointer-events-none absolute top-1/2 left-2 size-3 -translate-y-1/2 text-slate-500" />
            <input
              type="search"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search…"
              className="h-7 w-28 rounded border border-slate-700 bg-slate-900/80 pl-7 pr-7 font-mono text-[11px] text-slate-300 placeholder:text-slate-600 focus:border-cyan-600/50 focus:outline-none sm:w-36"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={handleClearSearch}
                className="absolute top-1/2 right-1.5 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                aria-label="Clear search"
              >
                <X className="size-3" />
              </button>
            )}
          </div>

          <Button
            type="button"
            variant="ghost"
            size="xs"
            onClick={() => setShowTimestamps((v) => !v)}
            className="h-7 gap-1 text-slate-400"
            title="Toggle timestamps"
          >
            <Clock className="size-3" />
            <span className="hidden sm:inline">{showTimestamps ? "Time" : "No time"}</span>
          </Button>

          <Button
            type="button"
            variant="ghost"
            size="xs"
            onClick={handleCopy}
            className="h-7 gap-1 text-slate-400"
            title="Copy log"
          >
            <Copy className="size-3" />
            <span className="hidden sm:inline">{copyFeedback ?? "Copy"}</span>
          </Button>

          <Button
            type="button"
            variant="ghost"
            size="xs"
            onClick={() => handleExport("txt")}
            className="h-7 gap-1 text-slate-400"
            title="Export log as text"
          >
            <Download className="size-3" />
            <span className="hidden sm:inline">TXT</span>
          </Button>

          <Button
            type="button"
            variant="ghost"
            size="xs"
            onClick={() => handleExport("json")}
            className="h-7 gap-1 text-slate-400"
            title="Export log as JSON"
          >
            <Download className="size-3" />
            <span className="hidden sm:inline">JSON</span>
          </Button>

          <span className="text-[10px] text-slate-600 tabular-nums">
            {filteredLines.length}/{lines.length}
          </span>
        </div>
      </div>

      {/* Filter bar */}
      <div
        className={cn(
          "flex shrink-0 flex-wrap items-center gap-1 border-b border-slate-800/80 bg-[#0d1117]/80",
          compact ? "px-2 py-1" : "px-3 py-1.5"
        )}
      >
        {FILTER_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            type="button"
            onClick={() => setFilter(opt.value)}
            className={cn(
              "rounded px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide transition-colors",
              filter === opt.value
                ? "bg-cyan-950/70 text-cyan-300 ring-1 ring-cyan-500/40"
                : "text-slate-500 hover:bg-slate-800/60 hover:text-slate-300"
            )}
          >
            {opt.label}
          </button>
        ))}
        {!autoScroll && (
          <Button
            type="button"
            variant="outline"
            size="xs"
            onClick={() => {
              setAutoScroll(true);
              if (terminalRef.current) {
                terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
              }
            }}
            className="ml-auto h-6 gap-1 border-amber-500/40 text-amber-400"
          >
            <Play className="size-3" /> Resume scroll
          </Button>
        )}
        {autoScroll && filteredLines.length > 0 && (
          <span className="ml-auto inline-flex items-center gap-1 text-[10px] text-slate-600">
            <Pause className="size-3" /> auto-scroll
          </span>
        )}
      </div>

      {/* Terminal body */}
      <div className="relative min-h-0 flex-1">
        <div
          ref={terminalRef}
          onScroll={handleScroll}
          className={cn("absolute inset-0 overflow-y-auto font-mono", compact ? "p-1" : "p-2")}
          style={{
            fontFamily: 'ui-monospace, "Cascadia Code", "SF Mono", Monaco, Menlo, Consolas, monospace',
          }}
        >
          {filteredLines.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center gap-1 text-center text-slate-500">
              {lines.length === 0 ? (
                <>
                  <span className="text-sm">Waiting for terminal output…</span>
                  <span className="text-xs text-slate-600">Attack execution will appear here</span>
                </>
              ) : (
                <span className="text-sm">No lines match the current filter</span>
              )}
            </div>
          ) : (
            <div className={compact ? "space-y-0" : "space-y-0.5"}>
              {filteredLines.map((line) => (
                <TerminalLineRow
                  key={line.id}
                  line={line}
                  showTimestamps={showTimestamps}
                  compact={compact}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
