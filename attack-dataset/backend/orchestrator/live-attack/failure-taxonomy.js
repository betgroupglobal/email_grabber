"use strict";

/**
 * Classify step/method failures to drive council directive selection.
 */
const FAILURE_CLASSES = [
  "tool_blocked",
  "auth_failed",
  "timeout",
  "wrong_vector",
  "detection_signal",
  "unknown",
];

const PATTERNS = [
  {
    class: "tool_blocked",
    re: /403|forbidden|blocked|waf|firewall|denied|not allowed|access denied/i,
  },
  {
    class: "auth_failed",
    re: /401|unauthorized|authentication|login failed|invalid credentials|password|auth/i,
  },
  {
    class: "timeout",
    re: /timeout|timed out|ETIMEDOUT|deadline|connection reset|ECONNRESET/i,
  },
  {
    class: "detection_signal",
    re: /detected|alert|ids|ips|honeypot|blocked by|rate.?limit|429/i,
  },
  {
    class: "wrong_vector",
    re: /not found|404|no route|unsupported|invalid target|wrong port|connection refused/i,
  },
];

function classifyFailure(trigger) {
  const output = String(
    trigger?.step_result?.output ||
      trigger?.method_result?.output ||
      trigger?.last_failure?.output ||
      ""
  );
  const tool =
    trigger?.step?.tool ||
    trigger?.step_result?.chain_attack_methods?.find((m) => !m.success)?.tool ||
    trigger?.last_failure?.tool ||
    "";

  const haystack = `${output} tool:${tool}`;

  for (const { class: failureClass, re } of PATTERNS) {
    if (re.test(haystack)) {
      return {
        failure_class: failureClass,
        confidence: 0.75,
        evidence: haystack.slice(0, 300),
        failed_tool: tool || null,
      };
    }
  }

  const isFailure =
    trigger?.type === "step_failed" ||
    trigger?.type === "method_failed" ||
    trigger?.step_result?.status === "failed";

  return {
    failure_class: isFailure ? "unknown" : "none",
    confidence: isFailure ? 0.4 : 1.0,
    evidence: haystack.slice(0, 200) || null,
    failed_tool: tool || null,
  };
}

function suggestActionForFailure(failureClass, triggerType) {
  if (triggerType === "step_completed" || failureClass === "none") {
    return "continue";
  }
  switch (failureClass) {
    case "tool_blocked":
    case "detection_signal":
      return "reinitiate_chain";
    case "auth_failed":
      return "patch_chain";
    case "timeout":
      return "patch_chain";
    case "wrong_vector":
      return "pivot_chain";
    default:
      return "reinitiate_chain";
  }
}

module.exports = {
  FAILURE_CLASSES,
  classifyFailure,
  suggestActionForFailure,
};
