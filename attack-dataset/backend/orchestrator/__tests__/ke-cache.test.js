"use strict";

const { describe, it } = require("node:test");
const assert = require("node:assert/strict");
const {
  getCachedSearch,
  formatSearchHitsForRag,
  rerankHitsByTargetKeywords,
  clearKeCache,
} = require("../ke-cache");

describe("ke-cache", () => {
  it("caches search results by query+target", async () => {
    clearKeCache();
    let calls = 0;
    const fetchFn = async () => {
      calls += 1;
      return {
        results: [
          { record: { title: "Web XSS", scenario_description: "reflected xss" }, score: 0.5 },
        ],
      };
    };

    const first = await getCachedSearch({
      query: "web app test",
      target: "mobileciti.com.au",
      fetchFn,
      ttlMs: 60_000,
    });
    const second = await getCachedSearch({
      query: "web app test",
      target: "mobileciti.com.au",
      fetchFn,
      ttlMs: 60_000,
    });

    assert.equal(calls, 1);
    assert.equal(first.cache_hit, false);
    assert.equal(second.cache_hit, true);
    assert.ok(first.rag_context.includes("Web XSS"));
  });

  it("reranks hits using target host tokens", () => {
    const hits = [
      { record: { title: "Satellite jam", category: "radio" }, score: 0.55 },
      { record: { title: "mobileciti checkout XSS", category: "web" }, score: 0.5 },
    ];
    const ranked = rerankHitsByTargetKeywords(hits, "mobileciti.com.au");
    assert.ok(ranked[0].record.title.includes("mobileciti"));
  });

  it("formats rag context compactly", () => {
    const text = formatSearchHitsForRag([
      { record: { title: "SQLi", scenario_description: "injection test" }, score: 0.8 },
    ]);
    assert.match(text, /SQLi/);
    assert.match(text, /relevance 0.8/);
  });
});
