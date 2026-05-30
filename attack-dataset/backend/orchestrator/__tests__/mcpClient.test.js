"use strict";

const { describe, it, before, after } = require("node:test");
const assert = require("node:assert/strict");

describe("mcpClient mock mode", () => {
  const prev = { ...process.env };

  before(() => {
    process.env.MCP_MOCK = "1";
    process.env.MCP_BURP_ENABLED = "1";
  });

  after(() => {
    process.env = prev;
    delete require.cache[require.resolve("../mcpClient")];
    delete require.cache[require.resolve("../mcpBurpTools")];
  });

  it("lists mock burp tools", async () => {
    delete require.cache[require.resolve("../mcpClient")];
    const { listTools, getMcpStatus } = require("../mcpClient");
    const { tools } = await listTools("burp");
    assert.ok(tools.length >= 3);
    assert.ok(tools.some((t) => t.name === "get_proxy_http_history"));
    const status = getMcpStatus();
    assert.equal(status.mock, true);
    assert.equal(status.burp_enabled, true);
  });

  it("calls mock send_http1_request", async () => {
    delete require.cache[require.resolve("../mcpClient")];
    const { callTool } = require("../mcpClient");
    const result = await callTool("burp", "send_http1_request", {
      content: "GET / HTTP/1.1\r\nHost: example.com\r\n\r\n",
      targetHostname: "example.com",
      targetPort: 443,
      usesHttps: true,
    });
    assert.ok(result.terminal_lines?.length);
    assert.match(String(result.text || ""), /mock|HTTP/i);
  });
});
