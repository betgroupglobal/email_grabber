import { Agent, CursorAgentError } from "@cursor/sdk";
import "dotenv/config";

function getApiKey(): string {
  const apiKey = process.env.CURSOR_API_KEY;
  if (!apiKey) {
    throw new Error("Missing CURSOR_API_KEY. Get one at https://cursor.com/dashboard/cloud-agents");
  }
  return apiKey;
}

const REPO_URL = process.env.REPO_URL || "https://github.com/your-org/attack-dataset";

export interface CloudAgentResult {
  agentId: string;
  runId: string;
  status: "finished" | "error" | "cancelled";
  durationMs?: number;
  result?: string;
}

/**
 * Run a cloud agent with the given prompt
 */
export async function runCloudAgent(prompt: string, options?: {
  startingRef?: string;
  autoCreatePR?: boolean;
  skipReviewerRequest?: boolean;
}): Promise<CloudAgentResult> {
  const { startingRef = "main", autoCreatePR = false, skipReviewerRequest = true } = options || {};

  const agent = await Agent.create({
    apiKey: getApiKey(),
    model: { id: "composer-2" },
    cloud: {
      repos: [{ url: REPO_URL, startingRef }],
      autoCreatePR,
      skipReviewerRequest,
    },
  });

  console.log(`[cloud-agent] Created agent: ${agent.agentId}`);

  try {
    const run = await agent.send(prompt);
    console.log(`[cloud-agent] Run started: ${run.id}`);

    // Stream events for observability
    for await (const event of run.stream()) {
      if (event.type === "status") {
        console.log(`[cloud-agent] Status: ${event.status}`);
      }
      if (event.type === "tool_call" && event.status !== "running") {
        console.log(`[cloud-agent] Tool ${event.name}: ${event.status}`);
      }
    }

    const result = await run.wait();
    
    // Cleanup
    await agent[Symbol.asyncDispose]();
    
    return {
      agentId: agent.agentId,
      runId: result.id,
      status: result.status,
      durationMs: result.durationMs,
      result: result.result,
    };
  } catch (err) {
    await agent[Symbol.asyncDispose]();
    if (err instanceof CursorAgentError) {
      console.error(`[cloud-agent] Startup failed: ${err.message}`);
      console.error(`[cloud-agent] Retryable: ${err.isRetryable}`);
      throw err;
    }
    throw err;
  }
}

/**
 * Resume an existing cloud agent
 */
export async function resumeCloudAgent(agentId: string, prompt: string): Promise<CloudAgentResult> {
  const agent = await Agent.resume(agentId, {
    apiKey: getApiKey(),
    model: { id: "composer-2" },
    cloud: {
      repos: [{ url: REPO_URL, startingRef: "main" }],
    },
  });

  console.log(`[cloud-agent] Resumed agent: ${agent.agentId}`);

  try {
    const run = await agent.send(prompt);
    const result = await run.wait();
    
    // Cleanup
    await agent[Symbol.asyncDispose]();
    
    return {
      agentId: agent.agentId,
      runId: result.id,
      status: result.status,
      durationMs: result.durationMs,
      result: result.result,
    };
  } catch (err) {
    await agent[Symbol.asyncDispose]();
    if (err instanceof CursorAgentError) {
      console.error(`[cloud-agent] Resume failed: ${err.message}`);
      throw err;
    }
    throw err;
  }
}
