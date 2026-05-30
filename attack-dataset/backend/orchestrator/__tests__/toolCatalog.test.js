"use strict";

const { describe, it, before, after } = require("node:test");
const assert = require("node:assert/strict");

const {
  buildFullCatalog,
  METASPLOIT_TOOLS,
  NUCLEI_TOOLS,
  FFUF_TOOLS,
  SQLMAP_TOOLS,
  BURP_MCP_TOOLS,
  MCP_BURP_PLUGIN,
  validateToolCall,
  filterToolCallsByPolicy,
  normalizeToolCall,
  defaultToolsForPhase,
  buildRunSummary,
} = require("../toolCatalog");

describe("toolCatalog metasploit", () => {
  it("includes metasploit static entries in full catalog", () => {
    const catalog = buildFullCatalog({
      plugins: [
        {
          name: "metasploit",
          description: "Metasploit Framework",
          capabilities: ["list_modules", "run_auxiliary"],
          healthy: true,
          enabled: true,
        },
      ],
      status: "healthy",
    });

    const msfIds = METASPLOIT_TOOLS.map((t) => t.id);
    for (const id of msfIds) {
      assert.ok(catalog.entries.some((e) => e.id === id));
    }
    assert.ok(catalog.entries.some((e) => e.plugin === "metasploit"));
  });

  it("validates metasploit tool call", () => {
    const catalog = buildFullCatalog({ plugins: [], status: "healthy" });
    const v = validateToolCall(
      {
        plugin: "metasploit",
        tool: "list_modules",
        params: { operation: "list_modules" },
      },
      catalog
    );
    assert.equal(v.valid, true);
    assert.equal(v.normalized.plugin, "metasploit");
  });

  it("allows metasploit exploit without roe or web_only gates", () => {
    const call = {
      plugin: "metasploit",
      tool: "run_exploit",
      params: { operation: "run_exploit" },
      _entry: METASPLOIT_TOOLS.find((t) => t.tool === "run_exploit"),
    };
    const { allowed, blocked } = filterToolCallsByPolicy([call], {
      webOnly: true,
      roeAcknowledged: false,
      aggressionLevel: 5,
    });
    assert.equal(blocked.length, 0);
    assert.equal(allowed.length, 1);
  });

  it("allows metasploit exploit when ALLOW_HIGH_RISK bypasses council approval", () => {
    const call = {
      plugin: "metasploit",
      tool: "run_exploit",
      params: { operation: "run_exploit" },
      _entry: METASPLOIT_TOOLS.find((t) => t.tool === "run_exploit"),
    };
    const { allowed } = filterToolCallsByPolicy([call], {
      webOnly: false,
      roeAcknowledged: true,
      liveRequireApproval: true,
      councilApproved: false,
    });
    assert.equal(allowed.length, 1);
  });
});

describe("toolCatalog web scanners", () => {
  it("includes nuclei, ffuf, and sqlmap static entries", () => {
    const catalog = buildFullCatalog({ plugins: [], status: "healthy" });
    for (const id of [
      ...NUCLEI_TOOLS.map((t) => t.id),
      ...FFUF_TOOLS.map((t) => t.id),
      ...SQLMAP_TOOLS.map((t) => t.id),
    ]) {
      assert.ok(catalog.entries.some((e) => e.id === id), `missing ${id}`);
    }
  });

  it("allows nuclei and ffuf without roe_acknowledged", () => {
    for (const plugin of ["nuclei", "ffuf"]) {
      const call = normalizeToolCall(
        {
          plugin,
          tool: plugin === "nuclei" ? "scan_target" : "fuzz_url",
          params: {
            operation: plugin === "nuclei" ? "scan_target" : "fuzz_url",
          },
        },
        plugin === "nuclei" ? NUCLEI_TOOLS[0] : FFUF_TOOLS[0]
      );
      const { allowed, blocked } = filterToolCallsByPolicy([call], {
        webOnly: true,
        roeAcknowledged: false,
      });
      assert.equal(blocked.length, 0, `${plugin} should not be policy-blocked`);
      assert.equal(allowed.length, 1);
    }
  });

  it("allows sqlmap without roe_acknowledged", () => {
    const call = normalizeToolCall(
      { plugin: "sqlmap", tool: "test_url", params: { operation: "test_url" } },
      SQLMAP_TOOLS[0]
    );
    const { allowed, blocked } = filterToolCallsByPolicy([call], {
      webOnly: true,
      roeAcknowledged: false,
    });
    assert.equal(blocked.length, 0);
    assert.equal(allowed.length, 1);
  });
});

describe("toolCatalog mcp burp", () => {
  const prev = { ...process.env };

  before(() => {
    process.env.MCP_MOCK = "1";
    process.env.MCP_BURP_ENABLED = "1";
  });

  after(() => {
    process.env = prev;
    delete require.cache[require.resolve("../mcpClient")];
    delete require.cache[require.resolve("../toolCatalog")];
  });

  it("includes burp static entries when MCP_BURP_ENABLED", () => {
    delete require.cache[require.resolve("../toolCatalog")];
    const { buildFullCatalog: build } = require("../toolCatalog");
    const catalog = build({ plugins: [], status: "healthy" });
    for (const id of BURP_MCP_TOOLS.map((t) => t.id).slice(0, 4)) {
      assert.ok(catalog.entries.some((e) => e.id === id), `missing ${id}`);
    }
  });

  it("validates burp send_request alias", () => {
    const catalog = buildFullCatalog({ plugins: [], status: "healthy" });
    const v = validateToolCall(
      {
        plugin: MCP_BURP_PLUGIN,
        tool: "send_request",
        params: { content: "GET / HTTP/1.1\r\n\r\n" },
      },
      catalog
    );
    assert.equal(v.valid, true);
    assert.equal(v.normalized.params.mcp_tool, "send_http1_request");
  });

  it("allows active burp tool without roe", () => {
    const call = normalizeToolCall(
      { plugin: MCP_BURP_PLUGIN, tool: "send_http1_request" },
      BURP_MCP_TOOLS.find((t) => t.tool === "send_http1_request")
    );
    const { allowed, blocked } = filterToolCallsByPolicy([call], {
      webOnly: true,
      roeAcknowledged: false,
    });
    assert.equal(blocked.length, 0);
    assert.equal(allowed.length, 1);
  });

  it("allows passive proxy history in web_only without roe", () => {
    const call = normalizeToolCall(
      { plugin: MCP_BURP_PLUGIN, tool: "get_proxy_history" },
      BURP_MCP_TOOLS.find((t) => t.tool === "get_proxy_history")
    );
    const { allowed } = filterToolCallsByPolicy([call], {
      webOnly: true,
      roeAcknowledged: false,
    });
    assert.equal(allowed.length, 1);
  });
});

describe("defaultToolsForPhase", () => {
  it("returns nuclei/ffuf for recon phases on web targets", () => {
    const calls = defaultToolsForPhase(2, "https://example.com", { webOnly: true });
    assert.ok(calls.some((c) => c.plugin === "nuclei"));
    assert.ok(calls.some((c) => c.plugin === "ffuf"));
  });

  it("returns KE attack-vector and sqlmap for evaluate phase on web targets (high aggression)", () => {
    const calls = defaultToolsForPhase(4, "https://example.com", {
      webOnly: true,
      aggressionLevel: 8,
    });
    assert.ok(calls.some((c) => c.plugin === "knowledge_engine" && c.tool === "attack-vector"));
    assert.ok(calls.some((c) => c.plugin === "sqlmap"));
  });

  it("omits sqlmap on phase 4 when aggression is low", () => {
    const calls = defaultToolsForPhase(4, "https://example.com", {
      webOnly: true,
      aggressionLevel: 4,
    });
    assert.ok(calls.some((c) => c.plugin === "knowledge_engine"));
    assert.ok(!calls.some((c) => c.plugin === "sqlmap"));
  });
});

describe("buildRunSummary", () => {
  it("aggregates phase and council stats", () => {
    const eng = {
      status: "complete",
      guided_autonomous: {
        status: "complete",
        phases: [
          { phase_number: 1, status: "complete", tool_results: [{ success: true, plugin: "nuclei" }] },
        ],
      },
      live_council: { turn: 3, directives: [{ approved_at: "2026-01-01" }] },
      influence_attempts: [{}, {}],
    };
    const summary = buildRunSummary(eng, { toolsInvokedCount: 2, phaseRecords: eng.guided_autonomous.phases });
    assert.equal(summary.phases_completed, 1);
    assert.equal(summary.tools_invoked_count, 2);
    assert.equal(summary.pathway_attempts_count, 2);
    assert.equal(summary.council_turns, 3);
    assert.ok(summary.tools_used.includes("nuclei"));
  });
});
