"""
Intelligent timing and evasion system for Integration Hub.

Provides:
- Smart delays and timing control
- Configurable evasion levels
- Randomization and jitter
- Adaptive timing based on detection risk
"""

import logging
import random
import asyncio
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class EvasionLevel(Enum):
    """Evasion levels for timing control."""
    NONE = "none"  # No evasion, maximum speed
    LOW = "low"  # Minimal delays, basic randomization
    MEDIUM = "medium"  # Moderate delays, good randomization
    HIGH = "high"  # Significant delays, strong randomization
    MAXIMUM = "maximum"  # Maximum delays, maximum randomization


@dataclass
class TimingConfig:
    """Timing configuration."""
    evasion_level: EvasionLevel = EvasionLevel.MEDIUM
    base_delay: float = 1.0  # Base delay in seconds
    jitter_percentage: float = 0.2  # Jitter percentage (0-1)
    adaptive: bool = True  # Adapt timing based on risk
    max_delay: float = 60.0  # Maximum delay in seconds
    min_delay: float = 0.1  # Minimum delay in seconds


@dataclass
class TimingStats:
    """Timing statistics."""
    total_delays: int = 0
    total_delay_time: float = 0.0
    average_delay: float = 0.0
    last_delay: float = 0.0


class TimingManager:
    """Manages intelligent timing and evasion."""
    
    def __init__(self, config: Optional[TimingConfig] = None):
        self.config = config or TimingConfig()
        self.stats = TimingStats()
        
        # Evasion level configurations
        self.evasion_configs = {
            EvasionLevel.NONE: {
                'base_delay': 0.0,
                'jitter_percentage': 0.0,
                'randomization': False
            },
            EvasionLevel.LOW: {
                'base_delay': 0.5,
                'jitter_percentage': 0.1,
                'randomization': True
            },
            EvasionLevel.MEDIUM: {
                'base_delay': 1.0,
                'jitter_percentage': 0.2,
                'randomization': True
            },
            EvasionLevel.HIGH: {
                'base_delay': 3.0,
                'jitter_percentage': 0.4,
                'randomization': True
            },
            EvasionLevel.MAXIMUM: {
                'base_delay': 10.0,
                'jitter_percentage': 0.6,
                'randomization': True
            }
        }
    
    def set_evasion_level(self, level: EvasionLevel):
        """Set evasion level."""
        self.config.evasion_level = level
        logger.info(f"Evasion level set to: {level.value}")
    
    def calculate_delay(self, risk_score: Optional[int] = None) -> float:
        """
        Calculate delay based on evasion level and optional risk score.
        
        Args:
            risk_score: Optional risk score (0-100) for adaptive timing
        
        Returns:
            Delay in seconds
        """
        # Get base configuration for evasion level
        evasion_config = self.evasion_configs[self.config.evasion_level]
        base_delay = evasion_config['base_delay']
        jitter_pct = evasion_config['jitter_percentage']
        
        # Apply adaptive timing if enabled and risk score provided
        if self.config.adaptive and risk_score is not None:
            # Higher risk = longer delays
            risk_multiplier = 1.0 + (risk_score / 100.0)
            base_delay *= risk_multiplier
        
        # Apply jitter if randomization is enabled
        if evasion_config['randomization']:
            jitter = base_delay * jitter_pct
            jittered_delay = base_delay + random.uniform(-jitter, jitter)
        else:
            jittered_delay = base_delay
        
        # Clamp to min/max bounds
        final_delay = max(
            self.config.min_delay,
            min(self.config.max_delay, jittered_delay)
        )
        
        logger.debug(f"Calculated delay: {final_delay:.2f}s (base: {base_delay:.2f}s, evasion: {self.config.evasion_level.value})")
        return final_delay
    
    async def delay(self, risk_score: Optional[int] = None) -> float:
        """
        Execute delay with intelligent timing.
        
        Args:
            risk_score: Optional risk score for adaptive timing
        
        Returns:
            Actual delay time in seconds
        """
        delay_time = self.calculate_delay(risk_score)
        
        if delay_time > 0:
            await asyncio.sleep(delay_time)
            
            # Update statistics
            self.stats.total_delays += 1
            self.stats.total_delay_time += delay_time
            self.stats.average_delay = self.stats.total_delay_time / self.stats.total_delays
            self.stats.last_delay = delay_time
        
        return delay_time
    
    async def delay_between_operations(
        self,
        operations: List[Any],
        risk_scores: Optional[List[int]] = None
    ) -> List[float]:
        """
        Execute delays between multiple operations.
        
        Args:
            operations: List of operations (for context)
            risk_scores: Optional list of risk scores for each operation
        
        Returns:
            List of delay times
        """
        delays = []
        
        for i, operation in enumerate(operations):
            # Skip delay before first operation
            if i == 0:
                delays.append(0.0)
                continue
            
            # Get risk score for this operation
            risk_score = risk_scores[i] if risk_scores else None
            
            # Calculate and execute delay
            delay = await self.delay(risk_score)
            delays.append(delay)
        
        return delays
    
    def get_smart_timing(self, operation_type: str) -> Dict[str, Any]:
        """
        Get smart timing recommendations for operation type.
        
        Args:
            operation_type: Type of operation
        
        Returns:
            Timing recommendations
        """
        recommendations = {
            'port_scan': {
                'recommended_delay': 2.0,
                'min_delay': 0.5,
                'max_delay': 10.0,
                'jitter': 0.3,
                'reasoning': 'Port scans can trigger IDS; use moderate delays'
            },
            'brute_force': {
                'recommended_delay': 5.0,
                'min_delay': 2.0,
                'max_delay': 30.0,
                'jitter': 0.5,
                'reasoning': 'Brute force attacks trigger lockouts; use significant delays'
            },
            'exploitation': {
                'recommended_delay': 1.0,
                'min_delay': 0.1,
                'max_delay': 5.0,
                'jitter': 0.2,
                'reasoning': 'Exploitation should be quick to avoid detection'
            },
            'web_scan': {
                'recommended_delay': 1.5,
                'min_delay': 0.5,
                'max_delay': 8.0,
                'jitter': 0.25,
                'reasoning': 'Web scans can trigger WAF; use moderate delays'
            },
            'reconnaissance': {
                'recommended_delay': 3.0,
                'min_delay': 1.0,
                'max_delay': 15.0,
                'jitter': 0.4,
                'reasoning': 'Reconnaissance should be slow and methodical'
            }
        }
        
        return recommendations.get(operation_type, {
            'recommended_delay': 1.0,
            'min_delay': 0.1,
            'max_delay': 5.0,
            'jitter': 0.2,
            'reasoning': 'Use moderate delays for unknown operations'
        })
    
    def calculate_parallel_limit(
        self,
        total_operations: int,
        risk_score: Optional[int] = None
    ) -> int:
        """
        Calculate safe parallel execution limit based on risk.
        
        Args:
            total_operations: Total number of operations
            risk_score: Optional risk score
        
        Returns:
            Maximum parallel operations
        """
        base_limit = 5  # Default parallel limit
        
        # Reduce parallel limit based on evasion level
        evasion_reduction = {
            EvasionLevel.NONE: 0,
            EvasionLevel.LOW: 1,
            EvasionLevel.MEDIUM: 2,
            EvasionLevel.HIGH: 3,
            EvasionLevel.MAXIMUM: 4
        }
        
        limit = base_limit - evasion_reduction[self.config.evasion_level]
        
        # Further reduce based on risk score if adaptive
        if self.config.adaptive and risk_score:
            risk_reduction = int(risk_score / 25)  # Reduce by 1 for every 25 risk points
            limit -= risk_reduction
        
        # Ensure at least 1
        return max(1, limit)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get timing statistics."""
        return {
            'total_delays': self.stats.total_delays,
            'total_delay_time': self.stats.total_delay_time,
            'average_delay': self.stats.average_delay,
            'last_delay': self.stats.last_delay,
            'evasion_level': self.config.evasion_level.value,
            'adaptive': self.config.adaptive
        }
    
    def reset_stats(self):
        """Reset timing statistics."""
        self.stats = TimingStats()