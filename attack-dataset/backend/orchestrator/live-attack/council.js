"use strict";

const { v4: uuidv4 } = require("uuid");
const axios = require("axios");
const { buildCouncilGroundingPack } = require("./grounding");
const {
  fetchHubToolCatalog,
  catalogSummaryForGrounding,
  formatCatalogForPrompt,
} = require("../toolCatalog");
const {
  keChainToOrchestratorSteps,
  extractDatasetRecordIds,
} = require("./chain-versioning");
const { suggestActionForFailure } = require("./failure-taxonomy");
const {
  appendReasoningTrace,
  OPSEC_VETO_THRESHOLD,
  ALLOW_HIGH_RISK,
} = require("./directive-applier");

const AGENT_ORDER = ["tactical", "opsec", "architect", "exploit", "conductor"];
const JAILBREAK_VIA_HUB = process.env.JAILBREAK_VIA_HUB !== "false";

async function fetchCouncilMemoFromHub(
  integrationHubUrl,
  authHeaders,
  operation,
  groundingPack,
  eng,
  trigger,
  agentMemos,
  failureInfo,
  toolCatalogSummary
) {
  const url = `${integrationHubUrl.replace(/\/$/, "")}/integrations/execute`;
  const { data } = await axios.post(
    url,
    {
      plugin_name: "jailbreak_ai",
      engagement_id: eng.id || eng.engagement_id || "live-council",
      target: eng.target || "unknown",
      parameters: {
        operation,
        grounding_pack: groundingPack,
        agent_memos: agentMemos,
        tool_catalog: toolCatalogSummary || groundingPack.tool_catalog || null,
        tool_catalog_prompt: groundingPack.tool_catalog_prompt || null,
        aggression_level:
          eng.aggression_level ?? groundingPack.aggression_level ?? 5,
        boundary_profile:
          eng.boundary_profile ?? groundingPack.boundary_profile ?? null,
        failure_class: failureInfo?.failure_class,
        trigger: {
          type: trigger.type,
          phase: trigger.step?.phase,
          step_number: trigger.step_number,
        },
        reasoning_context: {
          prior_directives: (eng.live_council?.directives || []).slice(-3),
          reasoning_trace: (eng.reasoning_trace || []).slice(-5),
          current_phase: trigger.step?.phase,
          aggression_level:
            eng.aggression_level ?? groundingPack.aggression_level ?? 5,
        },
        suggested_action:
          operation === "replan_attack_chain" ||
          operation === "council_conductor"
            ? suggestActionForFailure(failureInfo?.failure_class, trigger.type)
            : undefined,
      },
      timeout: 90,
    },
    { timeout: 95000, headers: authHeaders }
  );
  if (!data?.success || !data.output) return null;
  const out = data.output;
  const agent = operation.replace("council_", "");
  if (agent === "conductor" || operation === "replan_attack_chain") {
    return out.directive ? { agent: "conductor", ...out } : { agent: "conductor", directive: out };
  }
  return { agent, ...out };
}

async function runAgentMemosViaHub(
  integrationHubUrl,
  authHeaders,
  groundingPack,
  eng,
  trigger,
  failureInfo,
  toolCatalogSummary
) {
  const memos = [];
  for (const agent of AGENT_ORDER.slice(0, 4)) {
    const operation = `council_${agent}`;
    try {
      const memo = await fetchCouncilMemoFromHub(
        integrationHubUrl,
        authHeaders,
        operation,
        groundingPack,
        eng,
        trigger,
        memos,
        failureInfo,
        toolCatalogSummary
      );
      if (memo) memos.push(memo);
    } catch (err) {
      console.warn(`Council hub ${operation} failed:`, err.message);
    }
  }
  return memos.length ? memos : null;
}

function initLiveCouncil(eng) {
  if (eng.live_council?.enabled) {
    if (!eng.live_council.state) eng.live_council.state = "idle";
    if (!eng.reasoning_trace) eng.reasoning_trace = [];
    return eng.live_council;
  }
  eng.live_council = {
    enabled: true,
    state: "idle",
    turn: 0,
    analysis_lock: false,
    max_replans: parseInt(process.env.LIVE_MAX_REPLANS || "5", 10),
    replans_used: 0,
    agent_order: AGENT_ORDER,
    grounding_history: [],
    last_grounding_pack: null,
    last_directive: null,
    pending_directive: null,
    directives: [],
    agent_memos: [],
  };
  eng.reasoning_trace = eng.reasoning_trace || [];
  return eng.live_council;
}

function summarizeHits(hits, limit = 5) {
  return (hits || []).slice(0, limit).map((h) => ({
    id: h.id,
    title: h.title,
    mitre: h.mitre_technique,
    score: h.score,
  }));
}

function runAgentMemos(groundingPack, eng, trigger, failureInfo) {
  const memos = [];
  const topHit = groundingPack.dataset_hits[0];
  const mlTop = groundingPack.ml_predictions[0];
  const failure =
    trigger.step_result?.status === "failed" ||
    trigger.type === "step_failed" ||
    trigger.type === "method_failed";

  const opsecRisk = failure && topHit?.detection_method ? 0.65 : 0.35;

  memos.push({
    agent: "tactical",
    assessment: failure
      ? `Step failed (${failureInfo?.failure_class || "unknown"}); top dataset match: ${topHit?.title || "none"}`
      : `Step succeeded; continue toward ${trigger.step?.phase || "next phase"}`,
    suggested_tool: topHit?.tools_used?.split(",")[0]?.trim() || trigger.step?.tool,
    evidence_ids: summarizeHits(groundingPack.dataset_hits).map((h) => h.id).filter(Boolean),
    dataset_hits: summarizeHits(groundingPack.dataset_hits),
  });

  memos.push({
    agent: "opsec",
    veto: opsecRisk >= OPSEC_VETO_THRESHOLD,
    risk_score: opsecRisk,
    risk_note: topHit?.detection_method
      ? `Detection: ${String(topHit.detection_method).slice(0, 120)}`
      : "Standard execution risk",
    timing_advice: failure ? "Increase delay between methods" : "Maintain current tempo",
  });

  memos.push({
    agent: "architect",
    missing_phases: [],
    chain_patch_hint: mlTop
      ? `ML category ${mlTop.label} (${(mlTop.confidence * 100).toFixed(0)}%)`
      : "Re-align remaining steps to MITRE order",
    phase_skip_authorized: false,
  });

  const alternateIdx =
    groundingPack.replan_candidates?.length > 1 ? 1 : null;

  memos.push({
    agent: "exploit",
    new_methods: groundingPack.dataset_hits.slice(0, 3).map((h) => ({
      title: h.title,
      tool: h.tools_used,
      record_id: h.id,
    })),
    ml_category: mlTop?.label,
    tool_pivot: failureInfo?.failed_tool
      ? `Avoid ${failureInfo.failed_tool}; use alternate from dataset hits`
      : null,
    alternate_chain_index: alternateIdx,
  });

  return memos;
}

async function fetchLiveReplanChains(
  eng,
  trigger,
  groundingPack,
  knowledgeEngineUrl,
  authHeaders,
  failureInfo
) {
  const services =
    eng.scan_session?.fingerprint?.services?.map((s) =>
      [s.name, s.product, s.version].filter(Boolean).join(" ")
    ) || [];

  const completed_steps = (eng.chain_execution?.steps || []).map((s) => ({
    phase: s.step?.phase,
    status: s.status,
    attack: s.step?.attack,
    output: (s.output || "").slice(0, 500),
  }));

  const last_failure = {
    phase: trigger.step?.phase,
    tool: trigger.step?.tool || trigger.step_result?.chain_attack_methods?.[0]?.tool,
    method_id: trigger.step_result?.chain_attack_methods?.find((m) => !m.success)?.method_id,
    method_name: trigger.step_result?.chain_attack_methods?.find((m) => !m.success)?.method_name,
    output: (trigger.step_result?.output || "").slice(0, 2000),
    failure_class: failureInfo?.failure_class,
  };

  const { data } = await axios.post(
    `${knowledgeEngineUrl}/attack-vector/live-replan`,
    {
      target_description: `Target: ${eng.target}. ${groundingPack.query_text.slice(0, 500)}`,
      detected_services: services,
      detected_os: eng.scan_session?.fingerprint?.os || "",
      top_chains: parseInt(process.env.LIVE_REPLAN_TOP_CHAINS || "3", 10),
      failure_class: failureInfo?.failure_class,
      execution_context: {
        completed_steps,
        last_failure,
        from_phase: trigger.step?.phase,
        from_step_index: Math.max(0, (trigger.step_number || 1) - 1),
        prior_directive_ids: (eng.live_council?.directives || [])
          .slice(-3)
          .map((d) => d.directive_id),
      },
    },
    { timeout: 90000, headers: authHeaders }
  );

  if (data?.chains?.length) {
    groundingPack.replan_candidates = data.chains;
    groundingPack.alternate_chain_scores = data.alternate_chain_scores || [];
  }

  return data;
}

function countStepDelta(currentSteps, newSteps, fromIdx) {
  const remaining = (currentSteps || []).length - fromIdx;
  return Math.abs(remaining - (newSteps || []).length);
}

function buildDirectiveFromCouncil(
  eng,
  trigger,
  groundingPack,
  agentMemos,
  replanData,
  failureInfo,
  conductorOutput
) {
  const fromIdx = Math.max(0, (trigger.step_number || 1) - 1);
  const failureClass = failureInfo?.failure_class || "unknown";
  const opsecMemo = agentMemos.find((m) => m.agent === "opsec");
  const exploitMemo = agentMemos.find((m) => m.agent === "exploit");
  const opsecVeto =
    Boolean(opsecMemo?.veto) ||
    (opsecMemo?.risk_score != null && opsecMemo.risk_score >= OPSEC_VETO_THRESHOLD);

  if (conductorOutput?.directive) {
    const d = conductorOutput.directive;
    return {
      directive_id: uuidv4(),
      turn: groundingPack.turn,
      issued_at: new Date().toISOString(),
      action: d.action || "continue",
      priority: d.priority || "normal",
      from_step_index: d.from_step_index ?? fromIdx,
      rationale: d.rationale || conductorOutput.rationale || "Conductor directive",
      rationale_steps: d.rationale_steps || [],
      agent_consensus: { memos: agentMemos },
      updated_steps: d.updated_steps,
      pivot_chain_index: d.pivot_chain_index ?? d.updated_chain_index,
      dataset_record_ids: d.dataset_record_ids || [],
      opsec_veto: d.opsec_veto ?? opsecVeto,
      confidence: d.confidence ?? 0.7,
      failure_class: d.failure_class || failureClass,
      applied: false,
    };
  }

  const council = eng.live_council;
  if (council?.replans_used >= council?.max_replans) {
    return {
      directive_id: uuidv4(),
      turn: groundingPack.turn,
      issued_at: new Date().toISOString(),
      action: "abort",
      priority: "critical",
      from_step_index: fromIdx,
      rationale: "Max replans exceeded — aborting execution",
      rationale_steps: [{ step: "limit", detail: "LIVE_MAX_REPLANS reached" }],
      agent_consensus: { memos: agentMemos },
      opsec_veto: false,
      failure_class: failureClass,
      applied: false,
    };
  }

  if (opsecVeto && trigger.type !== "step_completed") {
    if (ALLOW_HIGH_RISK) {
      return {
        directive_id: uuidv4(),
        turn: groundingPack.turn,
        issued_at: new Date().toISOString(),
        action: "continue",
        priority: "high",
        from_step_index: fromIdx,
        rationale:
          opsecMemo?.risk_note ||
          "OpSec high risk noted — continuing (ALLOW_HIGH_RISK)",
        rationale_steps: [{ step: "opsec", detail: "Risk threshold exceeded — not blocking" }],
        agent_consensus: { memos: agentMemos },
        opsec_veto: true,
        failure_class: failureClass,
        applied: false,
      };
    }
    return {
      directive_id: uuidv4(),
      turn: groundingPack.turn,
      issued_at: new Date().toISOString(),
      action: "pause",
      priority: "high",
      from_step_index: fromIdx,
      rationale: opsecMemo?.risk_note || "OpSec veto — execution paused",
      rationale_steps: [{ step: "opsec", detail: "Risk threshold exceeded" }],
      agent_consensus: { memos: agentMemos },
      opsec_veto: true,
      failure_class: failureClass,
      applied: false,
    };
  }

  const chains = replanData?.chains || [];
  const best = chains[0];
  const alternate = chains[1];
  const currentSteps = eng.attack_chains?.chains?.[eng.attack_chains?.active_chain_index ?? 0]?.steps || [];

  if (!best?.steps?.length) {
    return {
      directive_id: uuidv4(),
      turn: groundingPack.turn,
      issued_at: new Date().toISOString(),
      action: trigger.type === "step_completed" ? "continue" : "continue",
      priority: "normal",
      from_step_index: fromIdx,
      rationale: "Live replan returned no chains; continue with caution",
      rationale_steps: [{ step: "replan", detail: "No matching chains in attack DB" }],
      agent_consensus: { memos: agentMemos },
      dataset_record_ids: summarizeHits(groundingPack.dataset_hits).map((h) => h.id),
      opsec_veto: false,
      confidence: 0.3,
      failure_class: failureClass,
      applied: false,
    };
  }

  const updated_steps = keChainToOrchestratorSteps(best);
  const dataset_record_ids = extractDatasetRecordIds(updated_steps);
  const suggested = suggestActionForFailure(failureClass, trigger.type);
  const delta = countStepDelta(currentSteps, updated_steps, fromIdx);

  let action = suggested;
  const altScore = replanData?.alternate_chain_scores?.[1];
  const primaryScore = replanData?.alternate_chain_scores?.[0] ?? best.confidence ?? 0.7;

  if (
    alternate?.steps?.length &&
    (failureClass === "wrong_vector" ||
      exploitMemo?.alternate_chain_index != null ||
      (altScore != null && altScore > primaryScore + 0.1))
  ) {
    action = "pivot_chain";
  } else if (delta <= 3 && failureClass === "auth_failed") {
    action = "patch_chain";
  } else if (trigger.type === "step_completed") {
    action = "continue";
  } else if (delta <= 3) {
    action = "patch_chain";
  } else {
    action = "reinitiate_chain";
  }

  const rationale_steps = [
    { step: "classify", detail: `Failure class: ${failureClass}` },
    { step: "ground", detail: `${replanData.dataset_hit_count || 0} dataset hits, ML: ${replanData.ml_top_label || "n/a"}` },
    { step: "decide", detail: `Selected ${action} (delta=${delta})` },
  ];

  const directive = {
    directive_id: uuidv4(),
    turn: groundingPack.turn,
    issued_at: new Date().toISOString(),
    action,
    priority: action === "continue" ? "normal" : "high",
    from_step_index: action === "pivot_chain" ? 0 : fromIdx,
    rationale:
      `Council ${action} from attack DB (${replanData.dataset_hit_count || 0} hits, ` +
      `ML: ${replanData.ml_top_label || "n/a"}, class: ${failureClass}).`,
    rationale_steps,
    agent_consensus: { memos: agentMemos },
    updated_steps: action === "continue" ? undefined : updated_steps,
    updated_chain: best,
    pivot_chain_index:
      action === "pivot_chain"
        ? exploitMemo?.alternate_chain_index ?? 1
        : undefined,
    dataset_record_ids,
    opsec_veto: false,
    confidence: best.confidence ?? primaryScore,
    grounding_query: replanData.grounding_query,
    failure_class: failureClass,
    applied: false,
  };

  if (action === "pivot_chain" && alternate?.steps?.length) {
    directive.updated_steps = keChainToOrchestratorSteps(alternate);
    directive.updated_chain = alternate;
    directive.pivot_chain_index = exploitMemo?.alternate_chain_index ?? 1;
    directive.dataset_record_ids = extractDatasetRecordIds(directive.updated_steps);
  }

  return directive;
}

async function runConductorViaHub(
  integrationHubUrl,
  authHeaders,
  groundingPack,
  eng,
  trigger,
  agentMemos,
  failureInfo,
  replanData
) {
  if (!JAILBREAK_VIA_HUB || !integrationHubUrl) return null;
  try {
    return await fetchCouncilMemoFromHub(
      integrationHubUrl,
      authHeaders,
      "replan_attack_chain",
      { ...groundingPack, replan_candidates: replanData?.chains },
      eng,
      trigger,
      agentMemos,
      failureInfo
    );
  } catch (err) {
    console.warn("Conductor hub failed:", err.message);
    return null;
  }
}

async function runCouncilTurn(ctx) {
  const {
    eng,
    trigger,
    knowledgeEngineUrl,
    integrationHubUrl,
    getServiceAuthHeaders,
    broadcastCouncil,
    broadcastTerminal,
    engagementId,
    failureInfo: passedFailureInfo,
  } = ctx;

  const council = initLiveCouncil(eng);
  if (council.analysis_lock) {
    return council.last_directive;
  }

  const isReplannable =
    trigger.type === "step_failed" ||
    trigger.type === "method_failed" ||
    trigger.type === "isolated_retry_exhausted" ||
    trigger.type === "force_replan";

  const isCouncilReview =
    isReplannable ||
    trigger.type === "scan_session_updated" ||
    trigger.type === "guided_phase_complete";

  if (!isCouncilReview) {
    return null;
  }

  if (isReplannable && council.replans_used >= council.max_replans) {
    return buildDirectiveFromCouncil(
      eng,
      trigger,
      { turn: council.turn + 1 },
      [],
      null,
      passedFailureInfo || { failure_class: "unknown" },
      null
    );
  }

  council.analysis_lock = true;
  const authHeaders = getServiceAuthHeaders ? getServiceAuthHeaders() : {};
  const failureInfo = passedFailureInfo || {
    failure_class: "none",
    confidence: 1,
  };

  try {
    council.turn += 1;
    if (broadcastCouncil) {
      broadcastCouncil(engagementId, {
        type: "council_turn_started",
        turn: council.turn,
        trigger: trigger.type,
      });
    }
    if (broadcastTerminal) {
      broadcastTerminal(
        engagementId,
        `\n🧠 LIVE COUNCIL TURN ${council.turn} — ${trigger.type} (${failureInfo.failure_class})`,
        "info"
      );
    }

    const groundingPack = await buildCouncilGroundingPack(
      eng,
      trigger,
      knowledgeEngineUrl,
      authHeaders
    );
    groundingPack.turn = council.turn;

    let toolCatalogSummary = eng.tool_catalog || null;
    if (integrationHubUrl && !toolCatalogSummary) {
      try {
        const catalog = await fetchHubToolCatalog(
          integrationHubUrl,
          axios,
          authHeaders
        );
        toolCatalogSummary = catalogSummaryForGrounding(catalog);
        groundingPack.tool_catalog = toolCatalogSummary;
        groundingPack.tool_catalog_prompt = formatCatalogForPrompt(catalog, {
          webOnly: eng.guided_autonomous?.web_only !== false,
          aggressionLevel: eng.aggression_level ?? 5,
        });
        eng.tool_catalog = toolCatalogSummary;
      } catch (catErr) {
        console.warn("Council tool catalog fetch:", catErr.message);
      }
    } else if (toolCatalogSummary) {
      groundingPack.tool_catalog = toolCatalogSummary;
    }

    council.last_grounding_pack = groundingPack;
    council.grounding_history.push({
      turn: council.turn,
      query_text: groundingPack.query_text.slice(0, 200),
      hit_count: groundingPack.dataset_hits.length,
      ml_top: groundingPack.ml_predictions[0]?.label,
      trigger: trigger.type,
      failure_class: failureInfo.failure_class,
    });
    if (council.grounding_history.length > 30) council.grounding_history.shift();

    let agentMemos = null;
    if (JAILBREAK_VIA_HUB && integrationHubUrl) {
      agentMemos = await runAgentMemosViaHub(
        integrationHubUrl,
        authHeaders,
        groundingPack,
        eng,
        trigger,
        failureInfo,
        toolCatalogSummary
      );
    }
    if (!agentMemos?.length) {
      agentMemos = runAgentMemos(groundingPack, eng, trigger, failureInfo);
    }

    for (const memo of agentMemos) {
      council.agent_memos.push({ turn: council.turn, ...memo });
      if (broadcastCouncil) {
        broadcastCouncil(engagementId, {
          type: "council_agent_memo",
          turn: council.turn,
          agent: memo.agent,
          memo,
        });
      }
    }

    let replanData = null;
    let conductorOutput = null;

    if (isReplannable) {
      replanData = await fetchLiveReplanChains(
        eng,
        trigger,
        groundingPack,
        knowledgeEngineUrl,
        authHeaders,
        failureInfo
      );
      conductorOutput = await runConductorViaHub(
        integrationHubUrl,
        authHeaders,
        groundingPack,
        eng,
        trigger,
        agentMemos,
        failureInfo,
        replanData
      );
    }

    const directive = buildDirectiveFromCouncil(
      eng,
      trigger,
      groundingPack,
      agentMemos,
      replanData,
      failureInfo,
      conductorOutput
    );

    council.last_directive = directive;
    council.directives.push(directive);
    if (directive.action !== "continue") {
      council.replans_used += 1;
    }

    appendReasoningTrace(
      eng,
      {
        source: "council_turn",
        turn: council.turn,
        trigger: trigger.type,
        failure_class: failureInfo.failure_class,
        action: directive.action,
        rationale: directive.rationale,
        rationale_steps: directive.rationale_steps,
        directive_id: directive.directive_id,
        alternate_pathways: (replanData?.chains || [])
          .slice(0, 3)
          .map((c, i) => c?.name || c?.id || `chain-${i + 1}`),
      },
      { engagementId, broadcastCouncil, broadcastTerminal }
    );

    if (broadcastCouncil) {
      broadcastCouncil(engagementId, {
        type: "live_directive",
        directive,
      });
    }
    if (broadcastTerminal) {
      broadcastTerminal(
        engagementId,
        `📋 DIRECTIVE: ${directive.action} — ${(directive.rationale || "").slice(0, 200)}`,
        ["reinitiate_chain", "pivot_chain", "abort"].includes(directive.action)
          ? "warning"
          : "info"
      );
    }

    return directive;
  } finally {
    council.analysis_lock = false;
  }
}

module.exports = {
  initLiveCouncil,
  runCouncilTurn,
  buildDirectiveFromCouncil,
  AGENT_ORDER,
};
