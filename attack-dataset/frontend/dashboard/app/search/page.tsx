"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { orchestratorFetchInit, orchestratorHttp } from "@/lib/config";

interface SearchResult {
  id: string;
  title: string;
  description: string;
  category: string;
  mitre_technique?: string;
  severity: "low" | "medium" | "high" | "critical";
  confidence: number;
}

function mapSearchResults(data: {
  results?: Array<{
    record?: {
      id?: number;
      title?: string;
      scenario_description?: string;
      category?: string;
      mitre_technique?: string;
      impact?: string;
    };
    score?: number;
  }>;
}): SearchResult[] {
  return (data.results || []).map((r, idx) => {
    const rec = r.record || {};
    const impact = (rec.impact || "").toLowerCase();
    let severity: SearchResult["severity"] = "medium";
    if (impact.includes("critical")) severity = "critical";
    else if (impact.includes("high")) severity = "high";
    else if (impact.includes("low")) severity = "low";
    return {
      id: String(rec.id ?? idx),
      title: rec.title || "Untitled",
      description: rec.scenario_description || "",
      category: rec.category || "Unknown",
      mitre_technique: rec.mitre_technique,
      severity,
      confidence: typeof r.score === "number" ? r.score : 0,
    };
  });
}

interface AttackVector {
  name: string;
  description: string;
  steps: Array<{
    phase: string;
    technique: string;
    description: string;
    tools: string[];
  }>;
  estimated_time: string;
  risk_level: "low" | "medium" | "high" | "critical";
}

export default function SearchAndVectors() {
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [selectedServices, setSelectedServices] = useState<string[]>([]);
  const [attackVectors, setAttackVectors] = useState<AttackVector[]>([]);
  const [isBuildingVectors, setIsBuildingVectors] = useState(false);
  const [activeTab, setActiveTab] = useState<"search" | "vectors">("search");

  const commonServices = [
    "HTTP", "HTTPS", "FTP", "SSH", "SMTP", "DNS", "SMB", 
    "RDP", "MySQL", "PostgreSQL", "MongoDB", "Redis", "Elasticsearch"
  ];

  const handleSearch = async () => {
    if (!query.trim()) return;

    setIsSearching(true);
    setSearchError(null);
    try {
      const response = await fetch(orchestratorHttp("/search"), orchestratorFetchInit({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: query,
          top_k: 10
        })
      }));

      if (response.ok) {
        const data = await response.json();
        setSearchResults(mapSearchResults(data));
      } else {
        const err = await response.json().catch(() => ({}));
        setSearchResults([]);
        setSearchError((err as { error?: string }).error || `Search failed (${response.status})`);
      }
    } catch (error) {
      console.error("Search failed:", error);
      setSearchResults([]);
      setSearchError("Cannot reach orchestrator — is the stack running on port 3001?");
    } finally {
      setIsSearching(false);
    }
  };

  const toggleService = (service: string) => {
    setSelectedServices(prev =>
      prev.includes(service)
        ? prev.filter(s => s !== service)
        : [...prev, service]
    );
  };

  const buildAttackVectors = async () => {
    if (selectedServices.length === 0) return;

    setIsBuildingVectors(true);
    try {
      const response = await fetch(orchestratorHttp("/attack-vector"), orchestratorFetchInit({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          target_description: `Services: ${selectedServices.join(", ")}`,
          detected_services: selectedServices,
          detected_os: "",
          top_chains: 3
        })
      }));

      if (response.ok) {
        const data = await response.json();
        const chains = data.chains || [];
        type ChainStep = {
          phase?: string;
          attack?: { title?: string; mitre_technique?: string; tools_used?: string };
        };
        setAttackVectors(
          chains.map((c: { chain_id?: string; confidence?: number; steps?: ChainStep[] }) => ({
            name: c.chain_id || "Attack chain",
            description: `Confidence ${((c.confidence ?? 0) * 100).toFixed(0)}%`,
            steps: (c.steps || []).map((s) => ({
              phase: s.phase || "",
              technique: s.attack?.mitre_technique || "",
              description: s.attack?.title || "",
              tools: s.attack?.tools_used ? String(s.attack.tools_used).split(",") : [],
            })),
            estimated_time: "varies",
            risk_level: "medium" as const,
          }))
        );
      }
    } catch (error) {
      console.error("Failed to build attack vectors:", error);
    } finally {
      setIsBuildingVectors(false);
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case "critical": return "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium bg-red-500/10 text-red-400";
      case "high": return "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium bg-red-500/10 text-red-400";
      case "medium": return "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium bg-amber-500/10 text-amber-400";
      case "low": return "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium bg-emerald-500/10 text-emerald-400";
      default: return "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium bg-slate-500/10 text-slate-400";
    }
  };

  return (
    <div className="min-h-screen bg-[#080c14] text-white">
      {/* Header */}
      <header className="sticky top-0 z-40 border-b border-slate-800/60 bg-[#080c14]/80 backdrop-blur-xl">
        <div className="mx-auto max-w-7xl px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-cyan-400">Knowledge Search</h1>
              <p className="text-sm text-slate-500">Search attack patterns & build vectors</p>
            </div>
            <div className="flex gap-2">
              <Button
                onClick={() => setActiveTab("search")}
                className={`h-8 px-4 rounded-lg text-sm ${
                  activeTab === "search"
                    ? "bg-cyan-600 hover:bg-cyan-700"
                    : "bg-slate-700 hover:bg-slate-600"
                }`}
              >
                Search
              </Button>
              <Button
                onClick={() => setActiveTab("vectors")}
                className={`h-8 px-4 rounded-lg text-sm ${
                  activeTab === "vectors"
                    ? "bg-cyan-600 hover:bg-cyan-700"
                    : "bg-slate-700 hover:bg-slate-600"
                }`}
              >
                Attack Vectors
              </Button>
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-8">
        {activeTab === "search" ? (
          /* Search Tab */
          <div className="space-y-6">
            {/* Search Input */}
            <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-sm">
              <h2 className="text-base font-semibold text-white mb-4">Semantic Search</h2>
              <div className="flex gap-4">
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyPress={(e) => e.key === "Enter" && handleSearch()}
                  placeholder="Search for attack patterns, techniques, vulnerabilities..."
                  className="flex-1 rounded-lg border border-slate-700 bg-slate-950/50 px-4 py-2.5 text-sm text-white placeholder:text-slate-600 focus:border-cyan-500/50 focus:outline-none focus:ring-1 focus:ring-cyan-500/20"
                />
                <Button
                  onClick={handleSearch}
                  disabled={isSearching || !query.trim()}
                  className="h-9 bg-cyan-600 hover:bg-cyan-700 text-white px-6 py-3 rounded-lg"
                >
                  {isSearching ? "Searching..." : "Search"}
                </Button>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <span className="text-xs text-slate-500">Try:</span>
                {["SQL injection", "privilege escalation", "lateral movement", "exfiltration"].map((suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() => setQuery(suggestion)}
                    className="h-7 text-[11px] bg-slate-800 hover:bg-slate-700 px-2.5 rounded-md text-slate-400 border border-slate-800"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </section>

            {searchError && (
              <div className="rounded-xl border border-red-500/30 bg-red-950/20 p-4 text-sm text-red-300">
                {searchError}
              </div>
            )}

            {/* Search Results */}
            {searchResults.length > 0 && (
              <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-sm">
                <h2 className="text-base font-semibold text-white mb-4">
                  Results ({searchResults.length})
                </h2>
                <div className="space-y-4">
                  {searchResults.map((result) => (
                    <div
                      key={result.id}
                      className="rounded-lg border border-slate-800 bg-slate-950/30 p-4 hover:border-slate-600 transition-all"
                    >
                      <div className="flex items-start justify-between mb-2">
                        <div>
                          <h3 className="text-sm font-medium text-white">{result.title}</h3>
                          <p className="text-xs text-slate-500">{result.category}</p>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className={getSeverityColor(result.severity)}>
                            {result.severity.toUpperCase()}
                          </span>
                          <span className="text-xs text-slate-500">
                            {Math.round(result.confidence * 100)}% match
                          </span>
                        </div>
                      </div>
                      <p className="text-sm text-slate-400 mb-2">{result.description}</p>
                      {result.mitre_technique && (
                        <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium bg-purple-500/10 text-purple-400">
                          {result.mitre_technique}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </section>
            )}

            {searchResults.length === 0 && query && !isSearching && (
              <div className="rounded-xl border border-dashed border-slate-800 py-16 text-center">
                <p className="text-sm text-slate-400">No results found for &ldquo;{query}&rdquo;</p>
                <p className="text-xs text-slate-500 mt-2">Try different keywords or browse attack vectors</p>
              </div>
            )}
          </div>
        ) : (
          /* Attack Vectors Tab */
          <div className="space-y-6">
            {/* Service Selection */}
            <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-sm">
              <h2 className="text-base font-semibold text-white mb-4">Build Attack Vectors</h2>
              <p className="text-xs text-slate-500 mb-4">Select detected services to generate attack chains</p>
              
              <div className="flex flex-wrap gap-2 mb-4">
                {commonServices.map((service) => (
                  <button
                    key={service}
                    onClick={() => toggleService(service)}
                    className={`h-8 px-3 rounded-lg text-xs font-medium transition-all ${
                      selectedServices.includes(service)
                        ? "bg-cyan-600 text-white border border-cyan-500"
                        : "bg-slate-950/30 text-slate-400 border border-slate-800 hover:border-slate-600"
                    }`}
                  >
                    {service}
                  </button>
                ))}
              </div>

              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-500">
                  {selectedServices.length} service(s) selected
                </span>
                <Button
                  onClick={buildAttackVectors}
                  disabled={selectedServices.length === 0 || isBuildingVectors}
                  className="h-9 bg-cyan-600 hover:bg-cyan-700 text-white px-6 py-2 rounded-lg"
                >
                  {isBuildingVectors ? "Building..." : "Generate Vectors"}
                </Button>
              </div>
            </section>

            {/* Generated Attack Vectors */}
            {attackVectors.length > 0 && (
              <section className="space-y-4">
                <h2 className="text-base font-semibold text-white">
                  Generated Attack Vectors ({attackVectors.length})
                </h2>
                {attackVectors.map((vector, idx) => (
                  <div
                    key={idx}
                    className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-sm"
                  >
                    <div className="flex items-start justify-between mb-4">
                      <div>
                        <h3 className="text-sm font-medium text-cyan-400">{vector.name}</h3>
                        <p className="text-xs text-slate-500 mt-1">{vector.description}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className={getSeverityColor(vector.risk_level)}>
                          {vector.risk_level.toUpperCase()} RISK
                        </span>
                        <span className="text-xs text-slate-500">
                          {vector.estimated_time}
                        </span>
                      </div>
                    </div>

                    <div className="space-y-3">
                      <h4 className="text-xs font-medium text-slate-400">Attack Steps</h4>
                      {vector.steps.map((step, stepIdx) => (
                        <div
                          key={stepIdx}
                          className="rounded-lg border border-slate-800 bg-slate-950/30 p-3"
                        >
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-sm font-medium text-white">
                              {stepIdx + 1}. {step.phase}
                            </span>
                            <span className="text-xs text-purple-400">{step.technique}</span>
                          </div>
                          <p className="text-sm text-slate-400 mb-2">{step.description}</p>
                          {step.tools.length > 0 && (
                            <div className="flex flex-wrap gap-1">
                              {step.tools.map((tool, toolIdx) => (
                                <span
                                  key={toolIdx}
                                  className="h-6 text-[11px] bg-slate-800 text-slate-400 px-2 rounded-md border border-slate-800 flex items-center"
                                >
                                  {tool}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>

                    <div className="mt-4 flex gap-2">
                      <Button className="h-8 bg-cyan-600 hover:bg-cyan-700 text-white px-4 py-2 rounded text-sm">
                        Use This Vector
                      </Button>
                      <Button className="h-8 bg-slate-700 hover:bg-slate-600 text-white px-4 py-2 rounded text-sm">
                        Export
                      </Button>
                    </div>
                  </div>
                ))}
              </section>
            )}

            {attackVectors.length === 0 && selectedServices.length > 0 && !isBuildingVectors && (
              <div className="rounded-xl border border-dashed border-slate-800 py-16 text-center">
                <p className="text-sm text-slate-400">Click &ldquo;Generate Vectors&rdquo; to create attack chains</p>
                <p className="text-xs text-slate-500 mt-2">Based on selected services and attack patterns</p>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
