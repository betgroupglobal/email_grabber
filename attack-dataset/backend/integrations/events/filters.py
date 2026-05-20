"""
Event filtering system for Integration Hub.

Filters events based on various criteria before delivery.
"""

import logging
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class FilterOperator(Enum):
    """Filter operators."""
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    IN = "in"
    NOT_IN = "not_in"
    REGEX = "regex"


@dataclass
class FilterCondition:
    """Single filter condition."""
    field: str
    operator: FilterOperator
    value: Any


@dataclass
class FilterRule:
    """Filter rule with multiple conditions."""
    rule_id: str
    name: str
    conditions: List[FilterCondition]
    logic: str = "AND"  # AND or OR
    enabled: bool = True


class EventFilter:
    """Filters events based on configured rules."""
    
    def __init__(self):
        self.rules: Dict[str, FilterRule] = {}
    
    def add_rule(self, rule: FilterRule):
        """Add a filter rule."""
        self.rules[rule.rule_id] = rule
        logger.info(f"Added filter rule: {rule.name}")
    
    def remove_rule(self, rule_id: str):
        """Remove a filter rule."""
        if rule_id in self.rules:
            del self.rules[rule_id]
            logger.info(f"Removed filter rule: {rule_id}")
    
    def enable_rule(self, rule_id: str):
        """Enable a filter rule."""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = True
    
    def disable_rule(self, rule_id: str):
        """Disable a filter rule."""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = False
    
    def should_pass(self, event: Dict[str, Any]) -> bool:
        """
        Determine if event should pass through all filters.
        
        Args:
            event: Event data
        
        Returns:
            True if event passes all filters, False otherwise
        """
        for rule in self.rules.values():
            if not rule.enabled:
                continue
            
            if not self._evaluate_rule(rule, event):
                logger.debug(f"Event filtered out by rule: {rule.name}")
                return False
        
        return True
    
    def _evaluate_rule(self, rule: FilterRule, event: Dict[str, Any]) -> bool:
        """Evaluate a single filter rule."""
        if rule.logic == "AND":
            # All conditions must be true
            return all(self._evaluate_condition(cond, event) for cond in rule.conditions)
        else:
            # At least one condition must be true
            return any(self._evaluate_condition(cond, event) for cond in rule.conditions)
    
    def _evaluate_condition(self, condition: FilterCondition, event: Dict[str, Any]) -> bool:
        """Evaluate a single filter condition."""
        # Get field value from event
        field_value = self._get_field_value(event, condition.field)
        
        # Apply operator
        operator = condition.operator
        
        if operator == FilterOperator.EQUALS:
            return field_value == condition.value
        
        elif operator == FilterOperator.NOT_EQUALS:
            return field_value != condition.value
        
        elif operator == FilterOperator.CONTAINS:
            if isinstance(field_value, str):
                return condition.value in field_value
            elif isinstance(field_value, list):
                return condition.value in field_value
            return False
        
        elif operator == FilterOperator.NOT_CONTAINS:
            if isinstance(field_value, str):
                return condition.value not in field_value
            elif isinstance(field_value, list):
                return condition.value not in field_value
            return True
        
        elif operator == FilterOperator.GREATER_THAN:
            try:
                return float(field_value) > float(condition.value)
            except (TypeError, ValueError):
                return False
        
        elif operator == FilterOperator.LESS_THAN:
            try:
                return float(field_value) < float(condition.value)
            except (TypeError, ValueError):
                return False
        
        elif operator == FilterOperator.IN:
            if isinstance(condition.value, list):
                return field_value in condition.value
            return False
        
        elif operator == FilterOperator.NOT_IN:
            if isinstance(condition.value, list):
                return field_value not in condition.value
            return True
        
        elif operator == FilterOperator.REGEX:
            import re
            try:
                pattern = re.compile(condition.value)
                if isinstance(field_value, str):
                    return bool(pattern.search(field_value))
                return False
            except re.error:
                logger.error(f"Invalid regex pattern: {condition.value}")
                return False
        
        else:
            logger.warning(f"Unknown filter operator: {operator}")
            return True
    
    def _get_field_value(self, event: Dict[str, Any], field: str) -> Any:
        """Get field value from event using dot notation."""
        keys = field.split('.')
        value = event
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        
        return value
    
    def create_preset_rules(self):
        """Create commonly used preset filter rules."""
        # Filter out health check events (too noisy)
        health_check_rule = FilterRule(
            rule_id="filter_health_checks",
            name="Filter Health Check Events",
            conditions=[
                FilterCondition(
                    field="event_type",
                    operator=FilterOperator.NOT_EQUALS,
                    value="health_check"
                )
            ],
            logic="AND",
            enabled=True
        )
        self.add_rule(health_check_rule)
        
        # Filter out low-risk OpSec events
        low_risk_opsec_rule = FilterRule(
            rule_id="filter_low_risk_opsec",
            name="Filter Low-Risk OpSec Events",
            conditions=[
                FilterCondition(
                    field="event_type",
                    operator=FilterOperator.EQUALS,
                    value="opsec_alert"
                ),
                FilterCondition(
                    field="data.risk_level",
                    operator=FilterOperator.NOT_IN,
                    value=["low", "minimal"]
                )
            ],
            logic="AND",
            enabled=False  # Disabled by default
        )
        self.add_rule(low_risk_opsec_rule)
        
        # Only deliver plugin execution events for specific plugins
        plugin_filter_rule = FilterRule(
            rule_id="filter_specific_plugins",
            name="Filter Specific Plugins",
            conditions=[
                FilterCondition(
                    field="event_type",
                    operator=FilterOperator.IN,
                    value=[
                        "plugin_execution_started",
                        "plugin_execution_completed",
                        "plugin_execution_failed"
                    ]
                ),
                FilterCondition(
                    field="data.plugin_name",
                    operator=FilterOperator.IN,
                    value=["nmap", "metasploit", "hydra"]  # Add more as needed
                )
            ],
            logic="AND",
            enabled=False  # Disabled by default
        )
        self.add_rule(plugin_filter_rule)
    
    def list_rules(self) -> List[Dict[str, Any]]:
        """List all filter rules."""
        return [
            {
                'rule_id': rule.rule_id,
                'name': rule.name,
                'conditions': [
                    {
                        'field': cond.field,
                        'operator': cond.operator.value,
                        'value': cond.value
                    }
                    for cond in rule.conditions
                ],
                'logic': rule.logic,
                'enabled': rule.enabled
            }
            for rule in self.rules.values()
        ]