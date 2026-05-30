"""
OpSec Assessment Layer for Integration Hub.

Provides operational security assessment capabilities including:
- Risk scoring engine
- Detection method mapping
- Evasion recommendation generation
- OpSec Monitor integration
"""

from .assessor import OpSecAssessor
from .scorer import RiskScorer
from .mapper import DetectionMethodMapper

__all__ = [
    'OpSecAssessor',
    'RiskScorer',
    'DetectionMethodMapper'
]