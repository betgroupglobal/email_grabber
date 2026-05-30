"""
Pydantic models shared across the knowledge engine.
"""
from __future__ import annotations
from typing import List, Optional, Dict, Any
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
    # ML enhancement fields (optional)
    ml_category: Optional[str] = None
    ml_confidence: Optional[float] = None
    combined_score: Optional[float] = None

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


class ExecutionFeedbackContext(BaseModel):
    """Live execution feedback for attack-vector replanning."""
    completed_steps: List[Dict[str, Any]] = Field(default_factory=list)
    last_failure: Optional[Dict[str, Any]] = None
    from_phase: Optional[str] = None
    from_step_index: int = Field(0, ge=0)
    prior_directive_ids: List[str] = Field(default_factory=list)


class LiveReplanRequest(AttackVectorRequest):
    """Extends attack-vector with live step/failure context."""
    execution_context: ExecutionFeedbackContext = Field(
        default_factory=ExecutionFeedbackContext
    )
    failure_class: Optional[str] = None


class LiveReplanResponse(AttackVectorResponse):
    """Attack chains replanned using dataset + trained model with live context."""
    grounding_query: str = ""
    dataset_hit_count: int = 0
    ml_top_label: Optional[str] = None
    ml_top_confidence: Optional[float] = None
    replan_reason: str = "live_execution_feedback"
    alternate_chain_scores: List[float] = Field(default_factory=list)
    failure_class: Optional[str] = None


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
    risk_level: str
    recommendations: List[str]


# ── ML Prediction models ─────────────────────────────────────────────────────

class MLPrediction(BaseModel):
    label: str = Field(..., description="Predicted class label")
    confidence: float = Field(..., description="Confidence score (0-1)")
    rank: int = Field(..., description="Rank of the prediction")


class MLPredictRequest(BaseModel):
    text: str = Field(..., description="Text to classify")
    target: str = Field(default="category", description="Target model to use (category, attack_type, etc.)")
    top_k: int = Field(default=3, ge=1, le=10, description="Number of top predictions to return")


class MLPredictResponse(BaseModel):
    text: str
    target: str
    predictions: List[MLPrediction]


class MLBatchPredictRequest(BaseModel):
    texts: List[str] = Field(..., description="List of texts to classify")
    target: str = Field(default="category", description="Target model to use")
    top_k: int = Field(default=3, ge=1, le=10, description="Number of top predictions to return")


class MLModelInfo(BaseModel):
    model_config = {'protected_namespaces': ()}
    
    target: str
    model_type: str
    num_classes: int
    accuracy: Optional[float] = None
    num_samples: Optional[int] = None
    embedding_method: Optional[str] = None
    timestamp: Optional[str] = None


class MLModelsResponse(BaseModel):
    models: List[MLModelInfo]
    available_targets: List[str]


# ── Attack Tree / Kill Chain Engine models ───────────────────────────────────

class MITRETTP(BaseModel):
    """MITRE ATT&CK Tactic, Technique, and Procedure"""
    technique_id: str = Field(..., description="MITRE technique ID (e.g., T1190)")
    technique_name: str = Field(..., description="MITRE technique name")
    tactic: str = Field(..., description="MITRE tactic (e.g., Initial Access)")
    sub_techniques: List[str] = Field(default_factory=list, description="Sub-technique IDs")
    detection: List[str] = Field(default_factory=list, description="Common detection methods")
    mitigation: List[str] = Field(default_factory=list, description="Recommended mitigations")
    is_custom: bool = Field(default=False, description="Whether this is a custom TTP")


class AttackTreeNode(BaseModel):
    """Node in an attack tree representing a specific attack step"""
    node_id: str = Field(..., description="Unique node identifier")
    attack_record_id: int = Field(..., description="Reference to attack record")
    mitre_ttp: MITRETTP = Field(..., description="MITRE TTP mapping")
    phase: str = Field(..., description="Attack phase (Reconnaissance, Initial Access, etc.)")
    success_probability: float = Field(default=0.5, ge=0.0, le=1.0, description="Estimated success probability")
    detection_risk: float = Field(default=0.5, ge=0.0, le=1.0, description="Detection risk score")
    impact_score: float = Field(default=0.5, ge=0.0, le=1.0, description="Impact score if successful")
    time_estimate: int = Field(default=60, description="Estimated time in seconds")
    required_tools: List[str] = Field(default_factory=list, description="Required tools")
    prerequisites: List[str] = Field(default_factory=list, description="Prerequisite node IDs")
    outcomes: List[str] = Field(default_factory=list, description="Possible outcome node IDs")


class AttackTree(BaseModel):
    """Complete attack tree structure"""
    tree_id: str = Field(..., description="Unique tree identifier")
    target_description: str = Field(..., description="Target this tree is designed for")
    nodes: Dict[str, AttackTreeNode] = Field(default_factory=dict, description="All nodes in the tree")
    root_nodes: List[str] = Field(default_factory=list, description="Root node IDs (starting points)")
    leaf_nodes: List[str] = Field(default_factory=list, description="Leaf node IDs (end goals)")
    overall_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Overall attack path score")
    estimated_time: int = Field(default=0, description="Total estimated time in seconds")
    created_at: str = Field(default_factory=lambda: str(__import__('datetime').datetime.now()))


class AttackPath(BaseModel):
    """A specific path through the attack tree"""
    path_id: str = Field(..., description="Unique path identifier")
    tree_id: str = Field(..., description="Parent attack tree ID")
    node_sequence: List[str] = Field(..., description="Ordered sequence of node IDs")
    cumulative_score: float = Field(..., ge=0.0, le=1.0, description="Cumulative path score")
    success_probability: float = Field(..., ge=0.0, le=1.0, description="Overall success probability")
    detection_risk: float = Field(..., ge=0.0, le=1.0, description="Overall detection risk")
    estimated_time: int = Field(..., description="Total estimated time")
    is_adaptive: bool = Field(default=False, description="Whether this path adapts based on feedback")


class ExecutionResult(BaseModel):
    """Result of executing an attack step"""
    result_id: str = Field(..., description="Unique result identifier")
    path_id: str = Field(..., description="Associated attack path ID")
    node_id: str = Field(..., description="Executed node ID")
    status: str = Field(..., description="Execution status (success, failure, partial)")
    actual_time: int = Field(..., description="Actual execution time in seconds")
    detected: bool = Field(default=False, description="Whether execution was detected")
    artifacts: List[str] = Field(default_factory=list, description="Artifacts left behind")
    lessons_learned: str = Field(default="", description="Key lessons for feedback")
    timestamp: str = Field(default_factory=lambda: str(__import__('datetime').datetime.now()))


class FeedbackLoop(BaseModel):
    """Feedback loop data for adaptive attack pathing"""
    feedback_id: str = Field(..., description="Unique feedback identifier")
    session_id: str = Field(..., description="Associated analysis session ID")
    execution_results: List[ExecutionResult] = Field(default_factory=list, description="Execution results")
    adjusted_probabilities: Dict[str, float] = Field(default_factory=dict, description="Adjusted success probabilities")
    new_recommendations: List[str] = Field(default_factory=list, description="New path recommendations")
    confidence_delta: float = Field(default=0.0, description="Change in overall confidence")
    timestamp: str = Field(default_factory=lambda: str(__import__('datetime').datetime.now()))


class AdaptiveAttackRequest(BaseModel):
    """Request for adaptive attack chain generation with feedback"""
    target_description: str = Field(..., description="Target description")
    detected_services: List[str] = Field(default_factory=list)
    detected_os: Optional[str] = None
    feedback_history: List[FeedbackLoop] = Field(default_factory=list, description="Previous feedback loops")
    current_context: Dict[str, Any] = Field(default_factory=dict, description="Current execution context")
    top_paths: int = Field(default=3, ge=1, le=10, description="Number of top paths to generate")


class AdaptiveAttackResponse(BaseModel):
    """Response with adaptive attack paths"""
    target_description: str
    attack_tree: AttackTree
    recommended_paths: List[AttackPath]
    adaptation_summary: str = Field(default="", description="Summary of adaptations made")
    confidence_score: float = Field(default=0.0, description="Overall confidence in recommendations")
