"""
Feedback Loop Manager - AI-Powered Integration of Attack Chain Building with Real-time Analyzer

This manager:
- Receives live analysis results from the Real-time Analyzer
- Uses AI to analyze execution results and generate intelligent feedback
- Enables adaptive attack pathing based on AI-powered insights
- Maintains session state for continuous improvement
- Provides AI-generated recommendations and insights
"""
from __future__ import annotations
import uuid
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json

from .core.models import (
    AttackRecord,
    AttackChain,
    AttackVectorRequest,
    AttackVectorResponse,
    AdaptiveAttackRequest,
    AdaptiveAttackResponse,
    FeedbackLoop,
    ExecutionResult,
)
from .search.attack_chainer import AttackChainer
from .search.searcher import AttackSearcher
from .attack_tree_engine import AttackTreeEngine
from .multi_agent_orchestrator import MultiAgentOrchestrator


class AnalysisSession:
    """Represents an active analysis session with feedback loop"""
    
    def __init__(self, session_id: str, target: str, initial_request: AttackVectorRequest):
        self.session_id = session_id
        self.target = target
        self.initial_request = initial_request
        self.created_at = datetime.now()
        self.last_updated = datetime.now()
        self.feedback_history: List[FeedbackLoop] = []
        self.attack_chains_generated: List[AttackChain] = []
        self.current_context: Dict[str, Any] = {}
        self.is_active = True
        self.iteration_count = 0
        self.max_iterations = 5
    
    def add_feedback(self, feedback: FeedbackLoop):
        """Add feedback to the session"""
        self.feedback_history.append(feedback)
        self.last_updated = datetime.now()
        self.iteration_count += 1
        
        # Check if we should continue iterating
        if self.iteration_count >= self.max_iterations:
            self.is_active = False
    
    def update_context(self, context: Dict[str, Any]):
        """Update the current execution context"""
        self.current_context.update(context)
        self.last_updated = datetime.now()
    
    def should_continue(self) -> bool:
        """Determine if the session should continue"""
        if not self.is_active:
            return False
        
        # Check if session is stale (no updates for 30 minutes)
        if datetime.now() - self.last_updated > timedelta(minutes=30):
            self.is_active = False
            return False
        
        return True
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the session"""
        return {
            "session_id": self.session_id,
            "target": self.target,
            "created_at": str(self.created_at),
            "last_updated": str(self.last_updated),
            "iteration_count": self.iteration_count,
            "is_active": self.is_active,
            "feedback_count": len(self.feedback_history),
            "chains_generated": len(self.attack_chains_generated)
        }


class FeedbackLoopManager:
    """Manages feedback loops between attack chain building and real-time analysis using AI insights"""
    
    def __init__(self, attack_chainer: AttackChainer, attack_tree_engine: AttackTreeEngine, orchestrator: MultiAgentOrchestrator, ai_analyzer=None):
        self.attack_chainer = attack_chainer
        self.attack_tree_engine = attack_tree_engine
        self.orchestrator = orchestrator
        self.ai_analyzer = ai_analyzer  # AI analyzer for intelligent insights
        self.sessions: Dict[str, AnalysisSession] = {}
        self.global_feedback: List[FeedbackLoop] = []
        self.performance_metrics: Dict[str, Any] = {
            "total_sessions": 0,
            "total_feedback_loops": 0,
            "average_adaptation_improvement": 0.0,
            "successful_adaptations": 0
        }
    
    def create_session(self, target: str, request: AttackVectorRequest) -> AnalysisSession:
        """Create a new analysis session"""
        session_id = str(uuid.uuid4())[:8]
        session = AnalysisSession(session_id, target, request)
        self.sessions[session_id] = session
        self.performance_metrics["total_sessions"] += 1
        return session
    
    def get_session(self, session_id: str) -> Optional[AnalysisSession]:
        """Get an existing session"""
        return self.sessions.get(session_id)
    
    def cleanup_inactive_sessions(self):
        """Remove inactive sessions"""
        active_sessions = {}
        for session_id, session in self.sessions.items():
            if session.should_continue():
                active_sessions[session_id] = session
        
        removed_count = len(self.sessions) - len(active_sessions)
        self.sessions = active_sessions
        return removed_count
    
    async def process_analyzer_results(self, session_id: str, analyzer_results: Dict[str, Any]) -> FeedbackLoop:
        """Process results from the Real-time Analyzer and create AI-powered feedback"""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        # Convert analyzer results to execution results
        execution_results = self._convert_analyzer_results(analyzer_results, session_id)
        
        # Use AI to analyze results and generate intelligent feedback
        if self.ai_analyzer:
            try:
                feedback = await self._ai_generate_feedback(session_id, execution_results, analyzer_results, session)
            except Exception as e:
                print(f"AI feedback generation failed, using standard approach: {e}")
                feedback = self.orchestrator.create_feedback_loop(session_id, execution_results)
        else:
            feedback = self.orchestrator.create_feedback_loop(session_id, execution_results)
        
        # Add to session
        session.add_feedback(feedback)
        
        # Add to global feedback
        self.global_feedback.append(feedback)
        self.performance_metrics["total_feedback_loops"] += 1
        
        # Update performance metrics
        if feedback.confidence_delta > 0:
            self.performance_metrics["successful_adaptations"] += 1
        
        # Update session context with analyzer findings
        session.update_context({
            "analyzer_results": analyzer_results,
            "last_scan_time": str(datetime.now())
        })
        
        return feedback
    
    async def _ai_generate_feedback(self, session_id: str, execution_results: List[ExecutionResult], 
                                   analyzer_results: Dict[str, Any], session: AnalysisSession) -> FeedbackLoop:
        """Use AI to generate intelligent feedback from execution results"""
        try:
            # Prepare execution summary for AI
            results_summary = self._summarize_execution_results(execution_results)
            analyzer_summary = self._summarize_analyzer_results(analyzer_results)
            session_context = self._summarize_session_context(session)
            
            ai_prompt = f"""
Analyze these execution results and generate intelligent feedback:

Execution Results:
{results_summary}

Analyzer Findings:
{analyzer_summary}

Session Context:
{session_context}

Provide:
1. Adjusted success probabilities for each node (-1.0 to +1.0 adjustments)
2. New attack recommendations based on findings
3. Key lessons learned from execution
4. Confidence delta (overall improvement score -1.0 to +1.0)
5. Strategic recommendations for next iteration

Format as JSON with structured feedback data.
"""
            ai_response = self.ai_analyzer.analyze_attack(ai_prompt)
            
            if ai_response:
                # Parse AI response into feedback structure
                adjusted_probabilities = ai_response.get("adjusted_probabilities", {})
                new_recommendations = ai_response.get("new_recommendations", [])
                confidence_delta = ai_response.get("confidence_delta", 0.0)
                
                # Add AI lessons learned to execution results
                for result in execution_results:
                    if ai_response.get("lessons_learned"):
                        result.lessons_learned = ai_response["lessons_learned"]
                
                feedback = FeedbackLoop(
                    feedback_id=str(uuid.uuid4())[:8],
                    session_id=session_id,
                    execution_results=execution_results,
                    adjusted_probabilities=adjusted_probabilities,
                    new_recommendations=new_recommendations,
                    confidence_delta=confidence_delta
                )
                
                return feedback
        except Exception as e:
            print(f"AI feedback analysis failed: {e}")
        
        # Fallback to standard feedback generation
        return self.orchestrator.create_feedback_loop(session_id, execution_results)
    
    def _summarize_execution_results(self, execution_results: List[ExecutionResult]) -> str:
        """Create a summary of execution results for AI analysis"""
        summary = f"Total results: {len(execution_results)}\n"
        for result in execution_results:
            summary += f"- {result.node_id}: {result.status} (detected: {result.detected}, time: {result.actual_time}s)\n"
            if result.lessons_learned:
                summary += f"  Lessons: {result.lessons_learned}\n"
        return summary
    
    def _summarize_analyzer_results(self, analyzer_results: Dict[str, Any]) -> str:
        """Create a summary of analyzer results for AI analysis"""
        fingerprint = analyzer_results.get("fingerprint", {})
        summary = f"Target: {analyzer_results.get('target', 'unknown')}\n"
        summary += f"OS: {fingerprint.get('os', 'unknown')}\n"
        summary += f"Services found: {len(fingerprint.get('services', []))}\n"
        
        for service in fingerprint.get("services", [])[:5]:
            summary += f"- Port {service.get('port')}: {service.get('name')} {service.get('product', '')} {service.get('version', '')}\n"
        
        return summary
    
    def _summarize_session_context(self, session: AnalysisSession) -> str:
        """Create a summary of session context for AI analysis"""
        summary = f"Session ID: {session.session_id}\n"
        summary += f"Iteration: {session.iteration_count}\n"
        summary += f"Feedback loops: {len(session.feedback_history)}\n"
        summary += f"Chains generated: {len(session.attack_chains_generated)}\n"
        return summary
    
    def _convert_analyzer_results(self, analyzer_results: Dict[str, Any], session_id: str) -> List[ExecutionResult]:
        """Convert analyzer results to execution results format"""
        execution_results = []
        
        # Extract fingerprint data
        fingerprint = analyzer_results.get("fingerprint", {})
        services = fingerprint.get("services", [])
        
        # Create execution results for discovered services
        for service in services:
            result = ExecutionResult(
                result_id=str(uuid.uuid4())[:8],
                path_id=session_id,
                node_id=f"service_{service.get('port', 'unknown')}",
                status="success",
                actual_time=30,
                detected=False,
                artifacts=[f"port_{service.get('port')}_scan"],
                lessons_learned=f"Service {service.get('name')} discovered on port {service.get('port')}"
            )
            execution_results.append(result)
        
        # Create result for OS detection
        os_info = fingerprint.get("os", "")
        if os_info:
            result = ExecutionResult(
                result_id=str(uuid.uuid4())[:8],
                path_id=session_id,
                node_id="os_detection",
                status="success",
                actual_time=60,
                detected=False,
                artifacts=["os_fingerprint"],
                lessons_learned=f"OS identified as {os_info}"
            )
            execution_results.append(result)
        
        return execution_results
    
    async def generate_adaptive_chains(self, session_id: str) -> AttackVectorResponse:
        """Generate adaptive attack chains based on session feedback"""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        # Create adaptive request with feedback history
        adaptive_request = AdaptiveAttackRequest(
            target_description=session.initial_request.target_description,
            detected_services=session.initial_request.detected_services,
            detected_os=session.initial_request.detected_os,
            feedback_history=session.feedback_history,
            current_context=session.current_context,
            top_paths=session.initial_request.top_chains
        )
        
        # Get candidate attacks from searcher
        services_str = ", ".join(session.initial_request.detected_services) if session.initial_request.detected_services else ""
        os_str = session.initial_request.detected_os or ""
        full_query = " ".join(filter(None, [
            session.initial_request.target_description,
            services_str,
            os_str,
        ]))
        
        response = self.attack_chainer.searcher.semantic_search(full_query, top_k=40)
        candidates = [r.record for r in response.results]
        
        # Generate adaptive attack using attack tree engine
        adaptive_response = self.attack_tree_engine.generate_adaptive_attack(
            adaptive_request, 
            candidates
        )
        
        # Convert attack tree paths to attack chains format
        chains = self._convert_paths_to_chains(adaptive_response)
        
        # Store generated chains in session
        session.attack_chains_generated.extend(chains)
        
        return AttackVectorResponse(
            target_description=session.initial_request.target_description,
            chains=chains
        )
    
    def _convert_paths_to_chains(self, adaptive_response: AdaptiveAttackResponse) -> List[AttackChain]:
        """Convert attack tree paths to attack chains format"""
        chains = []
        
        for path in adaptive_response.recommended_paths:
            # Convert path nodes to attack steps
            steps = []
            for node_id in path.node_sequence:
                if node_id in adaptive_response.attack_tree.nodes:
                    node = adaptive_response.attack_tree.nodes[node_id]
                    
                    # Create a mock attack record from the node
                    from .core.models import AttackStep
                    step = AttackStep(
                        phase=node.phase,
                        attack=AttackRecord(
                            id=node.attack_record_id,
                            title=node.mitre_ttp.technique_name,
                            category=node.mitre_ttp.tactic,
                            attack_type=node.mitre_ttp.technique_name,
                            scenario_description=f"MITRE {node.mitre_ttp.technique_id}: {node.mitre_ttp.technique_name}",
                            tools_used=", ".join(node.required_tools),
                            attack_steps=f"Execute {node.mitre_ttp.technique_name} with {node.mitre_ttp.technique_id}",
                            target_type="various",
                            vulnerability="unknown",
                            mitre_technique=node.mitre_ttp.technique_id,
                            impact=f"Impact score: {node.impact_score}",
                            detection_method=f"Detection risk: {node.detection_risk}",
                            solution="See MITRE mitigations",
                            tags=f"{node.phase}, {node.mitre_ttp.tactic}",
                            source="adaptive_engine"
                        ),
                        rationale=f"Selected based on adaptive analysis with success probability {node.success_probability}",
                        mitre_technique=node.mitre_ttp.technique_id
                    )
                    steps.append(step)
            
            if steps:
                chain = AttackChain(
                    chain_id=path.path_id,
                    target_description=adaptive_response.attack_tree.target_description,
                    confidence=path.cumulative_score,
                    steps=steps,
                    estimated_impact=f"Overall impact based on path analysis",
                    opsec_notes=f"Adaptive path with detection risk {path.detection_risk:.2f}"
                )
                chains.append(chain)
        
        return chains
    
    async def execute_adaptive_attack(self, session_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an adaptive attack using the orchestrator"""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        # Get current attack tree from the latest adaptive response
        if not session.feedback_history:
            # Generate initial adaptive chains
            await self.generate_adaptive_chains(session_id)
        
        # Get candidates for tree building
        services_str = ", ".join(session.initial_request.detected_services) if session.initial_request.detected_services else ""
        os_str = session.initial_request.detected_os or ""
        full_query = " ".join(filter(None, [
            session.initial_request.target_description,
            services_str,
            os_str,
        ]))
        
        response = self.attack_chainer.searcher.semantic_search(full_query, top_k=40)
        candidates = [r.record for r in response.results]
        
        # Build attack tree
        attack_tree = self.attack_tree_engine.build_attack_tree(
            candidates,
            session.initial_request.target_description
        )
        
        # Apply feedback history
        for feedback in session.feedback_history:
            attack_tree = self.attack_tree_engine.apply_feedback(attack_tree, feedback)
        
        # Execute adaptive attack using orchestrator
        execution_result = await self.orchestrator.execute_adaptive_attack(
            attack_tree,
            context
        )
        
        return execution_result
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for the feedback loop system"""
        # Calculate average adaptation improvement
        if self.global_feedback:
            avg_delta = sum(f.confidence_delta for f in self.global_feedback) / len(self.global_feedback)
            self.performance_metrics["average_adaptation_improvement"] = avg_delta
        
        return self.performance_metrics
    
    def get_session_insights(self, session_id: str) -> Dict[str, Any]:
        """Get insights about a specific session"""
        session = self.get_session(session_id)
        if not session:
            return {"error": "Session not found"}
        
        # Analyze feedback patterns
        success_rate = 0.0
        detection_rate = 0.0
        
        if session.feedback_history:
            total_results = sum(len(f.execution_results) for f in session.feedback_history)
            if total_results > 0:
                successful_results = sum(
                    1 for f in session.feedback_history 
                    for r in f.execution_results 
                    if r.status == "success"
                )
                detected_results = sum(
                    1 for f in session.feedback_history 
                    for r in f.execution_results 
                    if r.detected
                )
                success_rate = successful_results / total_results
                detection_rate = detected_results / total_results
        
        return {
            "session_summary": session.get_summary(),
            "success_rate": success_rate,
            "detection_rate": detection_rate,
            "feedback_patterns": self._analyze_feedback_patterns(session),
            "recommendations": self._generate_session_recommendations(session)
        }
    
    def _analyze_feedback_patterns(self, session: AnalysisSession) -> Dict[str, Any]:
        """Analyze patterns in feedback data using AI insights"""
        # Use AI for intelligent pattern analysis
        if self.ai_analyzer:
            try:
                feedback_summary = self._summarize_feedback_history(session)
                
                ai_prompt = f"""
Analyze patterns in this feedback history and provide insights:

{feedback_summary}

Provide:
1. Common failure patterns and root causes
2. Recurring detection patterns and evasion opportunities
3. Time-based trends or patterns
4. Strategic insights for improvement
5. Risk assessment and mitigation recommendations

Format as structured analysis.
"""
                ai_response = self.ai_analyzer.analyze_attack(ai_prompt)
                
                if ai_response:
                    return {
                        "ai_analysis": ai_response,
                        "common_failures": ai_response.get("common_failures", []),
                        "common_detections": ai_response.get("common_detections", []),
                        "strategic_insights": ai_response.get("strategic_insights", []),
                        "risk_assessment": ai_response.get("risk_assessment", "")
                    }
            except Exception as e:
                print(f"AI pattern analysis failed, using statistical approach: {e}")
        
        # Fallback to statistical analysis
        patterns = {
            "common_failures": [],
            "common_detections": [],
            "time_trends": []
        }
        
        failure_counts = {}
        detection_counts = {}
        
        for feedback in session.feedback_history:
            for result in feedback.execution_results:
                if result.status == "failure":
                    failure_counts[result.node_id] = failure_counts.get(result.node_id, 0) + 1
                if result.detected:
                    detection_counts[result.node_id] = detection_counts.get(result.node_id, 0) + 1
        
        patterns["common_failures"] = sorted(failure_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        patterns["common_detections"] = sorted(detection_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return patterns
    
    def _summarize_feedback_history(self, session: AnalysisSession) -> str:
        """Create a summary of feedback history for AI analysis"""
        summary = f"Feedback loops: {len(session.feedback_history)}\n"
        
        for idx, feedback in enumerate(session.feedback_history):
            summary += f"\nLoop {idx + 1} ({feedback.timestamp}):\n"
            summary += f"  Confidence delta: {feedback.confidence_delta}\n"
            summary += f"  Execution results: {len(feedback.execution_results)}\n"
            
            for result in feedback.execution_results:
                summary += f"    - {result.node_id}: {result.status} (detected: {result.detected})\n"
            
            if feedback.new_recommendations:
                summary += f"  Recommendations: {len(feedback.new_recommendations)}\n"
        
        return summary
    
    def _generate_session_recommendations(self, session: AnalysisSession) -> List[str]:
        """Generate AI-powered recommendations based on session data"""
        # Use AI for intelligent recommendations
        if self.ai_analyzer and session.feedback_history:
            try:
                session_summary = self._summarize_session_context(session)
                feedback_summary = self._summarize_feedback_history(session)
                
                ai_prompt = f"""
Generate strategic recommendations based on this session data:

Session Context:
{session_summary}

Feedback History:
{feedback_summary}

Provide 5-7 specific, actionable recommendations for:
1. Improving attack success rates
2. Reducing detection risks
3. Optimizing attack path selection
4. Enhancing overall strategy
5. Specific tactical adjustments
6. Resource allocation improvements
7. Timeline optimization

Format as a list of clear, actionable recommendations.
"""
                ai_response = self.ai_analyzer.analyze_attack(ai_prompt)
                
                if ai_response and "recommendations" in ai_response:
                    return ai_response["recommendations"]
            except Exception as e:
                print(f"AI recommendation generation failed, using rule-based: {e}")
        
        # Fallback to rule-based recommendations
        recommendations = []
        
        if not session.feedback_history:
            recommendations.append("Execute initial attack chains to gather feedback data")
            return recommendations
        
        # Analyze success rates
        success_rate = 0.0
        total_results = sum(len(f.execution_results) for f in session.feedback_history)
        if total_results > 0:
            successful_results = sum(
                1 for f in session.feedback_history 
                for r in f.execution_results 
                if r.status == "success"
            )
            success_rate = successful_results / total_results
        
        if success_rate < 0.5:
            recommendations.append("Consider alternative attack vectors - current success rate is low")
        
        # Analyze detection rates
        detection_rate = 0.0
        if total_results > 0:
            detected_results = sum(
                1 for f in session.feedback_history 
                for r in f.execution_results 
                if r.detected
            )
            detection_rate = detected_results / total_results
        
        if detection_rate > 0.7:
            recommendations.append("High detection rate - consider stealthier techniques or timing adjustments")
        
        # Check iteration count
        if session.iteration_count >= session.max_iterations:
            recommendations.append("Maximum iterations reached - review results and consider manual intervention")
        
        return recommendations