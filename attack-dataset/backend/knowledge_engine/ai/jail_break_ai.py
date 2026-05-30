"""
Claude Analyst — AI-powered intelligence layer (Jailbreak AI-compatible).

Provides three capabilities:
  1. analyse_engagement()  — narrative report over a full engagement
  2. analyse_chain()       — deep-dive on a single attack chain
  3. chat()                — RAG-grounded streaming Q&A
"""
from __future__ import annotations

import sys
import os
# Add parent directory to path to import shared modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import json
import logging
from typing import AsyncIterator, List, Optional, Dict, Any

from openai import OpenAI

from ..search.attack_chainer import AttackChainer
from ..utils.config import JAILBREAK_API_KEY, JAILBREAK_MODEL, JAILBREAK_BASE_URL
from ..core.models import AttackRecord, AttackChain, AttackVectorRequest, AttackVectorResponse
from ..utils.opsec_audit import OpSecAuditEngine
from ..search.searcher import AttackSearcher
from .swarm_execution import SwarmExecutionModule

log = logging.getLogger("claude_analyst")

# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are an expert offensive security analyst and red team operator.
You have deep knowledge of MITRE ATT&CK, penetration testing methodologies,
network exploitation, web application attacks, privilege escalation, and
operational security (OpSec).

You assist security professionals conducting authorised penetration tests.
You have access to a knowledge base of 14,000+ attack techniques and scenarios.

When analysing attack chains:
- Be precise and technical
- Highlight the highest-risk steps and why
- Flag any OpSec concerns that could burn the operation
- Suggest concrete improvements or alternatives
- Map everything to MITRE ATT&CK where relevant

When answering questions:
- Ground your answers in the provided attack knowledge context
- Be direct and operational — avoid generic security advice
- Format your output clearly with headers and bullet points where helpful
- Use available tools when needed to retrieve exact records and OpSec recommendations
"""


def _format_chain_for_claude(chain: Dict[str, Any]) -> str:
    """Serialise an attack chain dict into a compact readable block."""
    lines = [
        f"Chain ID: {chain.get('chain_id', 'N/A')}",
        f"Confidence: {chain.get('confidence', 0):.0%}",
        f"Target: {chain.get('target_description', '')}",
        f"Estimated Impact: {chain.get('estimated_impact', '')[:200]}",
        "",
        "Steps:",
    ]
    for step in chain.get("steps", []):
        atk = step.get("attack", {})
        lines += [
            f"  [{step.get('phase', '?')}] {atk.get('title', '')}",
            f"    Type: {atk.get('attack_type', '')}",
            f"    MITRE: {atk.get('mitre_technique', '')}",
            f"    Tools: {atk.get('tools_used', '')[:120]}",
            f"    Impact: {atk.get('impact', '')[:120]}",
            f"    Detection: {atk.get('detection_method', '')[:120]}",
            "",
        ]
    lines.append(f"OpSec Notes: {chain.get('opsec_notes', '')}")
    return "\n".join(lines)


def _format_records_for_context(records: List[AttackRecord]) -> str:
    """Format retrieved attack records as Claude context."""
    parts = []
    for r in records[:8]:  # cap at 8 to stay within context budget
        parts.append(
            f"[{r.id}] {r.title} ({r.category})\n"
            f"  Type: {r.attack_type}\n"
            f"  MITRE: {r.mitre_technique}\n"
            f"  Scenario: {r.scenario_description[:300]}\n"
            f"  Tools: {r.tools_used[:200]}\n"
            f"  Detection: {r.detection_method[:200]}\n"
            f"  Solution: {r.solution[:200]}\n"
        )
    return "\n---\n".join(parts)


def _record_to_tool_payload(record: AttackRecord) -> Dict[str, Any]:
    return {
        "id": record.id,
        "title": record.title,
        "category": record.category,
        "attack_type": record.attack_type,
        "mitre_technique": record.mitre_technique,
        "tools_used": record.tools_used[:220],
        "attack_steps": record.attack_steps[:260],
        "impact": record.impact[:220],
        "detection_method": record.detection_method[:220],
        "solution": record.solution[:220],
    }


def _chain_to_tool_payload(chain: Dict[str, Any]) -> Dict[str, Any]:
    steps_raw = chain.get("steps", [])
    steps = []
    for step in steps_raw[:10]:
        attack = step.get("attack", {})
        steps.append({
            "phase": step.get("phase", ""),
            "title": attack.get("title", ""),
            "attack_type": attack.get("attack_type", ""),
            "mitre_technique": attack.get("mitre_technique", ""),
            "tools_used": str(attack.get("tools_used", ""))[:140],
            "detection_method": str(attack.get("detection_method", ""))[:140],
        })
    return {
        "chain_id": chain.get("chain_id", ""),
        "confidence": chain.get("confidence", 0),
        "estimated_impact": str(chain.get("estimated_impact", ""))[:220],
        "opsec_notes": str(chain.get("opsec_notes", ""))[:220],
        "step_count": len(steps_raw),
        "steps": steps,
    }


def _risk_level_value(level: Any) -> str:
    return getattr(level, "value", str(level))


def _audit_result_to_tool_payload(result: Any) -> Dict[str, Any]:
    step_summaries = []
    for sr in getattr(result, "step_risks", [])[:12]:
        tool_risks = []
        for tr in getattr(sr, "tool_risks", [])[:5]:
            tool_risks.append({
                "tool_name": tr.tool_name,
                "risk_level": _risk_level_value(tr.risk_level),
                "risk_factors": tr.risk_factors[:6],
                "substitution_alternative": tr.substitution_alternative,
            })
        step_summaries.append({
            "step_index": sr.step_index,
            "step_description": sr.step_description[:220],
            "tools_found": sr.tools_found[:10],
            "overall_risk": _risk_level_value(sr.overall_risk),
            "recommendations": sr.recommendations[:6],
            "tool_risks": tool_risks,
        })

    substitution_map = getattr(result, "tool_substitutions", {}) or {}
    substitutions = [
        {"tool": tool, "alternative": alt}
        for tool, alt in list(substitution_map.items())[:25]
    ]
    return {
        "chain_id": getattr(result, "chain_id", ""),
        "chain_description": str(getattr(result, "chain_description", ""))[:220],
        "overall_risk_score": round(float(getattr(result, "overall_risk_score", 0.0)), 2),
        "overall_risk_level": _risk_level_value(getattr(result, "overall_risk_level", "unknown")),
        "critical_findings": getattr(result, "critical_findings", [])[:12],
        "evasive_techniques": getattr(result, "evasive_techniques", [])[:12],
        "tool_substitutions": substitutions,
        "step_risks": step_summaries,
    }


# ── Main analyst class ────────────────────────────────────────────────────────

class ClaudeAnalyst:
    def __init__(
        self,
        searcher: AttackSearcher,
        audit_engine: Optional[OpSecAuditEngine] = None,
        chainer: Optional[AttackChainer] = None,
    ):
        if not JAILBREAK_API_KEY:
            raise RuntimeError(
                "JAILBREAK_API_KEY is not set. Add it to your .env file."
            )
        self.client = OpenAI(
            api_key=JAILBREAK_API_KEY,
            base_url=JAILBREAK_BASE_URL
        )
        self.model = JAILBREAK_MODEL
        self.searcher = searcher
        self.audit_engine = audit_engine
        self.chainer = chainer
        self.swarm = SwarmExecutionModule(self._execute_tool_call)
        log.info("ClaudeAnalyst initialised with model %s via Jailbreak AI", JAILBREAK_MODEL)

    # ── 1. Full engagement analysis ───────────────────────────────────────────

    def analyse_engagement(
        self,
        target: str,
        chains: List[Dict[str, Any]],
        opsec_report: Optional[Dict[str, Any]] = None,
        scan_fingerprint: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generate a comprehensive narrative analysis of a full engagement.
        Returns the full text response (non-streaming).
        """
        sections = [f"## Target\n{target}\n"]

        if scan_fingerprint:
            fp = scan_fingerprint
            services = fp.get("services", [])
            svc_lines = "\n".join(
                f"  - {s.get('port')}/{s.get('protocol')} {s.get('name')} "
                f"{s.get('product','')} {s.get('version','')}"
                for s in services[:20]
            )
            sections.append(
                f"## Target Fingerprint\n"
                f"IP: {fp.get('ip', 'unknown')}\n"
                f"OS: {fp.get('os', 'unknown')}\n"
                f"Open Services:\n{svc_lines or '  (none detected)'}\n"
            )

        if chains:
            chain_blocks = "\n\n".join(
                _format_chain_for_claude(c) for c in chains[:3]
            )
            sections.append(f"## Attack Chains\n\n{chain_blocks}")

        if opsec_report:
            risk = opsec_report.get("risk_score", 0)
            findings = opsec_report.get("global_findings", [])
            finding_lines = "\n".join(
                f"  [{f.get('severity','?').upper()}] {f.get('title','')}: {f.get('description','')[:120]}"
                for f in findings[:10]
            )
            sections.append(
                f"## OpSec Assessment\n"
                f"Risk Score: {risk}/100\n"
                f"Findings:\n{finding_lines or '  (none)'}\n"
            )

        user_content = (
            "You have been provided with a full penetration test engagement report. "
            "Please provide:\n"
            "1. **Executive Summary** — what was found and what's the overall risk\n"
            "2. **Critical Attack Paths** — the highest-value chains and why\n"
            "3. **OpSec Analysis** — key operational risks and how to mitigate them\n"
            "4. **Recommended Priority Actions** — what to execute first and why\n"
            "5. **Detection Evasion Tips** — specific techniques for this target\n\n"
            + "\n\n".join(sections)
        )

        message = self.client.chat.completions.create(
            model=self.model,
            max_tokens=2048,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ],
        )
        return message.choices[0].message.content

    # ── 2. Single chain deep-dive ─────────────────────────────────────────────

    def analyse_chain(self, chain: Dict[str, Any]) -> str:
        """Deep analysis of a single attack chain."""
        chain_text = _format_chain_for_claude(chain)
        user_content = (
            "Analyse this attack chain in depth:\n\n"
            f"{chain_text}\n\n"
            "Provide:\n"
            "1. **Phase-by-phase breakdown** — risks and execution notes per step\n"
            "2. **Tool recommendations** — best tools for each phase on this target\n"
            "3. **Likely detection points** — where defenders will most likely catch this\n"
            "4. **OpSec hardening** — specific changes to reduce detection risk\n"
            "5. **Alternative techniques** — fallback options if primary fails\n"
        )
        message = self.client.chat.completions.create(
            model=self.model,
            max_tokens=1500,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ],
        )
        return message.choices[0].message.content

    # ── 3. RAG-grounded streaming chat ────────────────────────────────────────

    @staticmethod
    def _coerce_int(value: Any, default: int, minimum: int, maximum: int) -> int:
        try:
            n = int(value)
        except (TypeError, ValueError):
            return default
        return max(minimum, min(maximum, n))

    def _tool_specs(self) -> List[Dict[str, Any]]:
        specs: List[Dict[str, Any]] = [
            {
                "name": "semantic_search",
                "description": "Semantic search over the attack dataset",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "top_k": {"type": "integer", "minimum": 1, "maximum": 20},
                        "category_filter": {"type": "string"},
                        "attack_type_filter": {"type": "string"},
                        "mitre_filter": {"type": "string"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "keyword_search",
                "description": "Keyword search across attack records",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "list_categories",
                "description": "List attack categories with record counts",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "minimum": 1, "maximum": 100}
                    },
                },
            },
            {
                "name": "list_tools",
                "description": "List observed tools with frequency counts",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "minimum": 1, "maximum": 100}
                    },
                },
            },
            {
                "name": "attacks_by_mitre",
                "description": "Get attacks mapped to a MITRE technique id",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "technique_id": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                    },
                    "required": ["technique_id"],
                },
            },
            {
                "name": "attacks_by_category",
                "description": "Get attacks in a category",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                    },
                    "required": ["category"],
                },
            },
            {
                "name": "attacks_by_target",
                "description": "Get attacks by target type",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "target_type": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                    },
                    "required": ["target_type"],
                },
            },
            {
                "name": "build_attack_vector",
                "description": "Generate ranked multi-stage attack chains for a target context",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "target_description": {"type": "string"},
                        "detected_services": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "detected_os": {"type": "string"},
                        "top_chains": {"type": "integer", "minimum": 1, "maximum": 10},
                    },
                    "required": ["target_description"],
                },
            },
            {
                "name": "opsec_note_for_attack",
                "description": "Get OpSec/evasion note for a specific attack record id",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "attack_id": {"type": "integer"},
                    },
                    "required": ["attack_id"],
                },
            },
        ]
        if self.audit_engine is not None:
            specs.append(
                {
                    "name": "opsec_tool_recommendations",
                    "description": "Get OpSec recommendations for a tool",
                    "input_schema": {
                        "type": "object",
                        "properties": {"tool_name": {"type": "string"}},
                        "required": ["tool_name"],
                    },
                }
            )
            specs.append(
                {
                    "name": "opsec_audit_chain",
                    "description": "Audit attack chain steps for detectability risks and substitutions",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "chain_id": {"type": "string"},
                            "chain_description": {"type": "string"},
                            "steps": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                        "required": ["steps"],
                    },
                }
            )
        return specs

    def _tool_specs_openai(self) -> List[Dict[str, Any]]:
        """Convert Anthropic tool specs to OpenAI format."""
        anthropic_specs = self._tool_specs()
        openai_specs = []
        
        for spec in anthropic_specs:
            openai_spec = {
                "type": "function",
                "function": {
                    "name": spec["name"],
                    "description": spec["description"],
                    "parameters": spec["input_schema"]
                }
            }
            openai_specs.append(openai_spec)
        
        return openai_specs

    def _execute_tool_call(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name == "semantic_search":
            query = str(tool_input.get("query", "")).strip()
            if not query:
                return {"error": "query is required"}
            top_k = self._coerce_int(tool_input.get("top_k"), default=8, minimum=1, maximum=20)
            category = tool_input.get("category_filter")
            attack_type = tool_input.get("attack_type_filter")
            mitre = tool_input.get("mitre_filter")
            resp = self.searcher.semantic_search(
                query=query,
                top_k=top_k,
                category=category,
                attack_type=attack_type,
                mitre=mitre,
            )
            return {
                "query": resp.query,
                "total": resp.total,
                "results": [
                    {
                        "score": r.score,
                        "record": _record_to_tool_payload(r.record),
                    }
                    for r in resp.results[:top_k]
                ],
            }

        if tool_name == "keyword_search":
            query = str(tool_input.get("query", "")).strip()
            if not query:
                return {"error": "query is required"}
            limit = self._coerce_int(tool_input.get("limit"), default=10, minimum=1, maximum=50)
            records = self.searcher.keyword_search(query, limit=limit)
            return {
                "query": query,
                "total": len(records),
                "results": [_record_to_tool_payload(r) for r in records[:limit]],
            }

        if tool_name == "list_categories":
            limit = self._coerce_int(tool_input.get("limit"), default=20, minimum=1, maximum=100)
            categories = self.searcher.list_categories()
            return {"total": len(categories), "categories": categories[:limit]}

        if tool_name == "list_tools":
            limit = self._coerce_int(tool_input.get("limit"), default=20, minimum=1, maximum=100)
            tools = self.searcher.list_tools()
            return {"total": len(tools), "tools": tools[:limit]}

        if tool_name == "attacks_by_mitre":
            technique_id = str(tool_input.get("technique_id", "")).strip()
            if not technique_id:
                return {"error": "technique_id is required"}
            limit = self._coerce_int(tool_input.get("limit"), default=20, minimum=1, maximum=50)
            records = self.searcher.get_by_mitre(technique_id, limit=limit)
            return {
                "technique_id": technique_id,
                "total": len(records),
                "results": [_record_to_tool_payload(r) for r in records[:limit]],
            }

        if tool_name == "attacks_by_category":
            category = str(tool_input.get("category", "")).strip()
            if not category:
                return {"error": "category is required"}
            limit = self._coerce_int(tool_input.get("limit"), default=20, minimum=1, maximum=50)
            records = self.searcher.get_by_category(category, limit=limit)
            return {
                "category": category,
                "total": len(records),
                "results": [_record_to_tool_payload(r) for r in records[:limit]],
            }

        if tool_name == "attacks_by_target":
            target_type = str(tool_input.get("target_type", "")).strip()
            if not target_type:
                return {"error": "target_type is required"}
            limit = self._coerce_int(tool_input.get("limit"), default=20, minimum=1, maximum=50)
            records = self.searcher.get_by_target(target_type, limit=limit)
            return {
                "target_type": target_type,
                "total": len(records),
                "results": [_record_to_tool_payload(r) for r in records[:limit]],
            }

        if tool_name == "build_attack_vector":
            if self.chainer is None:
                return {"error": "Attack chainer unavailable"}
            target_description = str(tool_input.get("target_description", "")).strip()
            if not target_description:
                return {"error": "target_description is required"}
            raw_services = tool_input.get("detected_services") or []
            if isinstance(raw_services, list):
                detected_services = [
                    str(s).strip() for s in raw_services if str(s).strip()
                ][:20]
            else:
                detected_services = []
            detected_os = str(tool_input.get("detected_os", "")).strip() or None
            top_chains = self._coerce_int(tool_input.get("top_chains"), default=3, minimum=1, maximum=10)
            req = AttackVectorRequest(
                target_description=target_description,
                detected_services=detected_services,
                detected_os=detected_os,
                top_chains=top_chains,
            )
            vector = self.chainer.build_chains(req)
            return {
                "target_description": vector.target_description,
                "total_chains": len(vector.chains),
                "chains": [_chain_to_tool_payload(c.model_dump()) for c in vector.chains[:top_chains]],
            }

        if tool_name == "opsec_note_for_attack":
            if self.chainer is None:
                return {"error": "Attack chainer unavailable"}
            attack_id = self._coerce_int(tool_input.get("attack_id"), default=0, minimum=1, maximum=10**9)
            if attack_id <= 0:
                return {"error": "attack_id is required"}
            note = self.chainer.get_opsec_note(attack_id)
            if note is None:
                return {"found": False, "attack_id": attack_id}
            return {
                "found": True,
                "attack_id": note.attack_id,
                "detection_method": note.detection_method[:220],
                "evasion_hints": note.evasion_hints[:8],
                "recommended_opsec": note.recommended_opsec[:260],
            }

        if tool_name == "opsec_tool_recommendations":
            if self.audit_engine is None:
                return {"error": "OpSec audit engine unavailable"}
            tool = str(tool_input.get("tool_name", "")).strip()
            if not tool:
                return {"error": "tool_name is required"}
            return self.audit_engine.get_tool_recommendations(tool)

        if tool_name == "opsec_audit_chain":
            if self.audit_engine is None:
                return {"error": "OpSec audit engine unavailable"}
            raw_steps = tool_input.get("steps") or []
            if not isinstance(raw_steps, list) or not raw_steps:
                return {"error": "steps is required"}
            steps = [str(s).strip() for s in raw_steps if str(s).strip()][:20]
            if not steps:
                return {"error": "steps is required"}
            chain_id = str(tool_input.get("chain_id", "tool-chain")).strip()[:64] or "tool-chain"
            chain_description = str(tool_input.get("chain_description", "")).strip()
            result = self.audit_engine.audit_chain(
                chain_id=chain_id,
                chain_description=chain_description,
                steps=steps,
            )
            return _audit_result_to_tool_payload(result)

        return {"error": f"Unsupported tool: {tool_name}"}

    def _build_chat_messages(
        self,
        question: str,
        history: List[Dict[str, str]],
        engagement_context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        search_resp = self.searcher.semantic_search(question, top_k=8)
        knowledge_ctx = _format_records_for_context(
            [r.record for r in search_resp.results]
        )
        ctx_parts = ["## Relevant Attack Knowledge Base Entries\n" + knowledge_ctx]
        if engagement_context:
            chains = engagement_context.get("chains", [])
            if chains:
                ctx_parts.append(
                    "## Current Engagement Chains\n"
                    + "\n\n".join(_format_chain_for_claude(c) for c in chains[:2])
                )
        context_block = "\n\n".join(ctx_parts)

        messages: List[Dict[str, Any]] = []
        for turn in history[-6:]:
            messages.append({
                "role": turn["role"],
                "content": turn["content"],
            })
        messages.append({
            "role": "user",
            "content": (
                f"<knowledge_context>\n{context_block}\n</knowledge_context>\n\n"
                f"{question}"
            ),
        })
        return messages

    def _chat_with_tools(
        self,
        question: str,
        history: List[Dict[str, str]],
        engagement_context: Optional[Dict[str, Any]] = None,
        allow_tools: bool = True,
        execution_mode: str = "single_agent",
        swarm_max_steps: int = 12,
    ) -> str:
        if execution_mode == "swarm":
            return self.swarm.run(
                question=question,
                history=history,
                engagement_context=engagement_context,
                allow_tools=allow_tools,
                max_steps=swarm_max_steps,
            )

        messages = self._build_chat_messages(
            question=question,
            history=history,
            engagement_context=engagement_context,
        )
        # Add system message to the beginning
        messages.insert(0, {"role": "system", "content": SYSTEM_PROMPT})
        
        tools = self._tool_specs_openai() if allow_tools else None

        for _ in range(5):
            kwargs: Dict[str, Any] = {
                "model": self.model,
                "max_tokens": 1024,
                "messages": messages,
            }
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"

            message = self.client.chat.completions.create(**kwargs)
            
            assistant_message = message.choices[0].message
            
            messages.append({"role": "assistant", "content": assistant_message.content or ""})

            tool_calls = assistant_message.tool_calls
            if not tool_calls:
                return assistant_message.content or ""

            tool_results = []
            for tool_call in tool_calls:
                tool_input = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
                try:
                    result = self._execute_tool_call(tool_call.function.name, tool_input)
                except Exception as e:
                    result = {"error": str(e)}
                tool_results.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "content": json.dumps(result, ensure_ascii=False),
                })

            messages.extend(tool_results)

        return "Unable to complete tool execution within the allowed turns."

    async def chat_stream(
        self,
        question: str,
        history: List[Dict[str, str]],
        engagement_context: Optional[Dict[str, Any]] = None,
        allow_tools: bool = True,
        execution_mode: str = "single_agent",
        swarm_max_steps: int = 12,
    ) -> AsyncIterator[str]:
        answer = self._chat_with_tools(
            question=question,
            history=history,
            engagement_context=engagement_context,
            allow_tools=allow_tools,
            execution_mode=execution_mode,
            swarm_max_steps=swarm_max_steps,
        )
        chunk_size = 120
        if not answer:
            return
        for i in range(0, len(answer), chunk_size):
            yield answer[i:i + chunk_size]

    def chat_sync(
        self,
        question: str,
        history: List[Dict[str, str]],
        engagement_context: Optional[Dict[str, Any]] = None,
        allow_tools: bool = True,
        execution_mode: str = "single_agent",
        swarm_max_steps: int = 12,
    ) -> str:
        return self._chat_with_tools(
            question=question,
            history=history,
            engagement_context=engagement_context,
            allow_tools=allow_tools,
            execution_mode=execution_mode,
            swarm_max_steps=swarm_max_steps,
        )
