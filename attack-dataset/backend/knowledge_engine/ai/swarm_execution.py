from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger("swarm_execution")


@dataclass
class SwarmTask:
    worker: str
    tool: str
    input: Dict[str, Any]
    reason: str


class SwarmExecutionModule:
    def __init__(self, tool_executor: Callable[[str, Dict[str, Any]], Dict[str, Any]]):
        self._exec = tool_executor

    @staticmethod
    def _compact(obj: Any, limit: int = 900) -> str:
        try:
            s = json.dumps(obj, ensure_ascii=False)
        except Exception:
            s = str(obj)
        if len(s) <= limit:
            return s
        return s[:limit] + "…"

    @staticmethod
    def _normalize_services(engagement_context: Optional[Dict[str, Any]]) -> List[str]:
        if not engagement_context:
            return []
        services: List[str] = []
        for chain in engagement_context.get("chains", [])[:2]:
            for step in chain.get("steps", [])[:8]:
                attack = step.get("attack", {})
                raw = str(attack.get("tools_used", "")).strip()
                if raw:
                    services.append(raw[:120])
        # dedupe stable order
        seen = set()
        out = []
        for s in services:
            if s not in seen:
                seen.add(s)
                out.append(s)
        return out[:20]

    def _plan(
        self,
        question: str,
        engagement_context: Optional[Dict[str, Any]],
        allow_tools: bool,
    ) -> List[SwarmTask]:
        if not allow_tools:
            return []

        q = question.lower()
        tasks: List[SwarmTask] = []

        # Retriever baseline
        tasks.append(
            SwarmTask(
                worker="retriever",
                tool="semantic_search",
                input={"query": question, "top_k": 8},
                reason="Retrieve nearest attack records for grounding",
            )
        )

        needs_mitre = "mitre" in q or "technique" in q or "tactic" in q
        needs_tool_risk = "tool" in q or "opsec" in q or "detect" in q or "evasion" in q
        needs_chain = "chain" in q or "path" in q or "vector" in q or "attack plan" in q
        needs_categories = "category" in q or "categories" in q or "breakdown" in q
        needs_target = "target type" in q or "target" in q

        if needs_categories:
            tasks.append(
                SwarmTask(
                    worker="retriever",
                    tool="list_categories",
                    input={"limit": 15},
                    reason="Provide category-level aggregate evidence",
                )
            )

        if needs_target:
            tasks.append(
                SwarmTask(
                    worker="retriever",
                    tool="attacks_by_target",
                    input={"target_type": "server", "limit": 20},
                    reason="Capture target-type specific options",
                )
            )

        if needs_mitre:
            tasks.append(
                SwarmTask(
                    worker="retriever",
                    tool="attacks_by_mitre",
                    input={"technique_id": "T1059", "limit": 15},
                    reason="Include MITRE-mapped evidence set",
                )
            )

        if needs_chain:
            services = self._normalize_services(engagement_context)
            tasks.append(
                SwarmTask(
                    worker="chain_builder",
                    tool="build_attack_vector",
                    input={
                        "target_description": question[:220],
                        "detected_services": services,
                        "top_chains": 3,
                    },
                    reason="Generate ranked attack chains aligned to user intent",
                )
            )

        if needs_tool_risk:
            tasks.append(
                SwarmTask(
                    worker="opsec",
                    tool="list_tools",
                    input={"limit": 8},
                    reason="Find likely candidate tools for risk recommendations",
                )
            )

        return tasks

    def _run_tasks(self, tasks: List[SwarmTask], max_steps: int) -> Dict[str, Any]:
        trace: List[Dict[str, Any]] = []
        evidence: Dict[str, Any] = {}

        for idx, task in enumerate(tasks[:max_steps], start=1):
            try:
                result = self._exec(task.tool, task.input)
                status = "ok"
            except Exception as e:
                result = {"error": str(e)}
                status = "error"
            trace.append(
                {
                    "step": idx,
                    "worker": task.worker,
                    "tool": task.tool,
                    "reason": task.reason,
                    "status": status,
                    "input": task.input,
                    "result_preview": self._compact(result, limit=700),
                }
            )
            evidence[task.tool] = result

            if task.tool == "list_tools" and status == "ok":
                tools = (result or {}).get("tools", [])
                if tools:
                    top_tool = tools[0].get("tool")
                    if top_tool:
                        try:
                            opsec_res = self._exec(
                                "opsec_tool_recommendations",
                                {"tool_name": top_tool},
                            )
                            trace.append(
                                {
                                    "step": len(trace) + 1,
                                    "worker": "opsec",
                                    "tool": "opsec_tool_recommendations",
                                    "reason": "Expand highest-frequency tool with OpSec profile",
                                    "status": "ok",
                                    "input": {"tool_name": top_tool},
                                    "result_preview": self._compact(opsec_res, limit=700),
                                }
                            )
                            evidence["opsec_tool_recommendations"] = opsec_res
                        except Exception as e:
                            trace.append(
                                {
                                    "step": len(trace) + 1,
                                    "worker": "opsec",
                                    "tool": "opsec_tool_recommendations",
                                    "reason": "Expand highest-frequency tool with OpSec profile",
                                    "status": "error",
                                    "input": {"tool_name": top_tool},
                                    "result_preview": self._compact({"error": str(e)}, limit=700),
                                }
                            )

            if task.tool == "build_attack_vector" and status == "ok":
                chains = (result or {}).get("chains", [])
                if chains:
                    top_chain = chains[0]
                    steps = [f"{s.get('phase','')}: {s.get('title','')}" for s in top_chain.get("steps", []) if s.get("title")]
                    if steps:
                        try:
                            audit_res = self._exec(
                                "opsec_audit_chain",
                                {
                                    "chain_id": top_chain.get("chain_id", "swarm-chain"),
                                    "chain_description": "Generated by swarm execution",
                                    "steps": steps[:12],
                                },
                            )
                            trace.append(
                                {
                                    "step": len(trace) + 1,
                                    "worker": "opsec",
                                    "tool": "opsec_audit_chain",
                                    "reason": "Assess detectability for generated top chain",
                                    "status": "ok",
                                    "input": {"steps": steps[:12]},
                                    "result_preview": self._compact(audit_res, limit=700),
                                }
                            )
                            evidence["opsec_audit_chain"] = audit_res
                        except Exception as e:
                            trace.append(
                                {
                                    "step": len(trace) + 1,
                                    "worker": "opsec",
                                    "tool": "opsec_audit_chain",
                                    "reason": "Assess detectability for generated top chain",
                                    "status": "error",
                                    "input": {"steps": steps[:12]},
                                    "result_preview": self._compact({"error": str(e)}, limit=700),
                                }
                            )

        return {"trace": trace, "evidence": evidence}

    @staticmethod
    def _summarize(question: str, run_output: Dict[str, Any]) -> str:
        trace = run_output.get("trace", [])
        evidence = run_output.get("evidence", {})

        lines = [
            "## Swarm Execution Summary",
            f"Question: {question}",
            "",
            f"- Tasks executed: {len(trace)}",
            f"- Evidence sources: {', '.join(sorted(evidence.keys())) if evidence else 'none'}",
            "",
            "### Key Results",
        ]

        if "semantic_search" in evidence:
            sem = evidence["semantic_search"]
            lines.append(f"- Semantic search results: {sem.get('total', 0)} matches")
        if "build_attack_vector" in evidence:
            vec = evidence["build_attack_vector"]
            lines.append(f"- Generated attack chains: {vec.get('total_chains', 0)}")
        if "opsec_audit_chain" in evidence:
            audit = evidence["opsec_audit_chain"]
            lines.append(
                f"- OpSec chain risk: {audit.get('overall_risk_level', 'unknown')} "
                f"({audit.get('overall_risk_score', 'n/a')}/100)"
            )
        if "opsec_tool_recommendations" in evidence:
            tool = evidence["opsec_tool_recommendations"]
            lines.append(
                f"- Tool OpSec profile: {tool.get('tool', 'unknown')} "
                f"risk={tool.get('risk_level', 'unknown')}"
            )

        lines += [
            "",
            "### Task Trace",
        ]
        for t in trace[:12]:
            lines.append(
                f"- [{t.get('status')}] {t.get('worker')} → {t.get('tool')}: {t.get('reason')}"
            )

        return "\n".join(lines)

    def run(
        self,
        question: str,
        history: List[Dict[str, str]],
        engagement_context: Optional[Dict[str, Any]] = None,
        allow_tools: bool = True,
        max_steps: int = 12,
    ) -> str:
        try:
            tasks = self._plan(
                question=question,
                engagement_context=engagement_context,
                allow_tools=allow_tools,
            )
            run_output = self._run_tasks(tasks=tasks, max_steps=max_steps)
            return self._summarize(question=question, run_output=run_output)
        except Exception as e:
            log.exception("Swarm execution failed")
            return f"Swarm execution failed: {e}"
