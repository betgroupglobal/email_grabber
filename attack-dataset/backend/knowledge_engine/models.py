"""
Pydantic models shared across the knowledge engine.
"""
from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field


class AttackRecord(BaseModel):
    id: int
    title: str
    category: str
    attack_type: str
    scenario_description: str
    tools_used: str
    attack_steps: str
    target_type: str
    vulnerability: str
    mitre_technique: str
    impact: str
    detection_method: str
    solution: str
    tags: str
    source: str

    class Config:
        from_attributes = True


# ── Query / Response models ──────────────────────────────────────────────────

class SearchQuery(BaseModel):
    query: str = Field(..., description="Natural-language query or target context")
    top_k: int = Field(10, ge=1, le=50)
    category_filter: Optional[str] = None
    attack_type_filter: Optional[str] = None
    mitre_filter: Optional[str] = None


class AttackResult(BaseModel):
    record: AttackRecord
    score: float = Field(..., description="Semantic similarity score (0-1)")


class SearchResponse(BaseModel):
    query: str
    results: List[AttackResult]
    total: int


class AttackVectorRequest(BaseModel):
    target_description: str = Field(..., description="Target host / service fingerprint")
    detected_services: List[str] = Field(default_factory=list)
    detected_os: Optional[str] = None
    top_chains: int = Field(3, ge=1, le=10)


class AttackStep(BaseModel):
    phase: str
    attack: AttackRecord
    rationale: str
    mitre_technique: str


class AttackChain(BaseModel):
    chain_id: str
    target_description: str
    confidence: float
    steps: List[AttackStep]
    estimated_impact: str
    opsec_notes: str


class AttackVectorResponse(BaseModel):
    target_description: str
    chains: List[AttackChain]


class MitreMapping(BaseModel):
    technique_id: str
    technique_name: str
    tactic: str
    attacks: List[AttackRecord]


class ToolRecommendation(BaseModel):
    tool: str
    frequency: int
    related_attacks: List[str]


class OpsecNote(BaseModel):
    attack_id: int
    detection_method: str
    evasion_hints: List[str]
    recommended_opsec: str
