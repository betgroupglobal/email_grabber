"""
Webhook delivery system for Integration Hub.

Delivers events to configured webhooks with retry logic and error handling.
"""

import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

import aiohttp

logger = logging.getLogger(__name__)


class WebhookStatus(Enum):
    """Webhook delivery status."""
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class WebhookDeliveryResult:
    """Result of webhook delivery attempt."""
    webhook_id: str
    status: WebhookStatus
    status_code: Optional[int]
    response_body: Optional[str]
    error: Optional[str]
    attempt_number: int
    timestamp: str


class WebhookDelivery:
    """Delivers events to configured webhooks."""
    
    def __init__(self, retry_max_attempts: int = 3, retry_delay: int = 5):
        self.retry_max_attempts = retry_max_attempts
        self.retry_delay = retry_delay
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Webhook configurations (in production, these would come from database)
        self.webhooks: Dict[str, Dict[str, Any]] = {}
    
    async def initialize(self):
        """Initialize HTTP session."""
        self.session = aiohttp.ClientSession()
        logger.info("Webhook delivery initialized")
    
    async def shutdown(self):
        """Shutdown HTTP session."""
        if self.session:
            await self.session.close()
            logger.info("Webhook delivery shutdown")
    
    def register_webhook(
        self,
        webhook_id: str,
        url: str,
        secret: Optional[str] = None,
        event_types: Optional[List[str]] = None,
        headers: Optional[Dict[str, str]] = None
    ):
        """
        Register a webhook configuration.
        
        Args:
            webhook_id: Unique identifier for webhook
            url: Webhook URL
            secret: Optional secret for HMAC signature
            event_types: List of event types to deliver (empty = all)
            headers: Additional headers to include
        """
        self.webhooks[webhook_id] = {
            'webhook_id': webhook_id,
            'url': url,
            'secret': secret,
            'event_types': event_types or [],
            'headers': headers or {},
            'enabled': True,
            'created_at': datetime.now().isoformat()
        }
        logger.info(f"Registered webhook: {webhook_id} -> {url}")
    
    def unregister_webhook(self, webhook_id: str):
        """Unregister a webhook configuration."""
        if webhook_id in self.webhooks:
            del self.webhooks[webhook_id]
            logger.info(f"Unregistered webhook: {webhook_id}")
    
    async def deliver_event(
        self,
        event: Dict[str, Any],
        webhook_id: Optional[str] = None
    ) -> List[WebhookDeliveryResult]:
        """
        Deliver event to webhooks.
        
        Args:
            event: Event data to deliver
            webhook_id: Specific webhook ID (optional, delivers to all if not specified)
        
        Returns:
            List of delivery results
        """
        if not self.session:
            logger.warning("Webhook delivery not initialized, skipping delivery")
            return []
        
        results = []
        
        # Determine which webhooks to deliver to
        target_webhooks = []
        if webhook_id:
            if webhook_id in self.webhooks:
                target_webhooks = [self.webhooks[webhook_id]]
        else:
            target_webhooks = [
                wh for wh in self.webhooks.values()
                if wh['enabled'] and self._should_deliver_event(wh, event)
            ]
        
        # Deliver to each webhook
        for webhook in target_webhooks:
            result = await self._deliver_to_webhook(event, webhook)
            results.append(result)
        
        return results
    
    async def _deliver_to_webhook(
        self,
        event: Dict[str, Any],
        webhook: Dict[str, Any]
    ) -> WebhookDeliveryResult:
        """
        Deliver event to a specific webhook with retry logic.
        
        Args:
            event: Event data
            webhook: Webhook configuration
        
        Returns:
            Delivery result
        """
        webhook_id = webhook['webhook_id']
        url = webhook['url']
        
        for attempt in range(1, self.retry_max_attempts + 1):
            try:
                # Prepare headers
                headers = {
                    'Content-Type': 'application/json',
                    **webhook.get('headers', {})
                }
                
                # Add signature if secret is configured
                if webhook.get('secret'):
                    signature = self._generate_signature(event, webhook['secret'])
                    headers['X-Webhook-Signature'] = signature
                
                # Deliver event
                async with self.session.post(
                    url,
                    json=event,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    response_body = await response.text()
                    
                    if response.status >= 200 and response.status < 300:
                        return WebhookDeliveryResult(
                            webhook_id=webhook_id,
                            status=WebhookStatus.DELIVERED,
                            status_code=response.status,
                            response_body=response_body,
                            error=None,
                            attempt_number=attempt,
                            timestamp=datetime.now().isoformat()
                        )
                    else:
                        # Non-success status, retry if attempts remain
                        if attempt < self.retry_max_attempts:
                            logger.warning(
                                f"Webhook delivery failed (attempt {attempt}/{self.retry_max_attempts}): "
                                f"HTTP {response.status} for {url}"
                            )
                            await asyncio.sleep(self.retry_delay)
                            continue
                        else:
                            return WebhookDeliveryResult(
                                webhook_id=webhook_id,
                                status=WebhookStatus.FAILED,
                                status_code=response.status,
                                response_body=response_body,
                                error=f"HTTP {response.status}",
                                attempt_number=attempt,
                                timestamp=datetime.now().isoformat()
                            )
            
            except asyncio.TimeoutError:
                if attempt < self.retry_max_attempts:
                    logger.warning(
                        f"Webhook delivery timeout (attempt {attempt}/{self.retry_max_attempts}): {url}"
                    )
                    await asyncio.sleep(self.retry_delay)
                    continue
                else:
                    return WebhookDeliveryResult(
                        webhook_id=webhook_id,
                        status=WebhookStatus.FAILED,
                        status_code=None,
                        response_body=None,
                        error="Timeout",
                        attempt_number=attempt,
                        timestamp=datetime.now().isoformat()
                    )
            
            except aiohttp.ClientError as e:
                if attempt < self.retry_max_attempts:
                    logger.warning(
                        f"Webhook delivery error (attempt {attempt}/{self.retry_max_attempts}): {e}"
                    )
                    await asyncio.sleep(self.retry_delay)
                    continue
                else:
                    return WebhookDeliveryResult(
                        webhook_id=webhook_id,
                        status=WebhookStatus.FAILED,
                        status_code=None,
                        response_body=None,
                        error=str(e),
                        attempt_number=attempt,
                        timestamp=datetime.now().isoformat()
                    )
            
            except Exception as e:
                logger.error(f"Unexpected error delivering webhook: {e}")
                return WebhookDeliveryResult(
                    webhook_id=webhook_id,
                    status=WebhookStatus.FAILED,
                    status_code=None,
                    response_body=None,
                    error=str(e),
                    attempt_number=attempt,
                    timestamp=datetime.now().isoformat()
                )
        
        # Should not reach here, but just in case
        return WebhookDeliveryResult(
            webhook_id=webhook_id,
            status=WebhookStatus.FAILED,
            status_code=None,
            response_body=None,
            error="Max retries exceeded",
            attempt_number=self.retry_max_attempts,
            timestamp=datetime.now().isoformat()
        )
    
    def _should_deliver_event(self, webhook: Dict[str, Any], event: Dict[str, Any]) -> bool:
        """Determine if event should be delivered to webhook based on event type filter."""
        event_types = webhook.get('event_types', [])
        
        # If no event types specified, deliver all events
        if not event_types:
            return True
        
        # Check if event type matches
        event_type = event.get('event_type')
        return event_type in event_types
    
    def _generate_signature(self, event: Dict[str, Any], secret: str) -> str:
        """Generate HMAC signature for webhook."""
        import hmac
        import hashlib
        
        # Convert event to JSON string
        event_json = json.dumps(event, sort_keys=True)
        
        # Generate HMAC-SHA256 signature
        signature = hmac.new(
            secret.encode(),
            event_json.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return f"sha256={signature}"
    
    async def test_webhook(self, webhook_id: str) -> WebhookDeliveryResult:
        """
        Test a webhook with a sample event.
        
        Args:
            webhook_id: Webhook ID to test
        
        Returns:
            Delivery result
        """
        if webhook_id not in self.webhooks:
            raise ValueError(f"Webhook not found: {webhook_id}")
        
        # Create test event
        test_event = {
            'event_id': 'test_event',
            'event_type': 'test',
            'timestamp': datetime.now().isoformat(),
            'source': 'webhook_test',
            'data': {
                'test': True,
                'message': 'This is a test event'
            }
        }
        
        return await self._deliver_to_webhook(test_event, self.webhooks[webhook_id])
    
    def list_webhooks(self) -> List[Dict[str, Any]]:
        """List all registered webhooks."""
        return list(self.webhooks.values())