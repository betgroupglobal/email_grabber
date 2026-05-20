"use strict";

const GUIDED_PHASES = [
  { num: 1, key: "identify", title: "Identify target" },
  { num: 2, key: "reconnaissance", title: "Reconnaissance" },
  { num: 3, key: "vulnerability_scanning", title: "Vulnerability scanning" },
  { num: 4, key: "web_app_testing", title: "Web app testing" },
  { num: 5, key: "exploitation", title: "Exploitation" },
  { num: 6, key: "privilege_escalation", title: "Privilege escalation" },
  { num: 7, key: "post_exploitation", title: "Post-exploitation" },
  { num: 8, key: "covering_tracks", title: "Covering tracks" },
];

const stopFlags = new Map();

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Phase-specific orchestrator heuristic when jailbreak pathways exhaust or API fails. */
function buildPhaseHeuristicFallback(phase, ctx, errMessage) {
  const aggression = ctx.aggressionLevel ?? 5;
  const webOnly = ctx.webOnly !== false;
  const base = {
    phase_complete: true,
    skip_phase: false,
    foothold_detected: false,
    source: "heuristic_orchestrator",
    api_error: errMessage || null,
  };

  switch (phase.num) {
    case 1:
      return {
        ...base,
        narrative: `Identify ${ctx.target || "target"} — confirm web scope and ROE (aggression ${aggression}/10).`,
        recommended_actions: ["Confirm hostname/TLS", "Note CDN/WAF hints", "Record ROE scope"],
        invoke_scan: true,
        invoke_hub: false,
        hub_operation: "none",
        trigger_opsec_assess: false,
        trigger_execute_chain: false,
        artifact_text: `Phase 1 identify: web-only=${webOnly}, aggression=${aggression}.`,
      };
    case 2:
      return {
        ...base,
        narrative: "Reconnaissance — HTTP(S) service discovery and tech fingerprint (not repeat of phase 1).",
        recommended_actions: ["Hub reconnaissance 80/443", "TLS/cert check", "Technology fingerprint"],
        invoke_scan: true,
        invoke_hub: true,
        hub_operation: "reconnaissance",
        hub_parameters: { ports: "80,443,8080,8443", scan_type: "web_application" },
        tools_to_invoke: [
          { plugin: "nuclei", tool: "scan_target", params: { operation: "scan_target", templates: "http/technologies/" } },
        ],
        trigger_opsec_assess: false,
        trigger_execute_chain: false,
        artifact_text: "Phase 2 recon: web_application ports and nuclei tech templates.",
      };
    case 3:
      return {
        ...base,
        narrative: "Vulnerability scanning — template/CVE pass (avoid repeating phase 2 nmap-only).",
        recommended_actions: ["Nuclei CVE/high severity", "FFUF vhost if multi-host"],
        invoke_scan: true,
        invoke_hub: false,
        hub_operation: "none",
        tools_to_invoke: [
          { plugin: "nuclei", tool: "scan_target", params: { operation: "scan_target", severity: "critical,high" } },
          { plugin: "ffuf", tool: "fuzz_vhost", params: { operation: "fuzz_vhost" } },
        ],
        trigger_opsec_assess: false,
        trigger_execute_chain: false,
        artifact_text: "Phase 3 vuln scan: nuclei critical/high + optional vhost fuzz.",
      };
    case 4:
      return {
        ...base,
        narrative: "Web app testing — injection/auth/session checks; trigger OpSec assess for chains.",
        recommended_actions: ["SQLmap light probe", "KE attack-vector", "OpSec chain assess"],
        invoke_scan: false,
        invoke_hub: false,
        hub_operation: "none",
        tools_to_invoke: [
          { plugin: "sqlmap", tool: "test_url", params: { operation: "test_url", level: 1, risk: 1 } },
          { plugin: "knowledge_engine", tool: "attack-vector", params: { top_chains: 3 } },
        ],
        trigger_opsec_assess: true,
        trigger_execute_chain: false,
        artifact_text: "Phase 4 web testing + OpSec assess prep.",
      };
    case 5:
      return {
        ...base,
        narrative:
          aggression >= 7
            ? "Exploitation — execute best web-relevant KE chain after OpSec assess."
            : "Exploitation — controlled chain execution per council/OpSec.",
        recommended_actions: ["Execute chain index 0", "Validate findings against prior phases"],
        invoke_scan: false,
        invoke_hub: false,
        hub_operation: "none",
        trigger_opsec_assess: false,
        trigger_execute_chain: aggression >= 7 && webOnly,
        chain_index: 0,
        artifact_text: `Phase 5 exploitation (aggression ${aggression}, trigger_chain=${aggression >= 7}).`,
      };
    default:
      return {
        ...base,
        narrative: `Complete ${phase.title} with available web-safe tools.`,
        recommended_actions: [`Finish ${phase.title}`],
        invoke_scan: false,
        invoke_hub: false,
        hub_operation: "none",
        trigger_opsec_assess: false,
        trigger_execute_chain: false,
        artifact_text: `Phase ${phase.num} heuristic fallback.`,
      };
  }
}

function createGuidedAutonomousService(deps) {
  const {
    engagements,
    broadcast,
    broadcastTerminal,
    axios,
    getServiceAuthHeaders,
    normalizeTargetInput,
    isValidTarget,
    validateAndSanitizeTarget,
    buildBoundaryProfile,
    inferOpsecAssessAttackVectorContext,
    KNOWLEDGE_ENGINE,
    OPSEC_URL,
    INTEGRATION_HUB_URL,
    ANALYZER_URL,
    PORT,
    liveAttack,
  } = deps;

  const { appendReasoningTrace: appendReasoningTraceEntry } = require("./reasoning-pattern");
  const {
    fetchHubToolCatalog,
    formatCatalogForPrompt,
    catalogSummaryForGrounding,
    defaultToolsForPhase,
    buildRunSummary,
  } = require("./toolCatalog");
  const { executeToolCalls } = require("./toolExecutor");
  const {
    buildPhaseArtifactText,
    extractPriorFindingsText,
    mergeFingerprintFromResults,
    summarizeToolOutcomes,
  } = require("./toolOutcomeSummarizer");
  const { rankToolsForPhase, dedupeHubFromPlan } = require("./toolSelector");
  const { ALLOW_HIGH_RISK } = require("./live-attack/directive-applier");
  const { getCachedSearch, getCachedAttackVector } = require("./ke-cache");

  function appendReasoningTrace(eng, entry, extraOpts = {}) {
    return appendReasoningTraceEntry(eng, entry, {
      engagementId: extraOpts.engagementId,
      broadcastCouncil: extraOpts.broadcastCouncil || broadcast,
      broadcastTerminal: extraOpts.broadcastTerminal || broadcastTerminal,
    });
  }

  function appendLog(eng, msg) {
    eng.log = eng.log || [];
    eng.log.push({ ts: new Date().toISOString(), msg });
  }

  function updateGuided(eng, patch) {
    eng.guided_autonomous = {
      ...(eng.guided_autonomous || {}),
      ...patch,
      updated_at: new Date().toISOString(),
    };
  }

  function scanTypeForPhase(phase, target, plan) {
    if (plan?.scan_type && plan.scan_type !== "none") return plan.scan_type;
    const t = String(target || "").toLowerCase();
    if (phase.num === 1) return "quick";
    if (phase.num === 2) return t.includes("http") ? "web_application" : "comprehensive";
    if (phase.num === 3) return "web_application";
    if (phase.num === 4) return "comprehensive";
    return "quick";
  }

  function shouldRunScanForPhase(phase, plan, ctx) {
    if (plan?.invoke_scan === false) return false;
    if (plan?.invoke_scan === true) return true;
    if (phase.num < 1 || phase.num > 4) return false;
    const scanType = scanTypeForPhase(phase, ctx?.target, plan);
    if (ctx?.completedScanTypes?.has(scanType)) return false;
    return true;
  }

  async function emitScanCouncilEvent(engagementId, eng, scanDelta) {
    if (!liveAttack?.emitCouncilEvent) return;
    await liveAttack
      .emitCouncilEvent(
        {
          type: "scan_session_updated",
          engagement_id: engagementId,
          scan_delta: scanDelta,
        },
        {
          eng,
          engagementId,
          reqBody: { live_council: true },
          knowledgeEngineUrl: KNOWLEDGE_ENGINE,
          integrationHubUrl: INTEGRATION_HUB_URL,
          getServiceAuthHeaders,
          broadcast,
          broadcastCouncil: broadcast,
          broadcastTerminal,
        }
      )
      .catch((err) => console.warn(`[guided ${engagementId}] scan council:`, err.message));
  }

  async function runSingleAnalyzerScan(engagementId, eng, ctx, phase, plan, scanType) {
    const boundary = eng.boundary_profile || buildBoundaryProfile(ctx.aggressionLevel ?? 5);
    const scanTimeout = plan?.scan_timeout_sec ?? boundary.scan_timeout_sec ?? 120;
    const pollMs = boundary.scan_poll_timeout_ms ?? 180000;

    broadcastTerminal(
      engagementId,
      `[scan] Phase ${phase.num} — starting ${scanType} scan on ${eng.target}`,
      "command"
    );

    try {
      const { data: startData } = await axios.post(
        `${ANALYZER_URL}/scan`,
        {
          target: eng.target,
          aggression_level: ctx.aggressionLevel ?? 5,
          scan_timeout_sec: scanTimeout,
          scan_type: scanType,
        },
        { timeout: 30000, headers: getServiceAuthHeaders() }
      );

      const sessionId = startData?.id;
      if (!sessionId) {
        broadcastTerminal(engagementId, "[scan] No session id returned from analyzer", "warning");
        return null;
      }

      eng.scan_session = {
        id: sessionId,
        status: "scanning",
        scan_type: scanType,
        target: eng.target,
        phase: phase.num,
      };
      broadcast(engagementId, eng);
      broadcastTerminal(engagementId, `[scan] Session ${sessionId} — polling…`, "info");

      const deadline = Date.now() + pollMs;
      let lastStatus = "";
      while (Date.now() < deadline) {
        if (stopFlags.get(engagementId)) break;
        await sleep(2500);

        let sess;
        try {
          const resp = await axios.get(`${ANALYZER_URL}/sessions/${sessionId}`, {
            headers: getServiceAuthHeaders(),
            timeout: 15000,
          });
          sess = resp.data;
        } catch (pollErr) {
          broadcastTerminal(engagementId, `[scan] Poll error: ${pollErr.message}`, "warning");
          break;
        }

        eng.scan_session = { ...sess, id: sessionId, scan_type: scanType, phase: phase.num };
        if (sess.status !== lastStatus) {
          lastStatus = sess.status;
          const ports = sess.open_port_count ?? sess.fingerprint?.services?.length ?? 0;
          broadcastTerminal(
            engagementId,
            `[scan] ${sess.status}${ports ? ` · ${ports} open ports/services` : ""}`,
            "info"
          );
          broadcast(engagementId, eng);
        }

        if (sess.status === "ready") {
          eng.fingerprint = sess.fingerprint || eng.fingerprint;
          ctx.fingerprint = sess.fingerprint || ctx.fingerprint;
          if (ctx.completedScanTypes && scanType) {
            ctx.completedScanTypes.add(scanType);
          }
          const svcCount =
            sess.fingerprint?.services?.length ?? sess.service_count ?? 0;
          broadcastTerminal(
            engagementId,
            `[scan] Complete — ${svcCount} services · OS ${sess.fingerprint?.os || "unknown"}`,
            "success"
          );
          await emitScanCouncilEvent(engagementId, eng, {
            phase: phase.num,
            scan_type: scanType,
            session_id: sessionId,
            services_found: svcCount,
          });
          broadcast(engagementId, eng);
          return sess;
        }

        if (sess.status === "error") {
          broadcastTerminal(
            engagementId,
            `[scan] Session error: ${sess.error || "unknown"}`,
            "error"
          );
          return null;
        }
      }

      broadcastTerminal(
        engagementId,
        `[scan] Timed out waiting for session ${sessionId}`,
        "warning"
      );
    } catch (err) {
      broadcastTerminal(engagementId, `[scan] Failed: ${err.message}`, "warning");
      appendLog(eng, `Analyzer scan failed (phase ${phase.num}): ${err.message}`);
    }
    return null;
  }

  async function runRealtimeAnalyzerScan(engagementId, eng, ctx, phase, plan) {
    if (!ANALYZER_URL) {
      broadcastTerminal(engagementId, "[scan] Analyzer URL not configured", "warning");
      return null;
    }

    const primaryScanType = scanTypeForPhase(phase, eng.target, plan);
    appendReasoningTrace(
      eng,
      {
        source: "guided_autonomous",
        phase_number: phase.num,
        scan_type: primaryScanType,
        rationale: `Probe target via ${primaryScanType} scan (phase ${phase.num})`,
        pattern_step: "probe",
      },
      { engagementId }
    );
    if (!liveAttack?.runWithInfluencePathways) {
      return runSingleAnalyzerScan(engagementId, eng, ctx, phase, plan, primaryScanType);
    }

    liveAttack.initInfluenceState(eng);
    const pathwayResult = await liveAttack.runWithInfluencePathways({
      eng,
      engagementId,
      task_kind: "scan",
      task_id: `phase_${phase.num}_scan`,
      context: { primary_scan_type: primaryScanType, phase: phase.num },
      broadcastTerminal,
      broadcastCouncil: broadcast,
      executePrimary: () =>
        runSingleAnalyzerScan(engagementId, eng, ctx, phase, plan, primaryScanType),
      executeAlternate: (pathway) =>
        runSingleAnalyzerScan(
          engagementId,
          eng,
          ctx,
          phase,
          { ...plan, scan_type: pathway.params.scan_type },
          pathway.params.scan_type
        ),
      buildAlternates: (_failed, context) =>
        liveAttack.buildScanAlternatePathways(context.primary_scan_type),
    });

    return pathwayResult.result || null;
  }

  async function callHubWithPathways(engagementId, eng, operation, extra = {}) {
    const primaryParams = extra.hub_parameters || extra.parameters || {};

    if (!liveAttack?.runWithInfluencePathways) {
      return callHubOperation(engagementId, eng.target, operation, extra);
    }

    liveAttack.initInfluenceState(eng);
    const pathwayResult = await liveAttack.runWithInfluencePathways({
      eng,
      engagementId,
      task_kind: "hub",
      task_id: operation,
      context: { operation, primary_params: primaryParams },
      broadcastTerminal,
      broadcastCouncil: broadcast,
      executePrimary: () => callHubOperation(engagementId, eng.target, operation, extra),
      executeAlternate: (pathway) =>
        callHubOperation(engagementId, eng.target, operation, {
          ...extra,
          hub_parameters: { ...primaryParams, ...pathway.params },
          parameters: { ...primaryParams, ...pathway.params },
        }),
      buildAlternates: (_failed, context) =>
        liveAttack.buildHubAlternatePathways(context.operation, context.primary_params),
    });

    const data = pathwayResult.result;
    if (data && !pathwayResult.success && data.error) {
      throw new Error(data.error);
    }
    return data;
  }

  async function prefetchKeRagContext(ctx, target) {
    const query = `web application security penetration test ${target}`;
    try {
      const result = await getCachedSearch({
        query,
        target,
        limit: 6,
        fetchFn: async () => {
          const { data } = await axios.post(
            `${KNOWLEDGE_ENGINE}/search`,
            { query, limit: 10 },
            { timeout: 15_000, headers: getServiceAuthHeaders() }
          );
          return data;
        },
      });
      ctx.ragContext = result.rag_context || "";
      ctx.ragCacheHit = Boolean(result.cache_hit);
      appendLog(
        engagements.get(ctx.engagementId) || { log: [] },
        `KE RAG prefetch: ${result.cache_hit ? "cache hit" : "fresh"} (${result.latency_ms || 0}ms)`
      );
    } catch (err) {
      ctx.ragContext = "";
      appendLog(
        engagements.get(ctx.engagementId) || { log: [] },
        `KE RAG prefetch skipped: ${err.message}`
      );
    }
  }

  async function callGuidedPhasePlan(eng, engagementId, target, phase, ctx, pathwayOpts = {}) {
    const boundary =
      eng.boundary_profile || buildBoundaryProfile(ctx.aggressionLevel ?? 5);
    const hubTimeoutSec = Math.max(
      120,
      Math.ceil((boundary.ai_timeout_ms || 120000) / 1000)
    );
    const axiosTimeoutMs = Math.max(130000, hubTimeoutSec * 1000 + 15000);

    const catalogPromptMax =
      ctx.aggressionLevel >= 7
        ? parseInt(process.env.TOOL_CATALOG_PROMPT_MAX || "32", 10)
        : parseInt(process.env.TOOL_CATALOG_PROMPT_MAX || "24", 10);
    const toolCatalogText = ctx.toolCatalog
      ? formatCatalogForPrompt(ctx.toolCatalog, {
          webOnly: ctx.webOnly,
          aggressionLevel: ctx.aggressionLevel,
          maxEntries: catalogPromptMax,
        })
      : "";
    const priorFindings = extractPriorFindingsText(ctx.phaseRecords);
    const recommendedTools = rankToolsForPhase({
      phaseNum: phase.num,
      target,
      targetClass: ctx.targetClass || "web_application",
      fingerprint: ctx.fingerprint || {},
      aggression: ctx.aggressionLevel,
      webOnly: ctx.webOnly,
      catalog: ctx.toolCatalog,
      completedOps: ctx.completedHubOps || new Set(),
      priorFindings,
    });
    const payload = {
      plugin_name: "jailbreak_ai",
      engagement_id: engagementId,
      target,
      parameters: {
        operation: "guided_phase_plan",
        phase_number: phase.num,
        phase_key: phase.key,
        phase_title: phase.title,
        target,
        prior_artifacts: ctx.priorArtifacts,
        prior_findings: priorFindings,
        recommended_tools: recommendedTools,
        aggression_level: ctx.aggressionLevel,
        boundary_profile: boundary,
        web_only: ctx.webOnly,
        fingerprint: ctx.fingerprint || {},
        tool_catalog: ctx.toolCatalog ? catalogSummaryForGrounding(ctx.toolCatalog) : null,
        tool_catalog_prompt: toolCatalogText,
        template_variant: pathwayOpts.template_variant,
        reasoning_context: {
          prior_directives: (eng.live_council?.directives || []).slice(-3),
          reasoning_trace: (eng.reasoning_trace || []).slice(-5),
          tool_catalog_summary: ctx.toolCatalog
            ? catalogSummaryForGrounding(ctx.toolCatalog)
            : null,
        },
        rag_context: ctx.ragContext || "",
        target_class: ctx.targetClass || "web_application",
      },
      timeout: hubTimeoutSec,
    };

    const maxRetries = 1;
    let lastErr;
    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        const planStarted = Date.now();
        const { data } = await axios.post(
          `${INTEGRATION_HUB_URL}/integrations/execute`,
          payload,
          { timeout: axiosTimeoutMs, headers: getServiceAuthHeaders() }
        );
        if (!data?.success) {
          throw new Error(data?.error || "guided_phase_plan failed");
        }
        let plan = data.output || {};
        plan = dedupeHubFromPlan(plan);
        plan.ai_latency_ms = Math.round(
          (data.execution_time || 0) * 1000 || Date.now() - planStarted
        );
        plan.ai_source = plan.source || "jailbreak_api";
        plan.recommended_tools = recommendedTools;
        return plan;
      } catch (err) {
        lastErr = err;
        const retryable =
          /socket hang up|ECONNRESET|ETIMEDOUT|ECONNABORTED|timeout/i.test(
            err.message || ""
          );
        if (!retryable || attempt >= maxRetries) break;
        await sleep(1500 * (attempt + 1));
      }
    }
    throw lastErr;
  }

  async function callHubOperation(engagementId, target, operation, extra = {}) {
    const { data } = await axios.post(
      `${INTEGRATION_HUB_URL}/execute`,
      {
        operation,
        target,
        context: { engagement_id: engagementId },
        ...extra,
      },
      { timeout: 300000, headers: getServiceAuthHeaders() }
    );
    return data;
  }

  async function runOpsecAssessOnEngagement(eng) {
    const target = eng.target;
    const boundary = eng.boundary_profile || buildBoundaryProfile(eng.aggression_level);
    const authHeaders = getServiceAuthHeaders();
    const opType = "web_application";
    const assessCtx = inferOpsecAssessAttackVectorContext(
      target,
      opType,
      eng.fingerprint || null
    );

    let attack_chains = null;
    try {
      const vectorBody = {
        target_description: assessCtx.target_description,
        detected_services: assessCtx.detected_services,
        detected_os: assessCtx.detected_os,
        top_chains: boundary.base_top_chains || 3,
      };
      const vectorResult = await getCachedAttackVector({
        body: vectorBody,
        fetchFn: async () => {
          const { data } = await axios.post(
            `${KNOWLEDGE_ENGINE}/attack-vector`,
            vectorBody,
            { headers: authHeaders, timeout: 90000 }
          );
          return data;
        },
      });
      attack_chains = vectorResult.data;
      appendLog(
        eng,
        `KE attack-vector: ${attack_chains?.chains?.length || 0} chain(s)${vectorResult.cache_hit ? " (cached)" : ""}`
      );
    } catch (err) {
      appendLog(eng, `KE attack-vector: ${err.message}`);
    }

    let chainOpsec = { risk_score: 50, global_findings: [], summary: "" };
    try {
      const primary = attack_chains?.chains?.[0];
      if (primary?.steps?.length) {
        const steps = primary.steps.map((s) => {
          const attack = s.attack || {};
          return {
            title: attack.title || s.phase || "step",
            attack_type: attack.attack_type || opType,
            attack_steps:
              attack.scenario_description ||
              attack.attack_steps ||
              s.rationale ||
              `Phase ${s.phase}`,
            tools_used: attack.tools_used || "",
            mitre_technique: attack.mitre_technique || s.mitre_technique || "",
            detection_method: attack.detection_method || "",
            tags: attack.tags || "",
          };
        });
        const { data } = await axios.post(
          `${OPSEC_URL}/assess/chain`,
          { steps },
          { headers: authHeaders, timeout: 60000 }
        );
        chainOpsec = data;
      }
    } catch (err) {
      throw new Error(`OpSec assess failed: ${err.message}`);
    }

    eng.attack_chains = attack_chains;
    eng.opsec_reports = chainOpsec;
    const risk = chainOpsec.risk_score ?? 50;
    appendLog(
      eng,
      `OpSec assess: ${attack_chains?.chains?.length || 0} chain(s), risk ${risk}/100`
    );
    return { attack_chains, chainOpsec, risk_score: risk };
  }

  async function triggerExecuteChain(engagementId, chainIndex) {
    const eng = engagements.get(engagementId);
    if (!eng?.attack_chains?.chains?.length) {
      return { skipped: true, reason: "no_chains" };
    }
    const idx = Math.min(
      Math.max(0, chainIndex),
      eng.attack_chains.chains.length - 1
    );
    const chain = eng.attack_chains.chains[idx];
    const base = `http://127.0.0.1:${PORT}`;
    const { data } = await axios.post(
      `${base}/execute-chain`,
      {
        engagement_id: engagementId,
        chain_index: idx,
        chain,
        live_council: true,
      },
      { timeout: 600000, headers: getServiceAuthHeaders() }
    );
    if (data?.status === "aborted" || data?.status === "paused") {
      return { ...data, council_halted: true };
    }
    return data;
  }

  function buildPriorArtifacts(phaseRecords) {
    return (phaseRecords || [])
      .map((p) => {
        let body = String(p.artifact_text || "").trim();
        if (body.length < 80 && (p.tool_results?.length || p.hub_results?.length)) {
          const extra = summarizeToolOutcomes({
            tool_results: p.tool_results,
            hub_results: p.hub_results,
          });
          if (extra) body = body ? `${body}\n\n${extra}` : extra;
        }
        if (!body) return null;
        return `--- Phase ${p.phase_number}: ${p.title} (${p.status}) ---\n${body}`;
      })
      .filter(Boolean)
      .join("\n\n");
  }

  async function runPhase(engagementId, phase, ctx) {
    const eng = engagements.get(engagementId);
    if (!eng) return;

    if (stopFlags.get(engagementId)) {
      updateGuided(eng, { status: "stopped" });
      eng.status = "stopped";
      appendLog(eng, "Autonomous pipeline stopped by user");
      broadcast(engagementId, eng);
      return;
    }

    updateGuided(eng, { current_phase: phase.num, current_phase_title: phase.title });
    eng.status = "running";
    appendLog(eng, `Guided phase ${phase.num}/8: ${phase.title}`);
    broadcast(engagementId, eng);

    broadcastTerminal(
      engagementId,
      `\n🧠 JAILBREAK AI — Phase ${phase.num}/8: ${phase.title}`,
      "command"
    );

    appendReasoningTrace(
      eng,
      {
        source: "guided_autonomous",
        phase_number: phase.num,
        phase_key: phase.key,
        title: phase.title,
        rationale: `Hypothesize attack surface for phase ${phase.num}: ${phase.title}`,
      },
      { engagementId }
    );

    const webOnly = ctx.webOnly !== false;
    if (webOnly && (phase.num === 6 || phase.num === 7)) {
      const skipRecord = {
        phase_number: phase.num,
        phase_key: phase.key,
        title: phase.title,
        status: "skipped",
        ai_source: "policy",
        narrative: "Skipped — external web-only assessment (no foothold required).",
        artifact_text: "Skipped — external web-only target; privilege escalation and post-exploitation are N/A unless a foothold is confirmed.",
        hub_results: [],
      };
      ctx.phaseRecords.push(skipRecord);
      broadcastTerminal(engagementId, `⏭️ Phase ${phase.num} skipped (web-only)`, "info");
      broadcast(engagementId, eng);
      return;
    }

    let plan;
    try {
      ctx.priorArtifacts = buildPriorArtifacts(ctx.phaseRecords);
      if (liveAttack?.runWithInfluencePathways) {
        liveAttack.initInfluenceState(eng);
        const planPathways = await liveAttack.runWithInfluencePathways({
          eng,
          engagementId,
          task_kind: "guided_phase",
          task_id: `phase_${phase.num}_plan`,
          context: { phase: phase.num },
          broadcastTerminal,
          broadcastCouncil: broadcast,
          executePrimary: () =>
            callGuidedPhasePlan(eng, engagementId, eng.target, phase, ctx),
          executeAlternate: async (pathway) =>
            callGuidedPhasePlan(eng, engagementId, eng.target, phase, ctx, pathway.params || {}),
          buildAlternates: () => liveAttack.buildAlternatePathways("guided_phase", {}),
        });
        plan = planPathways.result;
        if (!planPathways.success) {
          throw new Error("guided_phase_plan failed after pathway attempts");
        }
      } else {
        plan = await callGuidedPhasePlan(eng, engagementId, eng.target, phase, ctx);
      }
    } catch (err) {
      plan = buildPhaseHeuristicFallback(phase, { ...ctx, target: eng.target }, err.message);
      appendLog(eng, `Jailbreak plan error (phase heuristic): ${err.message}`);
      broadcastTerminal(
        engagementId,
        `⚠️ Phase ${phase.num} using orchestrator heuristic — ${err.message}`,
        "warning"
      );
    }

    if (/heuristic/i.test(plan.source || "")) {
      broadcastTerminal(
        engagementId,
        `⚠️ AI plan source: ${plan.source}${plan.api_error ? ` (${plan.api_error})` : ""}`,
        "warning"
      );
    }

    if (shouldRunScanForPhase(phase, plan, ctx)) {
      await runRealtimeAnalyzerScan(engagementId, eng, ctx, phase, plan);
    }

    const aiSource = plan.source || plan.ai_source || "unknown";
    ctx.jailbreakSources.push(aiSource);
    updateGuided(eng, {
      last_ai_source: aiSource,
      last_ai_latency_ms: plan.ai_latency_ms ?? null,
      jailbreak_api_configured: ctx.jailbreakApiConfigured,
    });

    broadcastTerminal(
      engagementId,
      `📋 ${plan.narrative || "(no narrative)"}`.slice(0, 500),
      "info"
    );
    if (plan.ai_latency_ms != null) {
      broadcastTerminal(
        engagementId,
        `[ai] ${aiSource} · ${plan.ai_latency_ms}ms`,
        "info"
      );
    }
    if (plan.recommended_actions?.length) {
      for (const action of plan.recommended_actions.slice(0, 5)) {
        broadcastTerminal(engagementId, `  → ${action}`, "info");
      }
    }

    const hubResults = [];
    const toolResults = [];

    ctx.priorFindings = extractPriorFindingsText(ctx.phaseRecords);

    const plannedTools = Array.isArray(plan.tools_to_invoke) ? plan.tools_to_invoke : [];
    const autoTools =
      plannedTools.length === 0 && ctx.toolCatalog
        ? defaultToolsForPhase(phase.num, eng.target, {
            webOnly: ctx.webOnly !== false,
            aggressionLevel: ctx.aggressionLevel,
          })
        : [];
    const toolsToRun = plannedTools.length ? plannedTools : autoTools;

    if (autoTools.length) {
      broadcastTerminal(
        engagementId,
        `[tool] Phase ${phase.num} auto-invoke: ${autoTools.map((t) => t.plugin).join(", ")}`,
        "info"
      );
    }

    if (toolsToRun.length && ctx.toolCatalog) {
      const toolExec = await executeToolCalls(
        {
          axios,
          INTEGRATION_HUB_URL,
          ANALYZER_URL,
          KNOWLEDGE_ENGINE,
          getServiceAuthHeaders,
          liveAttack,
        },
        {
          calls: toolsToRun,
          catalog: ctx.toolCatalog,
          engagementId,
          eng,
          ctx,
          broadcastTerminal,
          broadcastCouncil: broadcast,
          appendReasoningTrace: (e, entry) =>
            appendReasoningTrace(e, entry, { engagementId }),
        }
      );
      toolResults.push(...(toolExec.results || []));
      const okCount = (toolExec.results || []).filter((r) => r.success).length;
      ctx.toolsInvokedCount = (ctx.toolsInvokedCount || 0) + okCount;
    }

    if (plan.skip_phase) {
      const skipRecord = {
        phase_number: phase.num,
        phase_key: phase.key,
        title: phase.title,
        status: "skipped",
        ai_source: aiSource,
        narrative: plan.narrative,
        artifact_text: plan.artifact_text || plan.narrative,
        hub_results: [],
      };
      ctx.phaseRecords.push(skipRecord);
      if (plan.foothold_detected) ctx.webOnly = false;
      broadcast(engagementId, eng);
      return;
    }

    if (plan.invoke_hub && plan.hub_operation && plan.hub_operation !== "none") {
      try {
        broadcastTerminal(
          engagementId,
          `[hub] ${plan.hub_operation} ${JSON.stringify(plan.hub_parameters || {}).slice(0, 120)}`,
          "command"
        );
        const hubData = await callHubWithPathways(
          engagementId,
          eng,
          plan.hub_operation,
          { hub_parameters: plan.hub_parameters || {} }
        );
        hubResults.push({ operation: plan.hub_operation, result: hubData });
        if (!ctx.completedHubOps) ctx.completedHubOps = new Set();
        ctx.completedHubOps.add(plan.hub_operation);
        const summary =
          typeof hubData?.output === "string"
            ? hubData.output.slice(0, 1500)
            : JSON.stringify(hubData?.output || hubData).slice(0, 1500);
        broadcastTerminal(engagementId, `[hub] result:\n${summary}`, "success");
      } catch (hubErr) {
        hubResults.push({ operation: plan.hub_operation, error: hubErr.message });
        appendLog(eng, `Hub ${plan.hub_operation} failed: ${hubErr.message}`);
        const alts = liveAttack?.buildHubAlternatePathways?.(
          plan.hub_operation,
          plan.hub_parameters || {}
        );
        const nextAlt = Array.isArray(alts) ? alts[0] : null;
        broadcastTerminal(
          engagementId,
          `[hub] failed: ${hubErr.message}${
            nextAlt
              ? ` — try alternate: ${nextAlt.label || nextAlt.pathway_id} (council replan: Shift+R or approve pivot)`
              : " — press Shift+R for council replan"
          }`,
          "warning"
        );
      }
    } else if (
      phase.num === 2 &&
      !plan.invoke_hub &&
      !ctx.completedHubOps?.has("reconnaissance")
    ) {
      try {
        broadcastTerminal(engagementId, "[hub] auto reconnaissance (nmap quick)", "command");
        const hubData = await callHubWithPathways(engagementId, eng, "reconnaissance", {
          hub_parameters: { ports: "80,443", scan_type: "quick" },
        });
        hubResults.push({ operation: "reconnaissance", result: hubData, auto: true });
        if (!ctx.completedHubOps) ctx.completedHubOps = new Set();
        ctx.completedHubOps.add("reconnaissance");
        const summary =
          typeof hubData?.output === "string"
            ? hubData.output.slice(0, 800)
            : JSON.stringify(hubData?.output || hubData).slice(0, 800);
        broadcastTerminal(engagementId, `[hub] result:\n${summary}`, "success");
      } catch (hubErr) {
        appendLog(eng, `Auto nmap failed: ${hubErr.message}`);
        broadcastTerminal(engagementId, `[hub] auto recon failed: ${hubErr.message}`, "warning");
      }
    }

    const runAssess =
      phase.num === 4 && (plan.trigger_opsec_assess !== false);
    if (runAssess) {
      try {
        broadcastTerminal(
          engagementId,
          "[opsec] Running assess — Knowledge Engine attack-vector + OpSec Monitor",
          "info"
        );
        await runOpsecAssessOnEngagement(eng);
        ctx.assessComplete = true;
        const chainCount = eng.attack_chains?.chains?.length || 0;
        const risk = eng.opsec_reports?.risk_score ?? "?";
        broadcastTerminal(
          engagementId,
          `[opsec] Complete — ${chainCount} chain(s), risk ${risk}/100`,
          "success"
        );
        if (ALLOW_HIGH_RISK && typeof risk === "number" && risk >= 75) {
          broadcastTerminal(
            engagementId,
            "[opsec] high risk noted — continuing (ALLOW_HIGH_RISK)",
            "warning"
          );
        }
        if (chainCount > 0) {
          broadcastTerminal(
            engagementId,
            `[mitre] KE mapped ${chainCount} attack chain(s) from scan + assess context`,
            "info"
          );
        }
      } catch (assessErr) {
        appendLog(eng, `OpSec assess failed: ${assessErr.message}`);
        broadcastTerminal(engagementId, `[opsec] failed: ${assessErr.message}`, "warning");
      }
    }

    const autoChainAfterAssess =
      runAssess &&
      eng.attack_chains?.chains?.length &&
      !ctx.chainExecuted &&
      !eng.live_council?.pending_directive;
    if (autoChainAfterAssess) {
      try {
        broadcastTerminal(
          engagementId,
          `[chain] Auto-execute — ${eng.attack_chains.chains.length} chain(s) ready (live council)`,
          "command"
        );
        await triggerExecuteChain(engagementId, plan.chain_index ?? 0);
        ctx.chainExecuted = true;
      } catch (chainErr) {
        appendLog(eng, `Auto execute-chain failed: ${chainErr.message}`);
        broadcastTerminal(engagementId, `[chain] auto-execute failed: ${chainErr.message}`, "warning");
      }
    }

    const aggression = ctx.aggressionLevel ?? eng.aggression_level ?? 5;
    const webTarget = ctx.webOnly !== false;
    const defaultPhase5Chain =
      phase.num === 5 &&
      aggression >= 7 &&
      webTarget &&
      ctx.assessComplete &&
      eng.attack_chains?.chains?.length;
    const runChain =
      phase.num === 5 &&
      (Boolean(plan.trigger_execute_chain) || defaultPhase5Chain) &&
      eng.attack_chains?.chains?.length &&
      !ctx.chainExecuted;
    if (runChain) {
      try {
        broadcastTerminal(
          engagementId,
          `[chain] Execute index ${plan.chain_index ?? 0} (phase 5)`,
          "command"
        );
        await triggerExecuteChain(engagementId, plan.chain_index ?? 0);
        ctx.chainExecuted = true;
      } catch (chainErr) {
        appendLog(eng, `Execute-chain failed: ${chainErr.message}`);
        broadcastTerminal(engagementId, `[chain] failed: ${chainErr.message}`, "warning");
      }
    }

    if (plan.foothold_detected) ctx.webOnly = false;

    const findingsSummary = summarizeToolOutcomes({
      tool_results: toolResults,
      hub_results: hubResults,
    });
    const artifactText = buildPhaseArtifactText(
      plan.artifact_text || plan.narrative,
      toolResults,
      hubResults
    );
    if (phase.num === 2 || toolResults.some((r) => r.plugin === "analyzer")) {
      ctx.fingerprint = mergeFingerprintFromResults(
        ctx.fingerprint,
        toolResults,
        hubResults
      );
    }

    const phaseRecord = {
      phase_number: phase.num,
      phase_key: phase.key,
      title: phase.title,
      status: plan.phase_complete !== false ? "complete" : "partial",
      ai_source: aiSource,
      ai_latency_ms: plan.ai_latency_ms ?? null,
      narrative: plan.narrative,
      artifact_text: artifactText,
      findings_summary: findingsSummary,
      tools_planned: plannedTools.length ? plannedTools : autoTools,
      tools_executed: toolResults,
      recommended_actions: plan.recommended_actions || [],
      hub_results: hubResults,
      tool_results: toolResults,
      council_turn: eng.live_council?.turn ?? null,
      council_turn_id: eng.live_council?.last_directive?.directive_id ?? null,
      completed_at: new Date().toISOString(),
    };
    ctx.phaseRecords.push(phaseRecord);
    updateGuided(eng, { phases: ctx.phaseRecords });

    appendReasoningTrace(
      eng,
      {
        source: "guided_autonomous",
        phase_number: phase.num,
        phase_key: phase.key,
        title: phase.title,
        narrative: plan.narrative,
        recommended_actions: plan.recommended_actions || [],
        ai_source: aiSource,
        council_turn: eng.live_council?.turn,
        hub_operation: plan.hub_operation,
        invoke_scan: plan.invoke_scan,
      },
      { engagementId }
    );

    if (liveAttack?.emitCouncilEvent) {
      await liveAttack
        .emitCouncilEvent(
          {
            type: "guided_phase_complete",
            engagement_id: engagementId,
            phase: phase.key,
            foothold_detected: Boolean(plan.foothold_detected),
          },
          {
            eng,
            engagementId,
            reqBody: { live_council: true },
            knowledgeEngineUrl: KNOWLEDGE_ENGINE,
            integrationHubUrl: INTEGRATION_HUB_URL,
            getServiceAuthHeaders,
            broadcast,
            broadcastTerminal,
          }
        )
        .catch((err) => console.warn(`[guided ${engagementId}] council phase emit:`, err.message));
    }

    broadcast(engagementId, eng);
    await sleep(800);
  }

  async function runGuidedAutonomousPipeline(engagementId) {
    const eng = engagements.get(engagementId);
    if (!eng) return;

    stopFlags.set(engagementId, false);
    const ctx = {
      phaseRecords: eng.guided_autonomous?.phases || [],
      webOnly: eng.guided_autonomous?.web_only !== false,
      aggressionLevel: eng.aggression_level ?? 5,
      fingerprint: eng.fingerprint || {},
      assessComplete: Boolean(eng.attack_chains?.chains?.length),
      chainExecuted: false,
      toolsInvokedCount: 0,
      jailbreakSources: [],
      jailbreakApiConfigured: Boolean(process.env.JAILBREAK_API_KEY),
      toolCatalog: null,
      completedScanTypes: new Set(),
      completedHubOps: new Set(),
      target: eng.target,
      engagementId,
      ragContext: "",
      ragCacheHit: false,
      targetClass: "web_application",
    };

    try {
      await prefetchKeRagContext(ctx, eng.target);
      ctx.toolCatalog = await fetchHubToolCatalog(
        INTEGRATION_HUB_URL,
        axios,
        getServiceAuthHeaders()
      );
      eng.tool_catalog = catalogSummaryForGrounding(ctx.toolCatalog);
      broadcastTerminal(
        engagementId,
        `[tool] catalog loaded — ${ctx.toolCatalog.entries?.length || 0} external tools available`,
        "info"
      );
    } catch (catErr) {
      appendLog(eng, `Tool catalog fetch failed: ${catErr.message}`);
      broadcastTerminal(
        engagementId,
        `[tool] catalog unavailable (${catErr.message}); static tools only`,
        "warning"
      );
    }

    updateGuided(eng, {
      status: "running",
      started_at: eng.guided_autonomous?.started_at || new Date().toISOString(),
      phases: ctx.phaseRecords,
    });
    eng.status = "running";
    if (liveAttack?.initLiveCouncil) {
      liveAttack.initLiveCouncil(eng);
      eng.live_council.enabled = true;
      eng.live_council.state = "executing";
    }
    broadcast(engagementId, eng);

    broadcastTerminal(engagementId, "\n" + "=".repeat(72), "info");
    broadcastTerminal(
      engagementId,
      "🤖 AUTONOMOUS GUIDED ASSESSMENT — Jailbreak AI orchestrator",
      "success"
    );
    broadcastTerminal(engagementId, `🎯 Target: ${eng.target}`, "info");
    broadcastTerminal(
      engagementId,
      `🔑 Jailbreak API: ${ctx.jailbreakApiConfigured ? "configured" : "heuristic fallback"}`,
      ctx.jailbreakApiConfigured ? "success" : "warning"
    );
    broadcastTerminal(engagementId, "=".repeat(72) + "\n", "info");

    appendReasoningTrace(
      eng,
      {
        source: "guided_autonomous",
        phase_number: 0,
        title: "Target engagement",
        rationale: `Orient on target ${eng.target}; aggression ${ctx.aggressionLevel}; web_only=${ctx.webOnly}`,
        boundary_profile: {
          scan_timeout_sec: eng.boundary_profile?.scan_timeout_sec,
        },
      },
      { engagementId }
    );

    try {
      for (const phase of GUIDED_PHASES) {
        if (stopFlags.get(engagementId)) break;
        await runPhase(engagementId, phase, ctx);
      }

      const finalEng = engagements.get(engagementId);
      if (!finalEng) return;

      if (stopFlags.get(engagementId)) {
        updateGuided(finalEng, {
          status: "stopped",
          phases: ctx.phaseRecords,
          jailbreak_sources: [...new Set(ctx.jailbreakSources)],
        });
        finalEng.status = "stopped";
      } else {
        const runSummary = buildRunSummary(finalEng, ctx);
        updateGuided(finalEng, {
          status: "complete",
          current_phase: 8,
          phases: ctx.phaseRecords,
          completed_at: new Date().toISOString(),
          jailbreak_sources: [...new Set(ctx.jailbreakSources)],
          assess_complete: ctx.assessComplete,
          chain_executed: ctx.chainExecuted,
          tools_invoked_count: ctx.toolsInvokedCount || 0,
          pathway_attempts_count: (finalEng.influence_attempts || []).length,
          run_summary: runSummary,
        });
        finalEng.status = "complete";
        finalEng.completed_at = new Date().toISOString();
        appendLog(finalEng, "Autonomous guided assessment complete (8 phases)");
        broadcastTerminal(engagementId, "\n✅ Autonomous guided assessment complete\n", "success");
      }
      broadcast(engagementId, finalEng);
    } catch (err) {
      const failedEng = engagements.get(engagementId);
      if (failedEng) {
        updateGuided(failedEng, {
          status: "error",
          error: err.message,
          phases: ctx.phaseRecords,
        });
        failedEng.status = "error";
        appendLog(failedEng, `Pipeline error: ${err.message}`);
        broadcastTerminal(engagementId, `❌ Pipeline error: ${err.message}`, "error");
        broadcast(engagementId, failedEng);
      }
    } finally {
      stopFlags.delete(engagementId);
    }
  }

  function requestStop(engagementId) {
    stopFlags.set(engagementId, true);
    const eng = engagements.get(engagementId);
    if (eng?.guided_autonomous) {
      updateGuided(eng, { status: "stopping" });
      broadcast(engagementId, eng);
    }
    return { ok: true };
  }

  function getStatus(engagementId) {
    const eng = engagements.get(engagementId);
    if (!eng) return null;
    const ga = eng.guided_autonomous || {};
    const pathwayAttempts = (eng.influence_attempts || []).length;
    const toolsInvoked =
      ga.tools_invoked_count ??
      (ga.phases || []).reduce(
        (n, p) => n + (p.tool_results || []).filter((r) => r.success).length,
        0
      );
    const runSummary =
      ga.run_summary ||
      (ga.status === "complete" || ga.status === "stopped"
        ? buildRunSummary(eng, {
            phaseRecords: ga.phases,
            toolsInvokedCount: toolsInvoked,
            assessComplete: ga.assess_complete,
            chainExecuted: ga.chain_executed,
          })
        : null);

    return {
      engagement_id: engagementId,
      target: eng.target,
      status: eng.status,
      policy: { allow_high_risk: ALLOW_HIGH_RISK },
      guided_autonomous: {
        ...ga,
        tools_invoked_count: toolsInvoked,
        pathway_attempts_count: ga.pathway_attempts_count ?? pathwayAttempts,
        run_summary: runSummary,
      },
      attack_chains_count: eng.attack_chains?.chains?.length || 0,
      live_council: eng.live_council || null,
      scan_session: eng.scan_session || null,
      fingerprint: eng.fingerprint || null,
      attack_chains: eng.attack_chains
        ? { version: eng.attack_chains.version ?? 0 }
        : null,
      reasoning_trace: (eng.reasoning_trace || []).slice(-20),
    };
  }

  return {
    GUIDED_PHASES,
    runGuidedAutonomousPipeline,
    requestStop,
    getStatus,
  };
}

module.exports = { createGuidedAutonomousService, GUIDED_PHASES };
