"""
Tool Recommendation API for offensive security operations.
Provides intelligent tool recommendations based on attack scenarios and OpSec requirements.
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
from enum import Enum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    """Risk levels for tools."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ToolRecommendationRequest(BaseModel):
    """Request model for tool recommendations."""
    attack_scenario: str = Field(..., description="Attack scenario or objective")
    mitre_tactic: Optional[str] = Field(None, description="MITRE ATT&CK tactic")
    max_risk_level: RiskLevel = Field(RiskLevel.HIGH, description="Maximum acceptable risk level")
    platform: Optional[str] = Field(None, description="Target platform")
    min_stealth_level: int = Field(0, description="Minimum stealth level (0-100)")
    max_noise_level: int = Field(100, description="Maximum noise level (0-100)")
    include_alternatives: bool = Field(True, description="Include alternative tools")


class ToolInfo(BaseModel):
    """Tool information model."""
    name: str
    category: str
    subcategory: Optional[str]
    description: str
    opsec_considerations: str
    detection_methods: List[str]
    mitre_tactic: str
    risk_level: str
    noise_level: int
    stealth_level: int
    platform: List[str]
    recommendation_score: Optional[int] = None
    rationale: Optional[str] = None


class ToolRecommendationResponse(BaseModel):
    """Response model for tool recommendations."""
    attack_scenario: str
    primary_recommendation: ToolInfo
    alternative_tools: List[ToolInfo]
    opsec_summary: Dict[str, Any]
    total_tools_considered: int


class OpSecAssessmentRequest(BaseModel):
    """Request model for OpSec assessment."""
    tools: List[str] = Field(..., description="List of tool names to assess")
    target_environment: Optional[str] = Field(None, description="Target environment description")


class OpSecAssessmentResponse(BaseModel):
    """Response model for OpSec assessment."""
    overall_risk_level: str
    tool_assessments: List[Dict[str, Any]]
    combined_detection_methods: List[str]
    recommendations: List[str]
    evasion_opportunities: List[str]


# Create FastAPI app
app = FastAPI(
    title="Tool Recommendation API",
    description="Intelligent tool recommendations for offensive security operations",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


# Database connection
def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(
        host='localhost',
        port=5432,
        database='attack_db',
        user='opsec',
        password='opsec',
        cursor_factory=RealDictCursor
    )


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Tool Recommendation API",
        "version": "1.0.0",
        "endpoints": {
            "recommend": "/api/v1/recommend",
            "assess": "/api/v1/assess",
            "tools": "/api/v1/tools",
            "categories": "/api/v1/categories"
        }
    }


@app.get("/api/v1/tools", response_model=List[ToolInfo])
async def list_tools(
    category: Optional[str] = Query(None, description="Filter by category"),
    risk_level: Optional[str] = Query(None, description="Filter by risk level"),
    platform: Optional[str] = Query(None, description="Filter by platform"),
    min_stealth: int = Query(0, description="Minimum stealth level"),
    limit: int = Query(50, description="Maximum results")
):
    """List available offensive tools with filtering."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        query = "SELECT * FROM offensive_tools WHERE 1=1"
        params = []
        
        if category:
            query += " AND category = %s"
            params.append(category)
        
        if risk_level:
            query += " AND risk_level = %s"
            params.append(risk_level)
        
        if platform:
            query += " AND %s = ANY(platform)"
            params.append(platform)
        
        query += " AND stealth_level >= %s"
        params.append(min_stealth)
        
        query += " ORDER BY stealth_level DESC LIMIT %s"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        tools = [ToolInfo(**row) for row in rows]
        return tools
        
    except Exception as e:
        logger.error(f"Failed to list tools: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.get("/api/v1/tools/{tool_name}", response_model=ToolInfo)
async def get_tool_info(tool_name: str):
    """Get detailed information about a specific tool."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM offensive_tools WHERE name = %s",
            (tool_name,)
        )
        row = cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Tool not found")
        
        return ToolInfo(**row)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get tool info: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.get("/api/v1/categories")
async def list_categories():
    """List available tool categories."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DISTINCT category, COUNT(*) as tool_count FROM offensive_tools GROUP BY category ORDER BY tool_count DESC"
        )
        rows = cursor.fetchall()
        
        categories = [
            {"category": row['category'], "tool_count": row['tool_count']}
            for row in rows
        ]
        
        return {"categories": categories}
        
    except Exception as e:
        logger.error(f"Failed to list categories: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.post("/api/v1/recommend", response_model=ToolRecommendationResponse)
async def recommend_tools(request: ToolRecommendationRequest):
    """Get tool recommendations based on attack scenario."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Build query based on request parameters
        query = "SELECT * FROM offensive_tools WHERE 1=1"
        params = []
        
        # Filter by MITRE tactic if specified
        if request.mitre_tactic:
            query += " AND mitre_tactic = %s"
            params.append(request.mitre_tactic)
        
        # Filter by risk level
        risk_levels = ['low', 'medium', 'high', 'critical']
        max_risk_index = risk_levels.index(request.max_risk_level.value)
        allowed_risk_levels = risk_levels[:max_risk_index + 1]
        query += f" AND risk_level = ANY(%s)"
        params.append(allowed_risk_levels)
        
        # Filter by platform if specified
        if request.platform:
            query += " AND %s = ANY(platform)"
            params.append(request.platform)
        
        # Filter by stealth and noise levels
        query += " AND stealth_level >= %s AND noise_level <= %s"
        params.extend([request.min_stealth_level, request.max_noise_level])
        
        query += " ORDER BY stealth_level DESC, noise_level ASC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        if not rows:
            raise HTTPException(status_code=404, detail="No tools found matching criteria")
        
        # Calculate recommendation scores based on scenario matching
        scored_tools = []
        scenario_keywords = request.attack_scenario.lower().split()
        
        for row in rows:
            tool = dict(row)
            score = 50  # Base score
            
            # Boost score for keyword matches in description
            description_lower = tool['description'].lower()
            for keyword in scenario_keywords:
                if keyword in description_lower:
                    score += 10
            
            # Boost score for high stealth
            score += (tool['stealth_level'] - 50) // 2
            
            # Penalty for high risk
            if tool['risk_level'] == 'critical':
                score -= 30
            elif tool['risk_level'] == 'high':
                score -= 15
            
            tool['recommendation_score'] = min(100, max(0, score))
            scored_tools.append(tool)
        
        # Sort by recommendation score
        scored_tools.sort(key=lambda x: x['recommendation_score'], reverse=True)
        
        # Select primary recommendation
        primary_tool = scored_tools[0]
        primary_tool['rationale'] = f"Selected based on stealth level ({primary_tool['stealth_level']}), " \
                                 f"risk level ({primary_tool['risk_level']}), and scenario relevance"
        
        # Select alternatives
        alternative_tools = scored_tools[1:6] if len(scored_tools) > 1 else []
        
        # Generate OpSec summary
        opsec_summary = {
            "primary_tool_risk": primary_tool['risk_level'],
            "primary_tool_noise": primary_tool['noise_level'],
            "primary_tool_stealth": primary_tool['stealth_level'],
            "detection_methods": primary_tool['detection_methods'],
            "opsec_considerations": primary_tool['opsec_considerations']
        }
        
        return ToolRecommendationResponse(
            attack_scenario=request.attack_scenario,
            primary_recommendation=ToolInfo(**primary_tool),
            alternative_tools=[ToolInfo(**tool) for tool in alternative_tools],
            opsec_summary=opsec_summary,
            total_tools_considered=len(scored_tools)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to recommend tools: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.post("/api/v1/assess", response_model=OpSecAssessmentResponse)
async def assess_opsec(request: OpSecAssessmentRequest):
    """Assess OpSec implications of tool combination."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Get information for each tool
        tool_data = []
        all_detection_methods = set()
        
        for tool_name in request.tools:
            cursor.execute(
                "SELECT * FROM offensive_tools WHERE name = %s",
                (tool_name,)
            )
            row = cursor.fetchone()
            
            if row:
                tool = dict(row)
                tool_data.append(tool)
                all_detection_methods.update(tool['detection_methods'])
        
        if not tool_data:
            raise HTTPException(status_code=404, detail="No valid tools found")
        
        # Calculate overall risk level
        risk_scores = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}
        max_risk_score = max(risk_scores.get(tool['risk_level'], 2) for tool in tool_data)
        
        if max_risk_score >= 4:
            overall_risk = 'critical'
        elif max_risk_score >= 3:
            overall_risk = 'high'
        elif max_risk_score >= 2:
            overall_risk = 'medium'
        else:
            overall_risk = 'low'
        
        # Generate tool assessments
        tool_assessments = []
        for tool in tool_data:
            assessment = {
                "tool": tool['name'],
                "risk_level": tool['risk_level'],
                "noise_level": tool['noise_level'],
                "stealth_level": tool['stealth_level'],
                "detection_methods": tool['detection_methods'],
                "opsec_considerations": tool['opsec_considerations']
            }
            tool_assessments.append(assessment)
        
        # Generate recommendations
        recommendations = []
        high_noise_tools = [tool['name'] for tool in tool_data if tool['noise_level'] > 70]
        if high_noise_tools:
            recommendations.append(f"Consider timing delays for: {', '.join(high_noise_tools)}")
        
        high_risk_tools = [tool['name'] for tool in tool_data if tool['risk_level'] in ['high', 'critical']]
        if high_risk_tools:
            recommendations.append(f"High-risk tools detected: {', '.join(high_risk_tools)}. Use with explicit authorization.")
        
        # Generate evasion opportunities
        evasion_opportunities = []
        for tool in tool_data:
            if 'stealthier' in tool['opsec_considerations'].lower():
                evasion_opportunities.append(f"{tool['name']}: Consider alternative stealthier methods")
            if 'passive' in tool['opsec_considerations'].lower():
                evasion_opportunities.append(f"{tool['name']}: Use passive mode if available")
        
        return OpSecAssessmentResponse(
            overall_risk_level=overall_risk,
            tool_assessments=tool_assessments,
            combined_detection_methods=list(all_detection_methods),
            recommendations=recommendations,
            evasion_opportunities=evasion_opportunities
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to assess OpSec: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)