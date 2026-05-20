"""
Event publisher for Integration Hub.

Publishes events to Redis Pub/Sub for real-time event distribution.
"""

import logging
import json
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Event types for integration hub."""
    PLUGIN_LOADED = "plugin_loaded"
    PLUGIN_UNLOADED = "plugin_unloaded"
    PLUGIN_EXECUTION_STARTED = "plugin_execution_started"
    PLUGIN_EXECUTION_COMPLETED = "plugin_execution_completed"
    PLUGIN_EXECUTION_FAILED = "plugin_execution_failed"
    OPERATION_STARTED = "operation_started"
    OPERATION_COMPLETED = "operation_completed"
    OPERATION_FAILED = "operation_failed"
    MONITORING_STARTED = "monitoring_started"
    MONITORING_STOPPED = "monitoring_stopped"
    MONITORING_ALERT = "monitoring_alert"
    OPSEC_ALERT = "opsec_alert"
    HEALTH_CHECK = "health_check"
    CUSTOM = "custom"


@dataclass
class Event:
    """Event data structure."""
    event_id: str
    event_type: EventType
    timestamp: str
    source: str
    data: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        result = {
            'event_id': self.event_id,
            'event_type': self.event_type.value,
            'timestamp': self.timestamp,
            'source': self.source,
            'data': self.data
        }
        if self.metadata:
            result['metadata'] = self.metadata
        return result
    
    def to_json(self) -> str:
        """Convert event to JSON string."""
        return json.dumps(self.to_dict())


class EventPublisher:
    """Publishes events to Redis Pub/Sub."""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis_client: Optional[redis.Redis] = None
        self._connected = False
        
        # Event channels
        self.channels = {
            'all': 'integration_hub:events:all',
            'plugins': 'integration_hub:events:plugins',
            'operations': 'integration_hub:events:operations',
            'monitoring': 'integration_hub:events:monitoring',
            'opsec': 'integration_hub:events:opsec',
            'health': 'integration_hub:events:health'
        }
    
    async def connect(self):
        """Connect to Redis."""
        try:
            self.redis_client = redis.from_url(self.redis_url)
            await self.redis_client.ping()
            self._connected = True
            logger.info(f"Event publisher connected to Redis at {self.redis_url}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self._connected = False
    
    async def disconnect(self):
        """Disconnect from Redis."""
        if self.redis_client:
            await self.redis_client.close()
            self._connected = False
            logger.info("Event publisher disconnected from Redis")
    
    async def publish(
        self,
        event_type: EventType,
        source: str,
        data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        channels: Optional[List[str]] = None
    ) -> str:
        """
        Publish an event.
        
        Args:
            event_type: Type of event
            source: Source of the event (plugin name, service name, etc.)
            data: Event data
            metadata: Optional metadata
            channels: Specific channels to publish to (default: auto-determine)
        
        Returns:
            Event ID
        """
        if not self._connected:
            logger.warning("Event publisher not connected, skipping event publication")
            return None
        
        # Generate event ID
        event_id = f"evt_{datetime.now().timestamp()}_{source}"
        
        # Create event
        event = Event(
            event_id=event_id,
            event_type=event_type,
            timestamp=datetime.now().isoformat(),
            source=source,
            data=data,
            metadata=metadata
        )
        
        # Determine channels if not specified
        if channels is None:
            channels = self._determine_channels(event_type)
        
        # Publish to channels
        event_json = event.to_json()
        published_count = 0
        
        for channel in channels:
            try:
                channel_name = self.channels.get(channel, f"integration_hub:events:{channel}")
                await self.redis_client.publish(channel_name, event_json)
                published_count += 1
            except Exception as e:
                logger.error(f"Failed to publish to channel {channel}: {e}")
        
        logger.debug(f"Published event {event_id} to {published_count} channels")
        return event_id
    
    async def publish_plugin_loaded(self, plugin_name: str, plugin_info: Dict[str, Any]):
        """Publish plugin loaded event."""
        await self.publish(
            event_type=EventType.PLUGIN_LOADED,
            source=plugin_name,
            data={
                'plugin_name': plugin_name,
                'plugin_info': plugin_info
            },
            channels=['all', 'plugins']
        )
    
    async def publish_plugin_execution_started(
        self,
        plugin_name: str,
        engagement_id: str,
        target: str,
        parameters: Dict[str, Any]
    ):
        """Publish plugin execution started event."""
        await self.publish(
            event_type=EventType.PLUGIN_EXECUTION_STARTED,
            source=plugin_name,
            data={
                'plugin_name': plugin_name,
                'engagement_id': engagement_id,
                'target': target,
                'parameters': parameters
            },
            channels=['all', 'plugins']
        )
    
    async def publish_plugin_execution_completed(
        self,
        plugin_name: str,
        engagement_id: str,
        target: str,
        success: bool,
        execution_time: float,
        output: Optional[Dict[str, Any]] = None
    ):
        """Publish plugin execution completed event."""
        await self.publish(
            event_type=EventType.PLUGIN_EXECUTION_COMPLETED,
            source=plugin_name,
            data={
                'plugin_name': plugin_name,
                'engagement_id': engagement_id,
                'target': target,
                'success': success,
                'execution_time': execution_time,
                'output': output
            },
            channels=['all', 'plugins']
        )
    
    async def publish_plugin_execution_failed(
        self,
        plugin_name: str,
        engagement_id: str,
        target: str,
        error: str,
        execution_time: float
    ):
        """Publish plugin execution failed event."""
        await self.publish(
            event_type=EventType.PLUGIN_EXECUTION_FAILED,
            source=plugin_name,
            data={
                'plugin_name': plugin_name,
                'engagement_id': engagement_id,
                'target': target,
                'error': error,
                'execution_time': execution_time
            },
            channels=['all', 'plugins']
        )
    
    async def publish_operation_started(
        self,
        operation_id: str,
        operation_type: str,
        target: str,
        engagement_id: str
    ):
        """Publish operation started event."""
        await self.publish(
            event_type=EventType.OPERATION_STARTED,
            source=operation_type,
            data={
                'operation_id': operation_id,
                'operation_type': operation_type,
                'target': target,
                'engagement_id': engagement_id
            },
            channels=['all', 'operations']
        )
    
    async def publish_operation_completed(
        self,
        operation_id: str,
        operation_type: str,
        success: bool,
        duration: float,
        results: Optional[Dict[str, Any]] = None
    ):
        """Publish operation completed event."""
        await self.publish(
            event_type=EventType.OPERATION_COMPLETED,
            source=operation_type,
            data={
                'operation_id': operation_id,
                'operation_type': operation_type,
                'success': success,
                'duration': duration,
                'results': results
            },
            channels=['all', 'operations']
        )
    
    async def publish_monitoring_started(
        self,
        session_id: str,
        targets: List[str],
        interval: int
    ):
        """Publish monitoring started event."""
        await self.publish(
            event_type=EventType.MONITORING_STARTED,
            source='monitoring',
            data={
                'session_id': session_id,
                'targets': targets,
                'interval': interval
            },
            channels=['all', 'monitoring']
        )
    
    async def publish_monitoring_alert(
        self,
        session_id: str,
        target: str,
        alert_type: str,
        message: str
    ):
        """Publish monitoring alert event."""
        await self.publish(
            event_type=EventType.MONITORING_ALERT,
            source='monitoring',
            data={
                'session_id': session_id,
                'target': target,
                'alert_type': alert_type,
                'message': message
            },
            channels=['all', 'monitoring']
        )
    
    async def publish_opsec_alert(
        self,
        plugin_name: str,
        operation: str,
        risk_level: str,
        recommendations: List[str]
    ):
        """Publish OpSec alert event."""
        await self.publish(
            event_type=EventType.OPSEC_ALERT,
            source=plugin_name,
            data={
                'plugin_name': plugin_name,
                'operation': operation,
                'risk_level': risk_level,
                'recommendations': recommendations
            },
            channels=['all', 'opsec']
        )
    
    def _determine_channels(self, event_type: EventType) -> List[str]:
        """Determine which channels to publish to based on event type."""
        # Always publish to 'all'
        channels = ['all']
        
        # Add specific channels based on event type
        if event_type in [
            EventType.PLUGIN_LOADED,
            EventType.PLUGIN_UNLOADED,
            EventType.PLUGIN_EXECUTION_STARTED,
            EventType.PLUGIN_EXECUTION_COMPLETED,
            EventType.PLUGIN_EXECUTION_FAILED
        ]:
            channels.append('plugins')
        
        elif event_type in [
            EventType.OPERATION_STARTED,
            EventType.OPERATION_COMPLETED,
            EventType.OPERATION_FAILED
        ]:
            channels.append('operations')
        
        elif event_type in [
            EventType.MONITORING_STARTED,
            EventType.MONITORING_STOPPED,
            EventType.MONITORING_ALERT
        ]:
            channels.append('monitoring')
        
        elif event_type == EventType.OPSEC_ALERT:
            channels.append('opsec')
        
        elif event_type == EventType.HEALTH_CHECK:
            channels.append('health')
        
        return channels