"use strict";

const {
  fetchHubToolCatalog,
  formatCatalogForPrompt,
  catalogSummaryForGrounding,
} = require("./toolCatalog");
const { executeToolCalls } = require("./toolExecutor");
const { summarizeToolOutcomes } = require("./toolOutcomeSummarizer");

const ASSISTANT_AGENT_MAX_ROUNDS = Math.max(
  1,
  parseInt(process.env.ASSISTANT_AGENT_MAX_ROUNDS || "3", 10)
);

async function runAssistantAgentChat(deps, opts) {
  const {
    axios,
    INTEGRATION_HUB_URL,
    ANALYZER_URL,
    KNOWLEDGE_ENGINE,
    getServiceAuthHeaders,
    callJailbreakHubExecute,
    liveAttack,
  } = deps;
  const {
    messages,
    target,
    rag_context,
    engagement_context,
    broadcastTerminal,
  } = opts;

  const catalog = await fetchHubToolCatalog(
    INTEGRATION_HUB_URL,
    axios,
    getServiceAuthHeaders()
  );
  if (!catalog?.entries?.length) {
    return null;
  }

  const catalogPrompt = formatCatalogForPrompt(catalog, {
    webOnly: true,
    aggressionLevel: 7,
    maxEntries: parseInt(process.env.TOOL_CATALOG_PROMPT_MAX || "24", 10),
  });

  const toolsUsed = [];
  let toolResultsSummary = "";
  const loopMessages = [...messages];
  let finalAnswer = "";
  let rounds = 0;
  let lastSource = "jailbreak_api";

  const fakeEng = {
    target: target || engagement_context?.target || "unknown",
    aggression_level: 7,
    guided_autonomous: { web_only: true, roe_acknowledged: true },
  };
  const ctx = {
    webOnly: true,
    aggressionLevel: 7,
    roeAcknowledged: true,
    priorFindings: "",
  };

  for (let round = 1; round <= ASSISTANT_AGENT_MAX_ROUNDS; round++) {
    rounds = round;
    const hubData = await callJailbreakHubExecute({
      plugin_name: "jailbreak_ai",
      engagement_id: engagement_context?.engagement_id || null,
      target: fakeEng.target,
      parameters: {
        operation: "assistant_agent",
        messages: loopMessages,
        target: fakeEng.target,
        round,
        tool_catalog_prompt: catalogPrompt,
        tool_catalog: catalogSummaryForGrounding(catalog),
        tool_results_summary: toolResultsSummary,
        rag_context: rag_context || "",
        web_only: true,
        aggression_level: 7,
      },
      timeout: 120,
    });

    if (!hubData?.success) {
      throw new Error(hubData?.error || "assistant_agent failed");
    }

    const output = hubData.output && typeof hubData.output === "object" ? hubData.output : {};
    lastSource = output.source || output.ai_source || "jailbreak_api";
    const toolCalls = Array.isArray(output.tool_calls) ? output.tool_calls : [];

    if (output.answer_partial) {
      finalAnswer = output.answer_partial;
    }
    if (output.answer) {
      finalAnswer = output.answer;
    }

    if (output.done || !toolCalls.length) {
      return {
        answer: finalAnswer || output.answer_partial || "No response from assistant.",
        tools_used: toolsUsed,
        rounds,
        source: lastSource,
      };
    }

    const exec = await executeToolCalls(
      {
        axios,
        INTEGRATION_HUB_URL,
        ANALYZER_URL,
        KNOWLEDGE_ENGINE,
        getServiceAuthHeaders,
        liveAttack,
      },
      {
        calls: toolCalls,
        catalog,
        engagementId: engagement_context?.engagement_id || "ai-chat",
        eng: fakeEng,
        ctx,
        broadcastTerminal,
      }
    );

    for (const r of exec.results || []) {
      toolsUsed.push({
        plugin: r.plugin,
        tool: r.tool,
        success: r.success,
      });
    }

    toolResultsSummary = summarizeToolOutcomes({
      tool_results: exec.results || [],
    });
    loopMessages.push({
      role: "assistant",
      content: JSON.stringify({
        tool_calls: toolCalls,
        answer_partial: output.answer_partial || "",
      }),
    });
    loopMessages.push({
      role: "user",
      content: `Tool results:\n${toolResultsSummary || "(no summary)"}`,
    });
  }

  return {
    answer:
      finalAnswer ||
      "Reached maximum tool rounds; partial results may be in prior tool summaries.",
    tools_used: toolsUsed,
    rounds,
    source: lastSource,
  };
}

module.exports = {
  runAssistantAgentChat,
  ASSISTANT_AGENT_MAX_ROUNDS,
};
