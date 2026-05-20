#!/usr/bin/env node
import { runCloudAgent } from "../cloud-agent";
import { CursorAgentError } from "@cursor/sdk";

const prompt = process.argv.slice(2).join(" ").trim();
if (!prompt) {
  console.error("Usage: npx tsx scripts/run-cloud-agent.ts <prompt>");
  console.error('Example: npx tsx scripts/run-cloud-agent.ts "Analyze attack patterns in backend/knowledge_engine"');
  process.exit(1);
}

async function main() {
  try {
    const result = await runCloudAgent(prompt, {
      autoCreatePR: process.env.AUTO_CREATE_PR === "true",
      skipReviewerRequest: true,
    });

    console.log("\n--- Result ---");
    console.log(`Status: ${result.status}`);
    console.log(`Agent ID: ${result.agentId}`);
    console.log(`Run ID: ${result.runId}`);
    if (result.durationMs) {
      console.log(`Duration: ${result.durationMs}ms`);
    }
    if (result.result) {
      console.log(`\nOutput:\n${result.result}`);
    }

    process.exit(result.status === "finished" ? 0 : 2);
  } catch (err) {
    if (err instanceof CursorAgentError) {
      console.error("Cursor Agent Error:", err.message);
      console.error("Retryable:", err.isRetryable);
    } else {
      console.error("Failed:", err);
    }
    process.exit(1);
  }
}

main();
