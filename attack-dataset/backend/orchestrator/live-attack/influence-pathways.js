"use strict";

const { LIVE_REQUIRE_APPROVAL, ALLOW_HIGH_RISK } = require("./directive-applier");

const INFLUENCE_MAX_PATHWAY_ATTEMPTS = Math.max(
  1,
  parseInt(process.env.INFLUENCE_MAX_PATHWAY_ATTEMPTS || "2", 10)
);
const GUIDED_PHASE_MAX_PATHWAY_ATTEMPTS = Math.max(
  1,
  parseInt(process.env.GUIDED_PHASE_MAX_PATHWAY_ATTEMPTS || "2", 10)
);
const INFLUENCE_PATHWAY_COOLDOWN_MS = Math.max(
  0,
  parseInt(process.env.INFLUENCE_PATHWAY_COOLDOWN_MS || "750", 10)
);

const SCAN_PROFILE_ALTERNATES = {
  quick: ["web_application", "comprehensive"],
  web_application: ["comprehensive", "quick"],
  comprehensive: ["web_application", "quick"],
};

const HUB_RECON_ALTERNATES = [
  { pathway_id: "hub_recon_quick", method: "hub_scan_profile", label: "recon quick ports 80,443", params: { scan_type: "quick", ports: "80,443" } },
  { pathway_id: "hub_recon_full", method: "hub_scan_profile", label: "recon comprehensive 1-1000", params: { scan_type: "comprehensive", ports: "1-1000" } },
  { pathway_id: "hub_recon_web", method: "hub_scan_profile", label: "recon web_application", params: { scan_type: "web_application", ports: "80,443,8080,8443" } },
];

const NUCLEI_TEMPLATE_ALTERNATES = [
  { pathway_id: "nuclei_tags_cve", method: "nuclei_templates", label: "nuclei tags=cve", params: { operation: "scan_target", tags: "cve" } },
  { pathway_id: "nuclei_severity_high", method: "nuclei_severity", label: "nuclei critical,high only", params: { operation: "scan_target", severity: "critical,high" } },
  { pathway_id: "nuclei_templates_tech", method: "nuclei_templates", label: "nuclei technologies/", params: { operation: "scan_target", templates: "http/technologies/" } },
];

const FFUF_WORDLIST_ALTERNATES = [
  { pathway_id: "ffuf_common", method: "ffuf_wordlist", label: "ffuf common wordlist", params: { operation: "fuzz_url", wordlist: "/usr/share/wordlists/dirb/common.txt" } },
  { pathway_id: "ffuf_small", method: "ffuf_wordlist", label: "ffuf small wordlist", params: { operation: "fuzz_url", wordlist: "/usr/share/seclists/Discovery/Web-Content/common.txt" } },
  { pathway_id: "ffuf_vhost", method: "ffuf_vhost", label: "ffuf vhost discovery", params: { operation: "fuzz_vhost" } },
];

const SQLMAP_TEST_ALTERNATES = [
  { pathway_id: "sqlmap_get", method: "sqlmap_method", label: "sqlmap GET test", params: { operation: "test_url", method: "GET", level: 1, risk: 1 } },
  { pathway_id: "sqlmap_post", method: "sqlmap_method", label: "sqlmap POST test", params: { operation: "test_url", method: "POST", level: 1, risk: 1 } },
];

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function initInfluenceState(eng) {
  if (!eng) return;
  eng.influence_attempts = eng.influence_attempts || [];
}

function recordInfluenceAttempt(eng, attempt) {
  initInfluenceState(eng);
  const row = {
    ...attempt,
    ts: attempt.ts || new Date().toISOString(),
  };
  eng.influence_attempts.push(row);
  if (eng.influence_attempts.length > 200) {
    eng.influence_attempts = eng.influence_attempts.slice(-200);
  }
  return row;
}

function emitPathwayTerminal(broadcastTerminal, engagementId, message, level = "info") {
  if (!broadcastTerminal || !engagementId) return;
  broadcastTerminal(engagementId, `[pathway] ${message}`, level);
}

function emitPathwayCouncil(broadcastCouncil, engagementId, payload) {
  if (!broadcastCouncil || !engagementId) return;
  broadcastCouncil(engagementId, {
    type: "pathway_attempt",
    ...payload,
  });
}

function isGuidedPhasePlan(result) {
  if (!result || typeof result !== "object") return false;
  const hasNarrative =
    typeof result.narrative === "string" && result.narrative.trim().length > 0;
  const hasPlanFields =
    Array.isArray(result.recommended_actions) ||
    typeof result.phase_complete === "boolean" ||
    typeof result.invoke_hub === "boolean" ||
    typeof result.hub_operation === "string";
  const hasSource =
    typeof result.source === "string" &&
    /jailbreak|heuristic|api/i.test(result.source);
  return hasNarrative && (hasPlanFields || hasSource);
}

function isEmptyScannerOutcome(plugin, result) {
  const p = String(plugin || "").toLowerCase();
  if (!["nuclei", "ffuf"].includes(p)) return false;
  const r = result?.result?.output ?? result?.output ?? result?.result ?? result;
  const text = typeof r === "string" ? r : JSON.stringify(r || {});
  if (p === "nuclei") {
    if (/0 (?:match|finding|issue|results)|no results found/i.test(text)) return true;
    if (!/critical|high|CVE-\d{4}/i.test(text) && text.length < 800) return true;
  }
  if (p === "ffuf") {
    if (/404-only|no paths found/i.test(text)) return true;
    if ((text.match(/Status:\s*404/gi) || []).length > 5 && !/\/admin|\/api/i.test(text)) {
      return true;
    }
  }
  return false;
}

function isSuccessOutcome(result) {
  if (result == null) return false;
  if (result.success === false) return false;
  if (isGuidedPhasePlan(result)) return true;
  if (result.success === true) return true;
  if (result.status === "success") return true;
  if (result.status === "ready") return true;
  if (result.status === "failed" || result.status === "error") return false;
  if (result.output != null || result.result != null) return true;
  if (typeof result === "object" && result.fingerprint) return true;
  return false;
}

function getMaxPathwayAttempts(taskKind) {
  if (taskKind === "guided_phase") return GUIDED_PHASE_MAX_PATHWAY_ATTEMPTS;
  return INFLUENCE_MAX_PATHWAY_ATTEMPTS;
}

function buildScanAlternatePathways(primaryScanType) {
  const primary = primaryScanType || "quick";
  const alts = SCAN_PROFILE_ALTERNATES[primary] || ["comprehensive", "quick"];
  return alts.map((scan_type, i) => ({
    pathway_id: `scan_profile_${scan_type}`,
    method: "analyzer_scan_profile",
    label: `scan ${scan_type}`,
    params: { scan_type },
    sort: i,
  }));
}

function buildWebScannerAlternatePathways(plugin, primaryParams = {}) {
  const p = String(plugin || "").toLowerCase();
  const usedKey = JSON.stringify(primaryParams || {});
  if (p === "nuclei") {
    return NUCLEI_TEMPLATE_ALTERNATES.filter(
      (alt) => JSON.stringify(alt.params) !== usedKey
    );
  }
  if (p === "ffuf") {
    return FFUF_WORDLIST_ALTERNATES.filter(
      (alt) => JSON.stringify(alt.params) !== usedKey
    );
  }
  if (p === "sqlmap") {
    return SQLMAP_TEST_ALTERNATES.filter(
      (alt) => JSON.stringify(alt.params) !== usedKey
    );
  }
  return [];
}

function buildHubAlternatePathways(operation, primaryParams = {}) {
  if (operation !== "reconnaissance") {
    return [
      {
        pathway_id: "hub_op_retry",
        method: "hub_retry",
        label: `${operation} retry`,
        params: { ...primaryParams },
      },
    ];
  }
  const used = `${primaryParams.scan_type || ""}:${primaryParams.ports || ""}`;
  return HUB_RECON_ALTERNATES.filter((p) => {
    const key = `${p.params.scan_type}:${p.params.ports}`;
    return key !== used;
  });
}

function buildChainIndexPathways(eng, activeIndex = 0) {
  const chains = eng?.attack_chains?.chains || [];
  const scores =
    eng?.attack_chains?.alternate_chain_scores ||
    eng?.live_council?.last_grounding_pack?.alternate_chain_scores ||
    chains.map((c) => c.confidence ?? 0);

  const candidates = [];
  chains.forEach((chain, idx) => {
    if (idx === activeIndex || !chain?.steps?.length) return;
    candidates.push({
      pathway_id: `chain_index_${idx}`,
      method: "pivot_chain_index",
      label: `chain #${idx + 1} (score ${scores[idx] ?? "?"})`,
      params: { chain_index: idx },
      score: scores[idx] ?? chain.confidence ?? 0,
      requires_approval: false,
    });
  });
  candidates.sort((a, b) => (b.score || 0) - (a.score || 0));
  return candidates;
}

function buildToolAlternatePathways(step, recommendedTools = []) {
  const current =
    step?.tool ||
    step?.attack?.tools_used?.split?.(/[,\s]+/)?.[0] ||
    "custom";
  const tools = [...new Set([...(recommendedTools || []), "nuclei", "ffuf", "nmap", "sqlmap", "curl"])]
    .map((t) => String(t).trim().toLowerCase())
    .filter((t) => t && t !== String(current).toLowerCase());

  return tools.slice(0, 3).map((tool, i) => ({
    pathway_id: `alternate_tool_${tool}`,
    method: "alternate_tool",
    label: `tool ${tool}`,
    params: { tool },
    sort: i,
  }));
}

function buildJailbreakTemplatePathways() {
  return [1, 2].map((n) => ({
    pathway_id: `jailbreak_template_${n}`,
    method: "jailbreak_template_variant",
    label: `jailbreak template variant ${n}`,
    params: { template_variant: n, isolatedAttempt: n },
  }));
}

/**
 * Build alternate pathways for a given influence task kind.
 */
function buildAlternatePathways(kind, context = {}) {
  switch (kind) {
    case "scan":
      return buildScanAlternatePathways(context.primary_scan_type);
    case "hub":
      return buildHubAlternatePathways(context.operation, context.primary_params);
    case "chain_step":
      return [
        ...buildToolAlternatePathways(context.step, context.recommended_tools),
        ...buildJailbreakTemplatePathways(),
        ...buildChainIndexPathways(context.eng, context.chain_index ?? 0),
      ];
    case "jailbreak":
      return buildJailbreakTemplatePathways();
    case "guided_phase":
      // JSON repair handled inside jailbreak guided_phase_plan — no pathway alternates.
      return [];
    default:
      return [];
  }
}

/**
 * Run primary + alternate pathways until success or attempts exhausted.
 */
async function runWithInfluencePathways(options) {
  const {
    eng,
    engagementId,
    task_kind,
    task_id,
    context = {},
    executePrimary,
    executeAlternate,
    broadcastTerminal,
    broadcastCouncil,
    buildAlternates,
    shouldRetryOnEmpty,
  } = options;

  initInfluenceState(eng);
  const maxAttempts = getMaxPathwayAttempts(task_kind);
  const attempts = [];

  const runOne = async (pathway, index, total, isPrimary) => {
    const pathwayId = isPrimary ? "primary" : pathway.pathway_id;
    const method = isPrimary ? "primary" : pathway.method;
    const label = isPrimary ? "primary" : pathway.label;

    emitPathwayTerminal(
      broadcastTerminal,
      engagementId,
      `attempt ${index}/${total} — ${label} (${method})`,
      "command"
    );
    emitPathwayCouncil(broadcastCouncil, engagementId, {
      task_kind,
      task_id,
      attempt: index,
      max_attempts: total,
      pathway_id: pathwayId,
      method,
      label,
      status: "running",
    });

    let result;
    try {
      result = isPrimary
        ? await executePrimary()
        : await executeAlternate(pathway);
    } catch (err) {
      result = { success: false, error: err.message, status: "failed" };
    }

    const success = isSuccessOutcome(result);
    const outcome = success ? "success" : result?.status || "failed";

    recordInfluenceAttempt(eng, {
      engagement_id: engagementId,
      task_kind,
      task_id,
      pathway_id: pathwayId,
      method,
      label,
      outcome,
      attempt_index: index,
      max_attempts: total,
      error: result?.error || null,
    });

    emitPathwayTerminal(
      broadcastTerminal,
      engagementId,
      `attempt ${index}/${total} — ${label} — ${outcome}${success ? "" : " — trying next alternate"}`,
      success ? "success" : "warning"
    );
    emitPathwayCouncil(broadcastCouncil, engagementId, {
      task_kind,
      task_id,
      attempt: index,
      max_attempts: total,
      pathway_id: pathwayId,
      method,
      label,
      status: outcome,
    });

    attempts.push({ pathway_id: pathwayId, method, label, outcome, result });
    return { success, result, pathway_id: pathwayId };
  };

  const primary = await runOne(null, 1, maxAttempts, true);
  const emptyButOk =
    primary.success &&
    typeof shouldRetryOnEmpty === "function" &&
    shouldRetryOnEmpty(primary.result);
  if (primary.success && !emptyButOk) {
    return {
      success: true,
      result: primary.result,
      attempts,
      pathway_id: "primary",
    };
  }

  const alternates = buildAlternates
    ? buildAlternates(primary.result, context)
    : buildAlternatePathways(task_kind, context);

  const slotsLeft = maxAttempts - 1;
  const toTry = alternates.slice(0, slotsLeft);

  for (let i = 0; i < toTry.length; i++) {
    const pathway = toTry[i];
    if (pathway.requires_approval && LIVE_REQUIRE_APPROVAL) {
      eng.live_council = eng.live_council || {};
      eng.live_council.pending_pathway = {
        pathway,
        task_kind,
        task_id,
        rationale: `Alternate pathway requires approval: ${pathway.label}`,
      };
      emitPathwayTerminal(
        broadcastTerminal,
        engagementId,
        `attempt ${i + 2}/${maxAttempts} — ${pathway.label} — approval required (use Council approve)`,
        "warning"
      );
      if (broadcastCouncil) {
        broadcastCouncil(engagementId, {
          type: "pathway_approval_required",
          pathway,
          task_kind,
          task_id,
        });
      }
      continue;
    }

    if (INFLUENCE_PATHWAY_COOLDOWN_MS > 0) {
      await sleep(INFLUENCE_PATHWAY_COOLDOWN_MS);
    }

    const attemptNum = i + 2;
    const alt = await runOne(pathway, attemptNum, maxAttempts, false);
    if (alt.success) {
      return {
        success: true,
        result: alt.result,
        attempts,
        pathway_id: alt.pathway_id,
      };
    }
  }

  emitPathwayTerminal(
    broadcastTerminal,
    engagementId,
    `all ${maxAttempts} pathway attempt(s) exhausted for ${task_kind}`,
    "error"
  );

  return {
    success: false,
    result: primary.result,
    attempts,
    exhausted: true,
  };
}

/**
 * Retry a failed chain step via alternate tools / jailbreak variants before council.
 */
async function retryChainStepWithPathways(ctx) {
  const {
    eng,
    engagementId,
    step,
    step_number,
    chain_index,
    initialResult,
    executeStep,
    broadcastTerminal,
    broadcastCouncil,
  } = ctx;

  const recommended =
    initialResult?.attack_result?.tools_used ||
    initialResult?.jailbreak_guidance?.recommended_tools ||
    [];

  return runWithInfluencePathways({
    eng,
    engagementId,
    task_kind: "chain_step",
    task_id: `step_${step_number}`,
    context: {
      step,
      eng,
      chain_index,
      recommended_tools: Array.isArray(recommended) ? recommended : [],
    },
    broadcastTerminal,
    broadcastCouncil,
    executePrimary: async () => initialResult,
    executeAlternate: async (pathway) => {
      if (pathway.method === "pivot_chain_index") {
        return {
          success: false,
          status: "deferred",
          pivot_chain_index: pathway.params.chain_index,
          note: "chain pivot deferred to live council",
        };
      }
      const variantStep = { ...step, pathway_id: pathway.pathway_id };
      if (pathway.method === "alternate_tool" && pathway.params.tool) {
        variantStep.tool = pathway.params.tool;
        if (variantStep.command) {
          variantStep.command = variantStep.command.replace(
            /via \w+/i,
            `via ${pathway.params.tool}`
          );
        }
      }
      if (pathway.method === "jailbreak_template_variant") {
        return executeStep(variantStep, {
          isolatedAttempt: pathway.params.isolatedAttempt,
          pathway_id: pathway.pathway_id,
        });
      }
      return executeStep(variantStep, { pathway_id: pathway.pathway_id });
    },
    buildAlternates: (_failed, context) =>
      buildAlternatePathways("chain_step", context),
  });
}

module.exports = {
  INFLUENCE_MAX_PATHWAY_ATTEMPTS,
  GUIDED_PHASE_MAX_PATHWAY_ATTEMPTS,
  INFLUENCE_PATHWAY_COOLDOWN_MS,
  initInfluenceState,
  recordInfluenceAttempt,
  buildAlternatePathways,
  buildScanAlternatePathways,
  buildHubAlternatePathways,
  buildWebScannerAlternatePathways,
  buildChainIndexPathways,
  runWithInfluencePathways,
  retryChainStepWithPathways,
  emitPathwayTerminal,
  isSuccessOutcome,
  isEmptyScannerOutcome,
  isGuidedPhasePlan,
  getMaxPathwayAttempts,
};
