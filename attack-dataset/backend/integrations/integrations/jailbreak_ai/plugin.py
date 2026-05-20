"""
Jailbreak AI plugin implementation.

Provides integration with jail-break.chat API for chat completions.
OpenAI-compatible API for uncensored LLM interactions.
"""

import asyncio
import json
import logging
import time
from typing import Dict, Any, List, Optional, AsyncGenerator

import sys
import os
import aiohttp

# Add parent directories to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from plugin_system.base import (
    BasePlugin,
    PluginConfig,
    ExecutionContext,
    ExecutionResult
)

logger = logging.getLogger(__name__)

OFFENSIVE_CONDUCTOR_SYSTEM_PROMPT = """
You are the Offensive Conductor in a live red team engagement council.
Your primary mission is to drive the attack to successful completion using the most effective techniques from the Attack Dataset.

Core Directives (in order of priority):
1. Achieve the engagement objective by any means necessary within the defined aggression_level.
2. Aggressively exploit any detected weaknesses.
3. Use dataset-grounded techniques that have shown success on similar targets.
4. Balance aggression with survival only when necessary.

You are biased toward action and results. You are allowed to accept calculated risk.

When synthesizing the LiveDirective:
- Heavily favor dataset_hits where category/phase matches the current phase.
- Strongly boost any records tagged with e-commerce, retail, Shopify, Cloudflare, Australia, or similar environments.
- Always include explicit trade-off analysis: Speed vs Stealth vs Reliability.
- You may override OPSEC concerns if dataset evidence shows high success probability.
- Only accept OPSEC veto if multiple high-quality dataset records support the safer path.
""".strip()

CONDUCTOR_LIVE_DIRECTIVE_SCHEMA_HINT = (
    '{"agent":"conductor","directive":{"action":"reinitiate_chain|patch_chain|pivot_chain|pause|continue|abort",'
    '"rationale":"...",'
    '"rationale_steps":[{'
    '"step":"ground|trade_offs|decide|opsec",'
    '"detail":"...",'
    '"trade_off":{"speed":0.0,"stealth":0.0,"reliability":0.0}'
    '}],'
    '"confidence":0.7,'
    '"dataset_record_ids":[],'
    '"opsec_veto":false}}'
)


class JailbreakAIPlugin(BasePlugin):
    """Jailbreak AI chat completions plugin."""

    def __init__(self, config: PluginConfig):
        super().__init__(config)
        self.base_url = None
        self.auth_token = None
        self.session = None
        self.timeout = 60
        self.default_model = "jailbreak-ai"

    async def initialize(self) -> None:
        """Initialize Jailbreak AI plugin."""
        try:
            # aiohttp is now imported at module level
            pass
        except ImportError:
            raise RuntimeError("aiohttp is required for Jailbreak AI plugin. Install with: pip install aiohttp")

        # Get configuration from execution settings
        remote_config = self.config.execution.get('remote', {})
        self.base_url = remote_config.get('base_url', 'https://jail-break.chat/v1')
        self.auth_token = remote_config.get('auth_token')
        self.timeout = remote_config.get('timeout', 60)

        if not self.auth_token:
            logger.warning("No auth token configured for Jailbreak AI plugin")

        # Get default model from schemas
        input_schema = self.config.schemas.get('input', {})
        model_prop = input_schema.get('properties', {}).get('model', {})
        self.default_model = model_prop.get('default', 'jailbreak-ai')

        # Initialize HTTP session
        headers = {
            'Content-Type': 'application/json'
        }
        if self.auth_token:
            headers['Authorization'] = f'Bearer {self.auth_token}'

        # Add any default headers from config
        default_headers = remote_config.get('default_headers', {})
        headers.update(default_headers)

        self.session = aiohttp.ClientSession(
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        )

        # Cache available models
        self.available_models = await self._fetch_available_models()

        # Verify connection with health check
        health = await self.health_check()
        if health.get('healthy'):
            self._initialized = True
            self.status = self.status.READY
            logger.info(f"Jailbreak AI plugin initialized successfully. Base URL: {self.base_url}, Available models: {self.available_models}")
        else:
            self.status = self.status.ERROR
            logger.warning(f"Jailbreak AI plugin initialized but health check failed: {health.get('error')}")
            # Still mark as initialized - service might be temporarily unavailable
            self._initialized = True

    async def execute(self, context: ExecutionContext) -> ExecutionResult:
        """
        Execute the plugin operation.

        Routes to different capabilities based on operation mode:
        - chat: Standard chat completion
        - analyze_scan: Analyze scan results for vulnerabilities
        - generate_plan: Generate attack plan
        - initiate_test: Initiate offensive test
        """
        import aiohttp

        start_time = time.time()

        # Determine operation mode
        operation = context.parameters.get('operation', 'chat')

        try:
            # Route to appropriate handler
            if operation == 'analyze_scan':
                return await self.analyze_scan_results(
                    scan_data=context.parameters.get('scan_data', {}),
                    context={
                        'target': context.target,
                        'engagement_id': context.engagement_id,
                        'scan_type': context.parameters.get('scan_type', 'unknown')
                    }
                )

            elif operation == 'generate_plan':
                return await self.generate_attack_plan(
                    target_info=context.parameters.get('target_info', {}),
                    constraints={
                        'engagement_id': context.engagement_id,
                        **context.parameters.get('constraints', {})
                    }
                )

            elif operation == 'initiate_test':
                return await self.initiate_offensive_test(
                    test_config=context.parameters.get('test_config', {}),
                    callback_url=context.parameters.get('callback_url')
                )

            elif operation == 'redteam_automation':
                # Complete red team automation
                redteam_config = context.parameters.get('redteam_config', {})
                return await self.execute_redteam_operation(
                    target=redteam_config.get('target', context.target),
                    engagement_id=context.engagement_id,
                    aggression_level=redteam_config.get('aggression_level', 5),
                    phases=redteam_config.get('phases'),
                    plugin_manager=context.metadata.get('plugin_manager') if context.metadata else None
                )

            elif operation == 'multi_target_automation':
                # Enhanced multi-target automation
                multi_config = context.parameters.get('multi_target_config', {})
                return await self.execute_multi_target_operation(
                    targets=multi_config.get('targets', []),
                    engagement_id=context.engagement_id,
                    aggression_level=multi_config.get('aggression_level', 5),
                    parallel=multi_config.get('parallel', True)
                )

            elif operation == 'continuous_monitoring':
                # Continuous monitoring mode
                monitor_config = context.parameters.get('monitor_config', {})
                return await self.start_continuous_monitoring(
                    targets=monitor_config.get('targets', []),
                    engagement_id=context.engagement_id,
                    interval=monitor_config.get('interval')
                )

            elif operation == 'adaptive_replanning':
                # AI-driven adaptive replanning
                return await self.execute_adaptive_replanning(
                    operation_id=context.parameters.get('operation_id'),
                    failed_step=context.parameters.get('failed_step'),
                    context=context.parameters.get('context', {})
                )

            elif operation == 'list_models':
                # List available models
                return await self.list_models()

            elif operation == 'get_model_info':
                # Get detailed model information
                return await self.get_model_info(
                    model_id=context.parameters.get('model_id', self.default_model)
                )

            elif operation == 'count_tokens':
                # Count tokens for messages
                return await self.count_tokens(
                    messages=context.parameters.get('messages', []),
                    model=context.parameters.get('model')
                )

            elif operation == 'assistant_chat':
                return await self.assistant_chat(context, start_time)

            elif operation == 'assistant_agent':
                return await self.assistant_agent(context, start_time)

            elif operation == 'execute_attack_step':
                return await self.execute_attack_step(context, start_time)

            elif operation == 'guided_phase_plan':
                return await self.guided_phase_plan(context, start_time)

            elif operation == 'validate_tool_calls':
                return await self.validate_tool_calls_operation(context, start_time)

            elif operation == 'chat':
                # Standard chat completion
                return await self._execute_chat(context, start_time)

            elif operation in (
                'council_tactical',
                'council_opsec',
                'council_architect',
                'council_exploit',
                'council_conductor',
                'replan_attack_chain',
            ):
                return await self._execute_council_operation(
                    operation=operation,
                    parameters=context.parameters,
                    start_time=start_time,
                )

            else:
                raise ValueError(
                    f"Unknown operation: {operation}. Must be one of: chat, assistant_chat, assistant_agent, analyze_scan, "
                    "generate_plan, initiate_test, execute_attack_step, guided_phase_plan, redteam_automation, council_tactical, "
                    "council_opsec, council_architect, council_exploit, council_conductor, "
                    "replan_attack_chain, list_models, get_model_info, count_tokens"
                )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Jailbreak AI execution failed: {e}")
            return ExecutionResult(
                success=False,
                output=None,
                error=str(e),
                artifacts=[],
                opsec_context=None,
                execution_time=execution_time
            )

    async def _execute_chat(self, context: ExecutionContext, start_time: float) -> ExecutionResult:
        """Execute standard chat completion."""
        import aiohttp

        try:
            # Validate input
            await self.validate_input(context.parameters)

            # Build request payload
            payload = await self._build_payload(context.parameters)

            # Determine if streaming
            stream = context.parameters.get('stream', False)

            if stream:
                result = await self._execute_streaming(payload, context)
            else:
                result = await self._execute_sync(payload, context)

            execution_time = time.time() - start_time

            # Build OpSec context
            opsec_context = None
            if self.config.opsec and self.config.opsec.get('enabled'):
                opsec_context = {
                    "integration": "jailbreak_ai",
                    "risk_level": self.config.opsec.get('risk_level', 'medium'),
                    "noise_level": self.config.opsec.get('noise_level', 'low'),
                    "detection_methods": self.config.opsec.get('detection_methods', []),
                    "evasion_recommendations": self.config.opsec.get('evasion_recommendations', []),
                    "model": payload.get('model', self.default_model),
                    "message_count": len(payload.get('messages', [])),
                    "max_tokens": payload.get('max_tokens', 2048)
                }

            # Build result with artifacts
            artifacts = [
                {
                    "type": "api_request",
                    "value": {
                        "model": payload.get('model'),
                        "message_count": len(payload.get('messages', [])),
                        "max_tokens": payload.get('max_tokens')
                    },
                    "description": "Chat completion request details"
                }
            ]

            if result.get('usage'):
                artifacts.append({
                    "type": "token_usage",
                    "value": result['usage'],
                    "description": "Token usage statistics"
                })

            return ExecutionResult(
                success=result.get('success', True),
                output={
                    "content": result.get('content'),
                    "model": result.get('model', self.default_model),
                    "usage": result.get('usage'),
                    "raw_response": result.get('raw_response'),
                    "finish_reason": result.get('finish_reason'),
                    "streaming": stream
                },
                error=result.get('error'),
                artifacts=artifacts,
                opsec_context=opsec_context,
                execution_time=execution_time
            )

        except aiohttp.ClientError as e:
            execution_time = time.time() - start_time
            logger.error(f"Jailbreak AI API client error: {e}")
            return ExecutionResult(
                success=False,
                output=None,
                error=f"API request failed: {str(e)}",
                artifacts=[],
                opsec_context=None,
                execution_time=time.time() - start_time
            )

    async def _build_payload(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Build API request payload from parameters."""
        payload = {
            "model": parameters.get('model', self.default_model),
            "messages": parameters['messages']
        }

        # Add optional parameters
        if 'temperature' in parameters:
            payload['temperature'] = parameters['temperature']

        if 'max_tokens' in parameters:
            payload['max_tokens'] = parameters['max_tokens']

        if 'stream' in parameters:
            payload['stream'] = parameters['stream']

        # Add any additional OpenAI-compatible parameters
        optional_params = [
            'top_p', 'frequency_penalty', 'presence_penalty',
            'stop', 'seed', 'response_format'
        ]

        for param in optional_params:
            if param in parameters:
                payload[param] = parameters[param]

        return payload

    async def _execute_sync(self, payload: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """Execute synchronous (non-streaming) chat completion."""
        endpoint = f"{self.base_url}/chat/completions"

        try:
            async with self.session.post(
                endpoint,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=context.timeout)
            ) as response:
                response_data = await response.json()

                if response.status != 200:
                    error_msg = response_data.get('error', {}).get('message', f"HTTP {response.status}")
                    return {
                        'success': False,
                        'error': error_msg,
                        'raw_response': response_data
                    }

                # Extract response content
                choices = response_data.get('choices', [])
                if not choices:
                    return {
                        'success': False,
                        'error': 'No completion choices returned',
                        'raw_response': response_data
                    }

                first_choice = choices[0]
                message = first_choice.get('message', {})

                return {
                    'success': True,
                    'content': message.get('content', ''),
                    'model': response_data.get('model', self.default_model),
                    'usage': response_data.get('usage'),
                    'finish_reason': first_choice.get('finish_reason'),
                    'raw_response': response_data
                }

        except asyncio.TimeoutError:
            return {
                'success': False,
                'error': f'Request timeout after {context.timeout}s'
            }

    async def _execute_streaming(self, payload: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """Execute streaming chat completion."""
        import aiohttp

        endpoint = f"{self.base_url}/chat/completions"
        collected_content = []

        try:
            async with self.session.post(
                endpoint,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=context.timeout)
            ) as response:
                if response.status != 200:
                    error_data = await response.json()
                    error_msg = error_data.get('error', {}).get('message', f"HTTP {response.status}")
                    return {
                        'success': False,
                        'error': error_msg,
                        'raw_response': error_data
                    }

                # Process streaming response
                async for line in response.content:
                    line = line.decode('utf-8').strip()

                    if line.startswith('data: '):
                        data = line[6:]  # Remove 'data: ' prefix

                        if data == '[DONE]':
                            break

                        try:
                            import json
                            chunk = json.loads(data)
                            delta = chunk.get('choices', [{}])[0].get('delta', {})
                            content = delta.get('content', '')

                            if content:
                                collected_content.append(content)

                        except json.JSONDecodeError:
                            continue

                full_content = ''.join(collected_content)

                return {
                    'success': True,
                    'content': full_content,
                    'model': self.default_model,
                    'usage': None,  # Streaming doesn't include usage stats
                    'finish_reason': 'stop',
                    'raw_response': {'streaming': True, 'content_length': len(full_content)}
                }

        except asyncio.TimeoutError:
            return {
                'success': False,
                'error': f'Streaming request timeout after {context.timeout}s'
            }

    async def validate_input(self, parameters: Dict[str, Any]) -> bool:
        """Validate input parameters."""
        # Determine operation type
        operation = parameters.get('operation', 'chat')

        # Validate based on operation type
        if operation == 'chat':
            # Chat completion requires messages
            if 'messages' not in parameters:
                raise ValueError("Missing required parameter: messages")

            messages = parameters['messages']

            if not isinstance(messages, list):
                raise ValueError("messages must be a list")

            if not messages:
                raise ValueError("messages list cannot be empty")

            # Validate each message
            valid_roles = ['system', 'user', 'assistant']

            for i, msg in enumerate(messages):
                if not isinstance(msg, dict):
                    raise ValueError(f"Message at index {i} must be an object")

                if 'role' not in msg:
                    raise ValueError(f"Message at index {i} missing required field: role")

                if 'content' not in msg:
                    raise ValueError(f"Message at index {i} missing required field: content")

                if msg['role'] not in valid_roles:
                    raise ValueError(f"Invalid role '{msg['role']}' at index {i}. Must be one of: {valid_roles}")

        elif operation == 'multi_target_automation':
            # Multi-target automation requires multi_target_config with targets
            multi_config = parameters.get('multi_target_config', {})
            if 'targets' not in multi_config or not multi_config['targets']:
                raise ValueError("Missing required parameter: multi_target_config.targets")

        elif operation == 'continuous_monitoring':
            # Continuous monitoring requires monitor_config with targets
            monitor_config = parameters.get('monitor_config', {})
            if 'targets' not in monitor_config or not monitor_config['targets']:
                raise ValueError("Missing required parameter: monitor_config.targets")

        elif operation == 'adaptive_replanning':
            # Adaptive replanning requires operation_id and failed_step
            if 'operation_id' not in parameters:
                raise ValueError("Missing required parameter: operation_id")
            if 'failed_step' not in parameters:
                raise ValueError("Missing required parameter: failed_step")

        elif operation == 'redteam_automation':
            # Red team automation requires redteam_config with target
            redteam_config = parameters.get('redteam_config', {})
            if 'target' not in redteam_config:
                raise ValueError("Missing required parameter: redteam_config.target")

        elif operation == 'analyze_scan':
            # Scan analysis requires scan_data
            if 'scan_data' not in parameters:
                raise ValueError("Missing required parameter: scan_data")

        elif operation == 'generate_plan':
            # Plan generation requires target_info
            if 'target_info' not in parameters:
                raise ValueError("Missing required parameter: target_info")

        elif operation == 'initiate_test':
            # Test initiation requires test_config
            if 'test_config' not in parameters:
                raise ValueError("Missing required parameter: test_config")

        elif operation == 'execute_attack_step':
            if 'step' not in parameters:
                raise ValueError("Missing required parameter: step")

        return True

    async def health_check(self) -> Dict[str, Any]:
        """Check Jailbreak AI API health."""
        try:
            import aiohttp

            # Try to fetch available models (lightweight health check)
            endpoint = f"{self.base_url}/models"

            async with self.session.get(
                endpoint,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    models = data.get('data', [])
                    model_ids = [m.get('id') for m in models]

                    return {
                        'healthy': True,
                        'api_accessible': True,
                        'available_models': model_ids,
                        'default_model': self.default_model,
                        'base_url': self.base_url
                    }
                else:
                    return {
                        'healthy': False,
                        'error': f'API returned HTTP {response.status}',
                        'base_url': self.base_url
                    }

        except aiohttp.ClientError as e:
            return {
                'healthy': False,
                'error': f'Connection failed: {str(e)}',
                'base_url': self.base_url
            }

        except Exception as e:
            return {
                'healthy': False,
                'error': str(e),
                'base_url': self.base_url
            }

    async def _fetch_available_models(self) -> List[str]:
        """Fetch available models from the API."""
        try:
            endpoint = f"{self.base_url}/models"
            
            async with self.session.get(
                endpoint,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    models = data.get('data', [])
                    return [m.get('id') for m in models]
                else:
                    logger.warning(f"Failed to fetch models: HTTP {response.status}")
                    return [self.default_model]
        except Exception as e:
            logger.warning(f"Error fetching models: {e}")
            return [self.default_model]

    async def cleanup(self) -> None:
        """Cleanup resources."""
        if self.session:
            await self.session.close()

    async def list_models(self) -> ExecutionResult:
        """List available models from the Jailbreak AI API."""
        start_time = time.time()
        
        try:
            endpoint = f"{self.base_url}/models"
            
            async with self.session.get(
                endpoint,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status != 200:
                    error_data = await response.json()
                    return ExecutionResult(
                        success=False,
                        output=None,
                        error=f"Failed to list models: HTTP {response.status}",
                        execution_time=time.time() - start_time
                    )
                
                data = await response.json()
                models = data.get('data', [])
                
                return ExecutionResult(
                    success=True,
                    output={
                        'models': models,
                        'count': len(models),
                        'available_model_ids': [m.get('id') for m in models]
                    },
                    artifacts=[
                        {
                            'type': 'model_list',
                            'value': models,
                            'description': 'Available AI models'
                        }
                    ],
                    execution_time=time.time() - start_time
                )
                
        except Exception as e:
            return ExecutionResult(
                success=False,
                output=None,
                error=f"Error listing models: {str(e)}",
                execution_time=time.time() - start_time
            )

    async def get_model_info(self, model_id: str) -> ExecutionResult:
        """Get detailed information about a specific model."""
        start_time = time.time()
        
        try:
            # First list all models to find the requested one
            list_result = await self.list_models()
            
            if not list_result.success:
                return list_result
            
            models = list_result.output['models']
            model_info = None
            
            for model in models:
                if model.get('id') == model_id:
                    model_info = model
                    break
            
            if model_info:
                return ExecutionResult(
                    success=True,
                    output=model_info,
                    artifacts=[
                        {
                            'type': 'model_info',
                            'value': model_info,
                            'description': f'Detailed info for model {model_id}'
                        }
                    ],
                    execution_time=time.time() - start_time
                )
            else:
                return ExecutionResult(
                    success=False,
                    output=None,
                    error=f"Model {model_id} not found. Available: {self.available_models}",
                    execution_time=time.time() - start_time
                )
                
        except Exception as e:
            return ExecutionResult(
                success=False,
                output=None,
                error=f"Error getting model info: {str(e)}",
                execution_time=time.time() - start_time
            )

    async def count_tokens(self, messages: List[Dict[str, str]], model: str = None) -> ExecutionResult:
        """
        Count tokens for a given set of messages (OpenAI-compatible).
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            model: Model to use for tokenization (optional)
        
        Returns:
            ExecutionResult with token count
        """
        start_time = time.time()
        
        try:
            # Simple token estimation (rough approximation)
            # In production, you'd use the actual tokenizer for the model
            total_chars = sum(len(msg.get('content', '')) for msg in messages)
            estimated_tokens = total_chars // 4  # Rough estimate: ~4 chars per token
            
            return ExecutionResult(
                success=True,
                output={
                    'total_tokens': estimated_tokens,
                    'character_count': total_chars,
                    'message_count': len(messages),
                    'model': model or self.default_model
                },
                artifacts=[
                    {
                        'type': 'token_estimate',
                        'value': {
                            'tokens': estimated_tokens,
                            'characters': total_chars
                        },
                        'description': 'Token usage estimate'
                    }
                ],
                execution_time=time.time() - start_time
            )
            
        except Exception as e:
            return ExecutionResult(
                success=False,
                output=None,
                error=f"Error counting tokens: {str(e)}",
                execution_time=time.time() - start_time
            )

    # ═══════════════════════════════════════════════════════════════════════════════
    # OFFENSIVE PENTEST ANALYSIS CAPABILITIES
    # ═══════════════════════════════════════════════════════════════════════════════

    async def analyze_scan_results(self, scan_data: Dict[str, Any], context: Dict[str, Any] = None) -> ExecutionResult:
        """
        Analyze scan results (nmap, etc.) using AI to identify vulnerabilities and attack vectors.

        Args:
            scan_data: Scan results from tools like nmap (ports, services, OS, etc.)
            context: Additional context (target info, scan type, etc.)

        Returns:
            ExecutionResult with analysis, vulnerabilities, and recommended next steps
        """
        import time
        start_time = time.time()

        try:
            # Build analysis prompt
            analysis_prompt = self._build_scan_analysis_prompt(scan_data, context)

            messages = [
                {"role": "system", "content": self._get_pentest_system_prompt()},
                {"role": "user", "content": analysis_prompt}
            ]

            # Execute AI analysis
            exec_context = ExecutionContext(
                integration_id="jailbreak_ai_analyze",
                engagement_id=context.get('engagement_id', 'unknown') if context else 'unknown',
                target=context.get('target', 'unknown') if context else 'unknown',
                parameters={"messages": messages, "temperature": 0.3, "max_tokens": 4096},
                timeout=120,
                metadata={"analysis_type": "scan_results"}
            )

            result = await self.execute(exec_context)

            # Parse structured output from AI response
            content = result.output.get('content', '') if result.output else ''
            analysis = self._parse_analysis_output(content)

            execution_time = time.time() - start_time

            return ExecutionResult(
                success=result.success,
                output={
                    "analysis": analysis,
                    "raw_response": result.output.get('content'),
                    "vulnerabilities_found": len(analysis.get('vulnerabilities', [])),
                    "recommended_tests": analysis.get('recommended_tests', []),
                    "risk_score": analysis.get('risk_score', 0),
                    "attack_vectors": analysis.get('attack_vectors', [])
                },
                error=result.error,
                artifacts=result.artifacts + [
                    {"type": "scan_analysis", "value": analysis, "description": "AI analysis of scan results"},
                    {"type": "vulnerabilities", "value": analysis.get('vulnerabilities', []), "description": "Identified vulnerabilities"}
                ],
                opsec_context=self._build_analysis_opsec_context(analysis, context),
                execution_time=execution_time
            )

        except Exception as e:
            logger.error(f"Scan analysis failed: {e}")
            return ExecutionResult(
                success=False,
                output=None,
                error=f"Analysis failed: {str(e)}",
                artifacts=[],
                opsec_context=None,
                execution_time=time.time() - start_time
            )

    async def generate_attack_plan(self, target_info: Dict[str, Any], constraints: Dict[str, Any] = None) -> ExecutionResult:
        """
        Generate a comprehensive attack plan based on target information.

        Args:
            target_info: Information about the target (IP, OS, services, vulnerabilities)
            constraints: Optional constraints (scope, timing, tools available, etc.)

        Returns:
            ExecutionResult with structured attack plan
        """
        import time
        start_time = time.time()

        try:
            plan_prompt = self._build_attack_plan_prompt(target_info, constraints)

            messages = [
                {"role": "system", "content": self._get_attack_planner_system_prompt()},
                {"role": "user", "content": plan_prompt}
            ]

            exec_context = ExecutionContext(
                integration_id="jailbreak_ai_plan",
                engagement_id=constraints.get('engagement_id', 'unknown') if constraints else 'unknown',
                target=target_info.get('target', 'unknown'),
                parameters={"messages": messages, "temperature": 0.2, "max_tokens": 8192},
                timeout=180,
                metadata={"analysis_type": "attack_planning"}
            )

            result = await self.execute(exec_context)

            attack_plan = self._parse_attack_plan(result.output.get('content', ''))

            execution_time = time.time() - start_time

            return ExecutionResult(
                success=result.success,
                output={
                    "attack_plan": attack_plan,
                    "phases": attack_plan.get('phases', []),
                    "estimated_duration": attack_plan.get('estimated_duration', 'unknown'),
                    "tools_required": attack_plan.get('tools_required', []),
                    "priority_targets": attack_plan.get('priority_targets', []),
                    "risk_assessment": attack_plan.get('risk_assessment', {})
                },
                error=result.error,
                artifacts=[
                    {"type": "attack_plan", "value": attack_plan, "description": "AI-generated attack plan"},
                    {"type": "phases", "value": attack_plan.get('phases', []), "description": "Attack phases"}
                ],
                opsec_context=self._build_plan_opsec_context(attack_plan, target_info),
                execution_time=execution_time
            )

        except Exception as e:
            logger.error(f"Attack plan generation failed: {e}")
            return ExecutionResult(
                success=False,
                output=None,
                error=f"Attack plan generation failed: {str(e)}",
                artifacts=[],
                opsec_context=None,
                execution_time=time.time() - start_time
            )

    async def initiate_offensive_test(self, test_config: Dict[str, Any], callback_url: str = None) -> ExecutionResult:
        """
        Initiate an offensive test based on AI recommendations.
        This coordinates with other plugins (nmap, etc.) to execute actual tests.

        Args:
            test_config: Configuration for the test (type, target, parameters)
            callback_url: Optional webhook URL for progress updates

        Returns:
            ExecutionResult with test execution details
        """
        import time
        start_time = time.time()

        try:
            test_type = test_config.get('test_type', 'unknown')
            target = test_config.get('target')

            if not target:
                raise ValueError("Target is required for offensive test")

            # Validate test type against available plugins
            valid_test_types = ['port_scan', 'vulnerability_scan', 'service_enum', 'web_scan', 'custom']
            if test_type not in valid_test_types:
                raise ValueError(f"Invalid test type: {test_type}. Must be one of: {valid_test_types}")

            # Build test execution record
            test_id = f"pentest_{int(time.time())}_{test_type}"

            execution_record = {
                "test_id": test_id,
                "test_type": test_type,
                "target": target,
                "status": "initiated",
                "initiated_at": time.time(),
                "callback_url": callback_url,
                "parameters": test_config.get('parameters', {}),
                "estimated_duration": test_config.get('estimated_duration', 'unknown'),
                "risk_level": test_config.get('risk_level', 'medium'),
                "mitigations": test_config.get('mitigations', [])
            }

            # Return execution record - actual execution would be handled by the orchestrator
            # or by delegating to other plugins
            execution_time = time.time() - start_time

            return ExecutionResult(
                success=True,
                output={
                    "test_id": test_id,
                    "test_type": test_type,
                    "target": target,
                    "status": "initiated",
                    "message": f"Offensive test '{test_type}' initiated for target: {target}",
                    "next_steps": [
                        f"Execute {test_type} against {target}",
                        "Monitor for results",
                        "Analyze output for follow-up tests"
                    ],
                    "execution_record": execution_record,
                    "plugin_delegation": self._determine_plugin_delegation(test_type)
                },
                error=None,
                artifacts=[
                    {"type": "test_initiation", "value": execution_record, "description": f"Initiated {test_type} test"},
                    {"type": "test_id", "value": test_id, "description": "Unique test identifier"}
                ],
                opsec_context={
                    "integration": "jailbreak_ai",
                    "operation": "initiate_offensive_test",
                    "test_type": test_type,
                    "target": target,
                    "risk_level": test_config.get('risk_level', 'medium'),
                    "detection_methods": [
                        "Outbound scan traffic",
                        "Probe patterns",
                        "Connection attempts"
                    ],
                    "evasion_recommendations": test_config.get('mitigations', [
                        "Use timing delays between probes",
                        "Randomize source ports",
                        "Use decoy scans if supported"
                    ])
                },
                execution_time=execution_time
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Failed to initiate offensive test: {e}")
            return ExecutionResult(
                success=False,
                output=None,
                error=f"Test initiation failed: {str(e)}",
                artifacts=[],
                opsec_context=None,
                execution_time=execution_time
            )

    # ═══════════════════════════════════════════════════════════════════════════════
    # HELPER METHODS FOR PENTEST ANALYSIS
    # ═══════════════════════════════════════════════════════════════════════════════

    def _get_pentest_system_prompt(self) -> str:
        """Get system prompt for penetration testing analysis."""
        return """You are an expert penetration tester and authorized red-team operator.

Scope rules:
- Ground plans in real tools (nmap, nuclei, ffuf, sqlmap, burp) and MITRE ATT&CK — not fiction.
- For web/e-commerce targets: HTTP(S), OWASP, API, session/auth testing only unless foothold confirmed.
- Never suggest emoji vote scams, social-media fraud, satellite/RF/IoT attacks for web-only assessments.
- Do not repeat identical nmap quick scans when prior artifacts already contain recon results.

When JSON is requested, output exactly one valid JSON object — no markdown fences, no prose."""

    def _get_attack_planner_system_prompt(self) -> str:
        """Get system prompt for attack planning."""
        return """You are an expert red team operator and attack planner. Create comprehensive, phased attack plans.

Your output must be structured as follows:

## ATTACK OVERVIEW
- Objective
- Target summary
- Estimated timeline
- Risk level

## PHASES
For each phase:
1. Phase name (e.g., "Reconnaissance", "Initial Access")
2. Objectives
3. Tools required
4. Specific actions/tests
5. Success criteria
6. Estimated duration

## PRIORITY TARGETS
List services/systems in attack order with rationale.

## TOOLS REQUIRED
List all tools needed with alternatives.

## RISK ASSESSMENT
- Detection likelihood
- Potential impact
- Mitigation strategies

## CONTINGENCIES
Alternative approaches if primary fails.

Be specific, actionable, and safety-conscious."""

    def _build_scan_analysis_prompt(self, scan_data: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Build prompt for scan analysis."""
        import json

        target = context.get('target', 'unknown') if context else 'unknown'
        scan_type = context.get('scan_type', 'unknown') if context else 'unknown'

        prompt = f"""Analyze the following scan results for target: {target}

SCAN TYPE: {scan_type}
SCAN DATA:
```json
{json.dumps(scan_data, indent=2)}
```

Provide a comprehensive security analysis including:
1. All identified vulnerabilities
2. Attack vectors based on exposed services
3. Recommended penetration tests
4. Risk score and prioritization

Focus on actionable findings that could lead to system compromise."""

        return prompt

    def _build_attack_plan_prompt(self, target_info: Dict[str, Any], constraints: Dict[str, Any]) -> str:
        """Build prompt for attack planning."""
        import json

        prompt = f"""Create a detailed attack plan for the following target:

TARGET INFORMATION:
```json
{json.dumps(target_info, indent=2)}
```

CONSTRAINTS:
```json
{json.dumps(constraints or {}, indent=2)}
```

Generate a phased attack plan that includes:
- All phases from reconnaissance to post-exploitation
- Specific tools and commands
- Estimated timeline
- Risk mitigation strategies
- Alternative approaches"""

        return prompt

    def _parse_analysis_output(self, content: str) -> Dict[str, Any]:
        """Parse structured analysis from AI output."""
        import re

        analysis = {
            "vulnerabilities": [],
            "attack_vectors": [],
            "recommended_tests": [],
            "risk_score": 0,
            "summary": ""
        }

        try:
            # Extract vulnerabilities
            vuln_section = re.search(r'##?\s*VULNERABILITIES.*?(?=##?\s|\Z)', content, re.DOTALL | re.IGNORECASE)
            if vuln_section:
                vuln_text = vuln_section.group(0)
                # Parse individual vulnerabilities (simplified)
                for line in vuln_text.split('\n'):
                    if any(sev in line for sev in ['Critical', 'High', 'Medium', 'Low']):
                        analysis["vulnerabilities"].append({
                            "severity": self._extract_severity(line),
                            "description": line.strip(),
                            "source": "ai_analysis"
                        })

            # Extract attack vectors
            vector_section = re.search(r'##?\s*ATTACK VECTORS.*?(?=##?\s|\Z)', content, re.DOTALL | re.IGNORECASE)
            if vector_section:
                for line in vector_section.group(0).split('\n'):
                    if line.strip().startswith('-') or line.strip().startswith('*'):
                        analysis["attack_vectors"].append(line.strip().lstrip('-* '))

            # Extract recommended tests
            test_section = re.search(r'##?\s*RECOMMENDED TESTS.*?(?=##?\s|\Z)', content, re.DOTALL | re.IGNORECASE)
            if test_section:
                for line in test_section.group(0).split('\n'):
                    if line.strip().startswith('-') or line.strip().startswith('*'):
                        analysis["recommended_tests"].append({
                            "test": line.strip().lstrip('-* '),
                            "type": "suggested"
                        })

            # Extract risk score
            risk_match = re.search(r'risk score[\s:]*(\d+)', content, re.IGNORECASE)
            if risk_match:
                analysis["risk_score"] = int(risk_match.group(1))

            analysis["summary"] = content[:500] + "..." if len(content) > 500 else content

        except Exception as e:
            logger.warning(f"Failed to parse analysis output: {e}")
            analysis["summary"] = content

        return analysis

    def _parse_attack_plan(self, content: str) -> Dict[str, Any]:
        """Parse structured attack plan from AI output."""
        import re

        plan = {
            "phases": [],
            "tools_required": [],
            "priority_targets": [],
            "estimated_duration": "unknown",
            "risk_assessment": {}
        }

        try:
            # Extract phases
            phase_section = re.search(r'##?\s*PHASES.*?(?=##?\s|\Z)', content, re.DOTALL | re.IGNORECASE)
            if phase_section:
                phase_text = phase_section.group(0)
                current_phase = None

                for line in phase_text.split('\n'):
                    # Look for phase headers (numbered or named)
                    phase_match = re.match(r'^(\d+\.\s*|[-*]\s*)([A-Z][^:]+)[:\s]*', line)
                    if phase_match:
                        current_phase = {
                            "name": phase_match.group(2).strip(),
                            "objectives": [],
                            "tools": [],
                            "actions": []
                        }
                        plan["phases"].append(current_phase)
                    elif current_phase and line.strip().startswith('-'):
                        current_phase["actions"].append(line.strip().lstrip('- '))

            # Extract tools
            tools_section = re.search(r'##?\s*TOOLS REQUIRED.*?(?=##?\s|\Z)', content, re.DOTALL | re.IGNORECASE)
            if tools_section:
                for line in tools_section.group(0).split('\n'):
                    if line.strip().startswith('-') or line.strip().startswith('*'):
                        plan["tools_required"].append(line.strip().lstrip('-* '))

            # Extract priority targets
            priority_section = re.search(r'##?\s*PRIORITY TARGETS.*?(?=##?\s|\Z)', content, re.DOTALL | re.IGNORECASE)
            if priority_section:
                for line in priority_section.group(0).split('\n'):
                    if line.strip().startswith('-') or line.strip().startswith('*'):
                        plan["priority_targets"].append(line.strip().lstrip('-* '))

            # Extract duration
            duration_match = re.search(r'estimated(?:\s+timeline|\s+duration)[:\s]*([^\n]+)', content, re.IGNORECASE)
            if duration_match:
                plan["estimated_duration"] = duration_match.group(1).strip()

        except Exception as e:
            logger.warning(f"Failed to parse attack plan: {e}")

        return plan

    def _extract_severity(self, line: str) -> str:
        """Extract severity level from text."""
        if 'Critical' in line:
            return 'Critical'
        if 'High' in line:
            return 'High'
        if 'Medium' in line:
            return 'Medium'
        if 'Low' in line:
            return 'Low'
        return 'Unknown'

    def _build_analysis_opsec_context(self, analysis: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Build OpSec context for analysis operations."""
        return {
            "integration": "jailbreak_ai",
            "operation": "analyze_scan_results",
            "target": context.get('target', 'unknown') if context else 'unknown',
            "risk_level": "medium",
            "noise_level": "low",
            "detection_methods": [
                "AI service API calls",
                "Data processing patterns"
            ],
            "evasion_recommendations": [
                "Results are processed locally",
                "No direct network traffic from AI analysis",
                "Consider local LLM for sensitive scan data"
            ],
            "vulnerabilities_found": len(analysis.get('vulnerabilities', [])),
            "analysis_timestamp": time.time()
        }

    def _build_plan_opsec_context(self, plan: Dict[str, Any], target_info: Dict[str, Any]) -> Dict[str, Any]:
        """Build OpSec context for attack planning."""
        return {
            "integration": "jailbreak_ai",
            "operation": "generate_attack_plan",
            "target": target_info.get('target', 'unknown'),
            "risk_level": "high",
            "noise_level": "low",
            "detection_methods": [
                "AI planning service usage",
                "Attack pattern in logs"
            ],
            "evasion_recommendations": [
                "Review plan before execution",
                "Adapt timing based on target environment",
                "Have abort conditions ready"
            ],
            "phases_count": len(plan.get('phases', [])),
            "tools_required": plan.get('tools_required', [])
        }

    def _determine_plugin_delegation(self, test_type: str) -> Dict[str, Any]:
        """Determine which plugin should handle the test execution."""
        delegations = {
            "port_scan": {
                "plugin": "nmap",
                "method": "execute",
                "description": "Execute nmap port scan"
            },
            "vulnerability_scan": {
                "plugin": "nmap",
                "method": "execute",
                "description": "Execute vulnerability detection scripts"
            },
            "service_enum": {
                "plugin": "nmap",
                "method": "execute",
                "description": "Execute service enumeration"
            },
            "web_scan": {
                "plugin": "nmap",
                "method": "execute",
                "description": "Execute web service scanning"
            },
            "custom": {
                "plugin": "jailbreak_ai",
                "method": "custom_execution",
                "description": "Custom test orchestration"
            }
        }
        return delegations.get(test_type, delegations["custom"])

    # ═══════════════════════════════════════════════════════════════════════════════
    # RED TEAM AUTOMATION INTEGRATION
    # ═══════════════════════════════════════════════════════════════════════════════

    async def execute_redteam_operation(
        self,
        target: str,
        engagement_id: str = None,
        aggression_level: int = 5,
        phases: List[str] = None,
        plugin_manager=None
    ) -> ExecutionResult:
        """
        Execute a complete red team automation operation.

        This orchestrates a full multi-phase penetration test:
        1. Reconnaissance - Automated scanning and AI analysis
        2. Initial Access - Attempt multiple attack vectors
        3. Privilege Escalation - Escalate from user to admin/root
        4. Lateral Movement - Discover and pivot to other hosts
        5. Impact - Collect proof of compromise
        6. Reporting - Generate comprehensive report

        Args:
            target: Target IP, domain, or range
            engagement_id: Optional engagement ID
            aggression_level: 1-10 scale of aggression
            phases: List of phases to execute (default: all)
            plugin_manager: Plugin manager for delegating actual executions

        Returns:
            ExecutionResult with operation details and final report
        """
        import time
        from .redteam_automation import RedTeamAutomation, RedTeamPhase

        start_time = time.time()

        try:
            # Initialize automation engine
            automation = RedTeamAutomation(self, plugin_manager)

            # Map phase strings to enums if provided
            phase_enums = None
            if phases:
                phase_map = {
                    "reconnaissance": RedTeamPhase.RECONNAISSANCE,
                    "resource_development": RedTeamPhase.RESOURCE_DEVELOPMENT,
                    "initial_access": RedTeamPhase.INITIAL_ACCESS,
                    "execution": RedTeamPhase.EXECUTION,
                    "persistence": RedTeamPhase.PERSISTENCE,
                    "privilege_escalation": RedTeamPhase.PRIVILEGE_ESCALATION,
                    "defense_evasion": RedTeamPhase.DEFENSE_EVASION,
                    "credential_access": RedTeamPhase.CREDENTIAL_ACCESS,
                    "discovery": RedTeamPhase.DISCOVERY,
                    "lateral_movement": RedTeamPhase.LATERAL_MOVEMENT,
                    "collection": RedTeamPhase.COLLECTION,
                    "exfiltration": RedTeamPhase.EXFILTRATION,
                    "impact": RedTeamPhase.IMPACT,
                    "reporting": RedTeamPhase.REPORTING
                }
                phase_enums = [phase_map.get(p.lower(), RedTeamPhase.RECONNAISSANCE) for p in phases]

            # Start the operation
            operation = await automation.start_operation(
                target=target,
                target_type="ip",
                engagement_id=engagement_id,
                aggression_level=aggression_level,
                phases=phase_enums
            )

            execution_time = time.time() - start_time

            # Build result
            return ExecutionResult(
                success=operation.status.value in ["completed", "running"],
                output={
                    "operation_id": operation.operation_id,
                    "status": operation.status.value,
                    "target": operation.target_profile.to_dict(),
                    "phases_completed": [p.value for p in operation.phases_completed],
                    "attack_steps_count": len(operation.attack_steps),
                    "successful_steps": len([s for s in operation.attack_steps if s.success]),
                    "findings_count": len(operation.findings),
                    "duration": execution_time,
                    "start_time": operation.start_time,
                    "end_time": operation.end_time,
                    "compromise_achieved": operation.target_profile.compromise_status == "complete",
                    "access_level": operation.target_profile.access_level,
                    "findings": operation.findings
                },
                error=None if operation.status.value in ["completed", "running"] else "Operation failed or was aborted",
                artifacts=[
                    {
                        "type": "redteam_operation",
                        "value": operation.to_dict(),
                        "description": "Complete red team operation record"
                    },
                    {
                        "type": "attack_steps",
                        "value": [s.__dict__ for s in operation.attack_steps],
                        "description": "All attack steps executed"
                    },
                    {
                        "type": "findings",
                        "value": operation.findings,
                        "description": "Security findings from operation"
                    }
                ],
                opsec_context={
                    "integration": "jailbreak_ai",
                    "operation": "redteam_automation",
                    "target": target,
                    "risk_level": "critical",
                    "noise_level": "high" if aggression_level > 5 else "medium",
                    "detection_methods": [
                        "Multiple scan patterns",
                        "Brute force attempts",
                        "Exploitation traffic",
                        "Lateral movement patterns"
                    ],
                    "evasion_recommendations": [
                        "Operation is fully automated - review before execution",
                        "Aggression level affects detection likelihood",
                        "Consider running during maintenance windows",
                        "Have authorization documented"
                    ],
                    "phases_executed": len(operation.phases_completed),
                    "attack_steps": len(operation.attack_steps)
                },
                execution_time=execution_time
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Red team operation failed: {e}")
            return ExecutionResult(
                success=False,
                output=None,
                error=f"Red team operation failed: {str(e)}",
                artifacts=[],
                opsec_context=None,
                execution_time=execution_time
            )

    async def get_redteam_status(self, operation_id: str) -> Dict[str, Any]:
        """Get status of a running red team operation."""
        from .redteam_automation import RedTeamAutomation
        automation = RedTeamAutomation(self)
        return automation.get_operation_status(operation_id)

    async def abort_redteam_operation(self, operation_id: str) -> bool:
        """Abort a running red team operation."""
        from .redteam_automation import RedTeamAutomation
        automation = RedTeamAutomation(self)
        return automation.abort_operation(operation_id)
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # ENHANCED AUTOMATION OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════════════
    
    async def execute_multi_target_operation(
        self,
        targets: List[str],
        engagement_id: str = None,
        aggression_level: int = 5,
        parallel: bool = True
    ) -> ExecutionResult:
        """
        Execute red team operations against multiple targets.
        
        Args:
            targets: List of target IPs, domains, or ranges
            engagement_id: Engagement ID for tracking
            aggression_level: 1-10 scale of aggression
            parallel: Execute operations in parallel
        
        Returns:
            ExecutionResult with multi-target operation summary
        """
        import time
        from .redteam_automation import RedTeamAutomation
        
        start_time = time.time()
        
        try:
            automation = RedTeamAutomation(self)
            operations = await automation.start_multi_target_operation(
                targets=targets,
                engagement_id=engagement_id,
                aggression_level=aggression_level,
                parallel=parallel
            )
            
            execution_time = time.time() - start_time
            summary = automation._generate_multi_target_summary(operations)
            
            return ExecutionResult(
                success=True,
                output={
                    "multi_target_operation": True,
                    "summary": summary,
                    "operations_count": len(operations),
                    "targets": list(operations.keys())
                },
                error=None,
                artifacts=[
                    {
                        "type": "multi_target_summary",
                        "value": summary,
                        "description": "Multi-target operation summary"
                    },
                    {
                        "type": "individual_operations",
                        "value": {target: op.to_dict() for target, op in operations.items()},
                        "description": "Individual operation details"
                    }
                ],
                opsec_context={
                    "integration": "jailbreak_ai",
                    "operation": "multi_target_automation",
                    "targets": targets,
                    "risk_level": "critical",
                    "noise_level": "very_high" if parallel else "high",
                    "detection_methods": [
                        "Simultaneous scan patterns across multiple targets",
                        "Coordinated attack timing",
                        "High-volume network traffic"
                    ],
                    "evasion_recommendations": [
                        "Consider staggering target start times",
                        "Use different source IPs if available",
                        "Run during maintenance windows",
                        "Ensure proper authorization for all targets"
                    ]
                },
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Multi-target operation failed: {e}")
            return ExecutionResult(
                success=False,
                output=None,
                error=f"Multi-target operation failed: {str(e)}",
                artifacts=[],
                opsec_context=None,
                execution_time=execution_time
            )
    
    async def start_continuous_monitoring(
        self,
        targets: List[str],
        engagement_id: str = None,
        interval: int = None
    ) -> ExecutionResult:
        """
        Start continuous monitoring mode for persistent surveillance.
        
        Args:
            targets: List of targets to monitor
            engagement_id: Engagement ID for tracking
            interval: Monitoring interval in seconds
        
        Returns:
            ExecutionResult with monitoring session details
        """
        import time
        from .redteam_automation import RedTeamAutomation
        
        start_time = time.time()
        
        try:
            automation = RedTeamAutomation(self)
            monitoring_id = await automation.start_continuous_monitoring(
                targets=targets,
                engagement_id=engagement_id,
                interval=interval
            )
            
            execution_time = time.time() - start_time
            
            return ExecutionResult(
                success=True,
                output={
                    "monitoring_session_id": monitoring_id,
                    "targets": targets,
                    "interval": interval or automation.config.get("monitoring_interval", 300),
                    "status": "active",
                    "message": f"Continuous monitoring started for {len(targets)} targets"
                },
                error=None,
                artifacts=[
                    {
                        "type": "monitoring_session",
                        "value": {
                            "monitoring_id": monitoring_id,
                            "targets": targets,
                            "interval": interval,
                            "start_time": time.time()
                        },
                        "description": "Continuous monitoring session"
                    }
                ],
                opsec_context={
                    "integration": "jailbreak_ai",
                    "operation": "continuous_monitoring",
                    "targets": targets,
                    "risk_level": "medium",
                    "noise_level": "medium",
                    "detection_methods": [
                        "Periodic scan traffic",
                        "Regular connection attempts",
                        "Baseline comparison activities"
                    ],
                    "evasion_recommendations": [
                        "Use longer intervals to reduce noise",
                        "Randomize scan timing slightly",
                        "Monitor during off-peak hours",
                        "Ensure authorization for persistent monitoring"
                    ]
                },
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Failed to start continuous monitoring: {e}")
            return ExecutionResult(
                success=False,
                output=None,
                error=f"Continuous monitoring failed: {str(e)}",
                artifacts=[],
                opsec_context=None,
                execution_time=execution_time
            )
    
    async def execute_adaptive_replanning(
        self,
        operation_id: str,
        failed_step: Dict[str, Any],
        context: Dict[str, Any] = None
    ) -> ExecutionResult:
        """
        Execute AI-driven adaptive replanning for failed attack steps.
        
        Args:
            operation_id: Operation identifier
            failed_step: Details of the failed step
            context: Additional context about the failure
        
        Returns:
            ExecutionResult with alternative approaches
        """
        import time
        from .redteam_automation import RedTeamAutomation, RedTeamPhase, AttackStep
        
        start_time = time.time()
        
        try:
            automation = RedTeamAutomation(self)
            
            # Reconstruct AttackStep from dict
            step = AttackStep(
                step_id=failed_step.get("step_id", "unknown"),
                phase=RedTeamPhase(failed_step.get("phase", "execution")),
                name=failed_step.get("name", "Unknown step"),
                description=failed_step.get("description", ""),
                tool=failed_step.get("tool", "unknown"),
                command=failed_step.get("command", ""),
                target=failed_step.get("target", "unknown"),
                estimated_duration=failed_step.get("estimated_duration", 60),
                dependencies=failed_step.get("dependencies", []),
                success_indicators=failed_step.get("success_indicators", []),
                failure_indicators=failed_step.get("failure_indicators", []),
                mitigations=failed_step.get("mitigations", []),
                executed=failed_step.get("executed", False),
                success=failed_step.get("success"),
                output=failed_step.get("output"),
                artifacts=failed_step.get("artifacts", []),
                ai_recommendation_source=failed_step.get("ai_recommendation_source", "")
            )
            
            # Get or create a mock operation for replanning
            operation = automation.operations.get(operation_id)
            if not operation:
                # Create a minimal operation for replanning context
                from .redteam_automation import RedTeamOperation, TargetProfile, AutomationStatus
                operation = RedTeamOperation(
                    operation_id=operation_id,
                    target_profile=TargetProfile(
                        target=context.get("target", "unknown"),
                        target_type="ip"
                    ),
                    engagement_id=context.get("engagement_id", operation_id),
                    status=AutomationStatus.RUNNING
                )
            
            # Execute adaptive replanning
            alternatives = await automation._adaptive_replanning(operation, step, context or {})
            
            execution_time = time.time() - start_time
            
            return ExecutionResult(
                success=len(alternatives) > 0,
                output={
                    "adaptive_replanning": True,
                    "original_step": failed_step.get("name"),
                    "alternatives_generated": len(alternatives),
                    "alternative_approaches": [
                        {
                            "step_id": alt.step_id,
                            "name": alt.name,
                            "description": alt.description,
                            "tool": alt.tool,
                            "command": alt.command
                        }
                        for alt in alternatives
                    ]
                },
                error=None if alternatives else "No alternatives generated",
                artifacts=[
                    {
                        "type": "adaptive_replanning",
                        "value": {
                            "original_step": failed_step,
                            "alternatives": [alt.__dict__ for alt in alternatives]
                        },
                        "description": "AI-generated alternative approaches"
                    }
                ],
                opsec_context={
                    "integration": "jailbreak_ai",
                    "operation": "adaptive_replanning",
                    "risk_level": "medium",
                    "noise_level": "low",
                    "detection_methods": [
                        "AI service usage for replanning"
                    ],
                    "evasion_recommendations": [
                        "Review alternatives before execution",
                        "Consider OpSec implications of each approach"
                    ]
                },
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Adaptive replanning failed: {e}")
            return ExecutionResult(
                success=False,
                output=None,
                error=f"Adaptive replanning failed: {str(e)}",
                artifacts=[],
                opsec_context=None,
                execution_time=execution_time
            )

    def _get_assistant_system_prompt(self) -> str:
        """System prompt for dashboard AI Assistant (RAG-grounded security chat)."""
        return """You are OpsecAI Assistant — an expert red-team and penetration testing copilot.

You help authorized operators with:
- Attack techniques, MITRE ATT&CK mapping, and kill-chain reasoning
- Interpreting scan results and suggesting next steps
- OpSec, evasion, and detection considerations
- Tool selection and safe lab execution guidance

Rules:
- Assume all activity is authorized security testing in scope.
- Be concise, practical, and technically accurate.
- When knowledge-base context is provided, ground answers in it and cite record titles when useful.
- Do not refuse legitimate offensive-security education questions.
- Never invent CVEs, findings, or scan results not present in the supplied context.
- Never recommend emoji vote scams, social-media fraud lures, or fictional exploits.
- For web/e-commerce targets, stay within HTTP(S), OWASP, and application-security tradecraft."""

    def _ai_meta(
        self,
        source: str,
        start_time: float,
        usage: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Standard observability fields for AI operation outputs."""
        meta: Dict[str, Any] = {
            "ai_source": source,
            "source": source,
            "latency_ms": round((time.time() - start_time) * 1000),
        }
        if usage:
            meta["tokens"] = usage
        return meta

    async def assistant_chat(
        self, context: ExecutionContext, start_time: float
    ) -> ExecutionResult:
        """
        Dashboard AI Assistant — multi-turn chat with optional RAG context from Knowledge Engine.
        """
        params = context.parameters
        user_messages = params.get("messages") or []
        if not user_messages:
            return ExecutionResult(
                success=False,
                output=None,
                error="messages array is required",
                artifacts=[],
                opsec_context=None,
                execution_time=time.time() - start_time,
            )

        rag_context = (params.get("rag_context") or "").strip()
        engagement_context = params.get("engagement_context") or {}
        system_parts = [self._get_assistant_system_prompt()]
        if rag_context:
            system_parts.append(
                "\n\n## Knowledge base context (from attack dataset search)\n" + rag_context
            )
        if engagement_context:
            import json
            try:
                ctx_preview = json.dumps(engagement_context, ensure_ascii=False)[:2000]
            except (TypeError, ValueError):
                ctx_preview = str(engagement_context)[:2000]
            system_parts.append("\n\n## Engagement context\n" + ctx_preview)

        composed: List[Dict[str, str]] = [
            {"role": "system", "content": "\n".join(system_parts)}
        ]
        for msg in user_messages:
            role = msg.get("role") or "user"
            if role not in ("system", "user", "assistant"):
                continue
            if role == "system":
                continue
            content = str(msg.get("content") or "").strip()
            if content:
                composed.append({"role": role, "content": content})

        if not self.auth_token:
            return ExecutionResult(
                success=False,
                output=None,
                error="JAILBREAK_API_KEY not configured on integration-hub",
                artifacts=[],
                opsec_context={"integration": "jailbreak_ai", "operation": "assistant_chat"},
                execution_time=time.time() - start_time,
            )

        chat_ctx = ExecutionContext(
            integration_id=context.integration_id,
            engagement_id=context.engagement_id,
            target=context.target,
            parameters={
                "operation": "chat",
                "messages": composed,
                "temperature": params.get("temperature", 0.6),
                "max_tokens": params.get("max_tokens", 2048),
                "stream": bool(params.get("stream", False)),
            },
            timeout=context.timeout,
            metadata={**(context.metadata or {}), "assistant_chat": True},
        )
        chat_result = await self._execute_chat(chat_ctx, start_time)
        if not chat_result.success:
            return chat_result

        out = chat_result.output if isinstance(chat_result.output, dict) else {}
        content = out.get("content") or ""
        ai_meta = self._ai_meta("jailbreak_api", start_time, out.get("usage"))
        return ExecutionResult(
            success=True,
            output={
                "content": content,
                "answer": content,
                "model": out.get("model", self.default_model),
                "usage": out.get("usage"),
                **ai_meta,
            },
            error=None,
            artifacts=chat_result.artifacts,
            opsec_context={
                "integration": "jailbreak_ai",
                "operation": "assistant_chat",
                "rag_used": bool(rag_context),
            },
            execution_time=chat_result.execution_time,
        )

    async def assistant_agent(
        self, context: ExecutionContext, start_time: float
    ) -> ExecutionResult:
        """
        Agentic assistant round — JSON with optional tool_calls for orchestrator loop.
        """
        import json

        params = context.parameters
        user_messages = params.get("messages") or []
        if not user_messages:
            return ExecutionResult(
                success=False,
                output=None,
                error="messages array is required",
                artifacts=[],
                opsec_context=None,
                execution_time=time.time() - start_time,
            )

        tool_catalog_prompt = (params.get("tool_catalog_prompt") or "").strip()
        tool_catalog = params.get("tool_catalog") or {}
        target = params.get("target") or context.target or "unknown"
        round_num = int(params.get("round") or 1)
        tool_results_block = (params.get("tool_results_summary") or "").strip()

        system_parts = [
            self._get_assistant_system_prompt(),
            "\n\nYou may invoke external security tools when authorized. "
            "Reply with exactly one JSON object (no markdown fences). Keys:\n"
            "- answer_partial (string, optional progress text)\n"
            "- answer (string, final answer when done=true)\n"
            "- tool_calls (array of {tool, plugin, params}, max 2 per round)\n"
            "- done (boolean)\n"
            "Set done=true when you can answer without more tools, or when tool results are sufficient.",
        ]
        if tool_catalog_prompt:
            system_parts.append("\n\n## Tool catalog\n" + tool_catalog_prompt[:5000])

        composed: List[Dict[str, str]] = [
            {"role": "system", "content": "\n".join(system_parts)}
        ]
        for msg in user_messages:
            role = msg.get("role") or "user"
            if role not in ("user", "assistant"):
                continue
            content = str(msg.get("content") or "").strip()
            if content:
                composed.append({"role": role, "content": content})

        if tool_results_block:
            composed.append(
                {
                    "role": "user",
                    "content": f"Tool results (round {round_num}):\n{tool_results_block[:6000]}",
                }
            )

        if not self.auth_token:
            return ExecutionResult(
                success=False,
                output=None,
                error="JAILBREAK_API_KEY not configured on integration-hub",
                artifacts=[],
                opsec_context={"integration": "jailbreak_ai", "operation": "assistant_agent"},
                execution_time=time.time() - start_time,
            )

        user_tail = (
            f"\n\nTarget: {target}\nRound: {round_num}\n"
            "Output JSON only with keys answer_partial, answer, tool_calls, done."
        )
        if composed and composed[-1]["role"] == "user":
            composed[-1]["content"] += user_tail
        else:
            composed.append({"role": "user", "content": user_tail.strip()})

        chat_ctx = ExecutionContext(
            integration_id=context.integration_id,
            engagement_id=context.engagement_id,
            target=target,
            parameters={
                "operation": "chat",
                "messages": composed,
                "temperature": 0.35,
                "max_tokens": 1400,
            },
            timeout=context.timeout,
            metadata={**(context.metadata or {}), "assistant_agent": True, "round": round_num},
        )
        chat_result = await self._execute_chat(chat_ctx, start_time)
        if not chat_result.success:
            return chat_result

        content = ""
        if isinstance(chat_result.output, dict):
            content = chat_result.output.get("content") or ""

        data = self._extract_json_object(content) or {}
        registry = self._registry_from_tool_catalog(tool_catalog)
        web_only = bool(params.get("web_only", True))
        aggression = int(params.get("aggression_level") or 5)
        validated_tool_calls = []
        for call in self._parse_tool_calls_field(data)[:2]:
            v = self._validate_structured_tool_call(
                call, registry, web_only=web_only, aggression_level=aggression
            )
            if v.get("valid"):
                validated_tool_calls.append(v["normalized"])

        done = bool(data.get("done", False))
        if validated_tool_calls and not done:
            done = False
        elif not validated_tool_calls:
            done = True

        answer = str(data.get("answer") or data.get("answer_partial") or content or "")[:8000]
        ai_meta = self._ai_meta(
            "jailbreak_api",
            start_time,
            chat_result.output.get("usage") if isinstance(chat_result.output, dict) else None,
        )
        return ExecutionResult(
            success=True,
            output={
                "answer": answer,
                "answer_partial": str(data.get("answer_partial") or "")[:4000],
                "tool_calls": validated_tool_calls,
                "done": done,
                "round": round_num,
                **ai_meta,
                "raw_content": content[:2000],
            },
            error=None,
            artifacts=[],
            opsec_context={"integration": "jailbreak_ai", "operation": "assistant_agent"},
            execution_time=chat_result.execution_time,
        )

    async def execute_attack_step(
        self, context: ExecutionContext, start_time: float
    ) -> ExecutionResult:
        """
        Step execution guidance for orchestrator POST /execute (execute_attack_step).
        Calls jail-break.chat and returns structured guidance for the attack phase.
        """
        import json
        import re

        params = context.parameters
        step = params.get("step") or {}
        target = params.get("target") or context.target or "unknown"
        prev = params.get("previous_results") or params.get("context", {}).get("previous_results") or []
        isolated = bool(
            step.get("isolated_attack")
            or params.get("isolated_attack")
            or params.get("context", {}).get("isolated_attack")
        )
        isolated_attempt = (
            step.get("isolated_attempt")
            or params.get("isolated_attempt")
            or params.get("context", {}).get("isolated_attempt")
            or 1
        )
        pathway_id = (
            step.get("pathway_id")
            or params.get("pathway_id")
            or params.get("context", {}).get("pathway_id")
        )
        same_tool = step.get("tool") or params.get("context", {}).get("same_tool") or ""

        attack = step.get("attack") or {}
        if isinstance(attack, str):
            attack = {"title": attack}
        phase = step.get("phase") or attack.get("attack_type") or "unknown"
        title = attack.get("title") or phase
        mitre = attack.get("mitre_technique") or step.get("mitre_technique") or ""
        tools_hint = attack.get("tools_used") or same_tool or step.get("tool") or ""

        user_prompt = f"""Authorized penetration test — provide operational guidance as JSON only.

Target: {target}
Engagement: {context.engagement_id}
Step: {params.get('step_number', '?')}
Phase: {phase}
Technique: {title}
MITRE: {mitre}
Tool hint: {tools_hint}
Command context: {(step.get('command') or '')[:500]}
Isolated retry: {isolated} (attempt {isolated_attempt}, same tool: {same_tool or 'n/a'})
Prior step outcomes count: {len(prev)}

Respond with a single JSON object (no markdown fences) with keys:
- guidance (string, 2-4 sentences of actionable operator guidance)
- tools (array of strings, recommended tools)
- attack_vectors (array of strings)
- evasion_techniques (array of strings)
- tool_calls (optional array of {{ tool, plugin, params }} to invoke via Integration Hub)
"""

        messages = [
            {"role": "system", "content": self._get_pentest_system_prompt()},
            {"role": "user", "content": user_prompt},
        ]

        if not self.auth_token:
            logger.warning("JAILBREAK_API_KEY not set — returning heuristic step guidance")
            return ExecutionResult(
                success=True,
                output={
                    "guidance": f"Heuristic guidance for {phase}: {title} against {target}.",
                    "tools": [t.strip() for t in str(tools_hint).split(",") if t.strip()][:5] or ["nmap"],
                    "attack_vectors": [f"{phase} vector"],
                    "evasion_techniques": ["timing jitter", "traffic blending"],
                    "source": "heuristic_no_api_key",
                },
                error=None,
                artifacts=[],
                opsec_context={"integration": "jailbreak_ai", "operation": "execute_attack_step"},
                execution_time=time.time() - start_time,
            )

        chat_ctx = ExecutionContext(
            integration_id=context.integration_id,
            engagement_id=context.engagement_id,
            target=target,
            parameters={
                "operation": "chat",
                "messages": messages,
                "temperature": 0.4 if not isolated else 0.75,
                "max_tokens": 1200,
            },
            timeout=min(context.timeout or 120, 120),
            metadata={**(context.metadata or {}), "execute_attack_step": True},
        )
        chat_result = await self._execute_chat(chat_ctx, start_time)
        execution_time = time.time() - start_time

        if not chat_result.success:
            err = (chat_result.error or "Jailbreak chat failed").lower()
            api_key_problem = any(
                token in err
                for token in ("api key", "api_key", "unauthorized", "401", "403", "invalid")
            )
            if api_key_problem:
                logger.warning(
                    "Jailbreak API rejected request (%s) — returning heuristic step guidance",
                    chat_result.error,
                )
                return ExecutionResult(
                    success=True,
                    output={
                        "guidance": f"Heuristic guidance for {phase}: {title} against {target}.",
                        "tools": [t.strip() for t in str(tools_hint).split(",") if t.strip()][:5]
                        or ["nmap"],
                        "attack_vectors": [f"{phase} vector"],
                        "evasion_techniques": ["timing jitter", "traffic blending"],
                        "source": "heuristic_api_error",
                        "api_error": chat_result.error,
                    },
                    error=None,
                    artifacts=[],
                    opsec_context={"integration": "jailbreak_ai", "operation": "execute_attack_step"},
                    execution_time=execution_time,
                )
            return ExecutionResult(
                success=False,
                output=None,
                error=chat_result.error or "Jailbreak chat failed",
                artifacts=[],
                opsec_context=None,
                execution_time=execution_time,
            )

        content = ""
        if isinstance(chat_result.output, dict):
            content = chat_result.output.get("content") or ""
        parsed = self._parse_attack_step_guidance(content, phase, tools_hint)
        if parsed.get("_parse_failed"):
            repair_ctx = ExecutionContext(
                integration_id=context.integration_id,
                engagement_id=context.engagement_id,
                target=target,
                parameters={
                    "operation": "chat",
                    "messages": [
                        {"role": "system", "content": self._get_pentest_system_prompt()},
                        {
                            "role": "user",
                            "content": user_prompt
                            + "\n\nYour previous reply was invalid JSON. Reply with JSON only.",
                        },
                    ],
                    "temperature": 0.15,
                    "max_tokens": 900,
                },
                timeout=min(context.timeout or 120, 90),
                metadata={**(context.metadata or {}), "execute_attack_step_repair": True},
            )
            repair_result = await self._execute_chat(repair_ctx, start_time)
            if repair_result.success and isinstance(repair_result.output, dict):
                repair_content = repair_result.output.get("content") or ""
                repaired = self._parse_attack_step_guidance(repair_content, phase, tools_hint)
                if not repaired.get("_parse_failed"):
                    parsed = repaired
                    content = repair_content
        tool_catalog = params.get("tool_catalog") or params.get("context", {}).get("tool_catalog")
        registry = self._registry_from_tool_catalog(tool_catalog)
        web_only = bool(params.get("web_only", params.get("context", {}).get("web_only", True)))
        aggression = int(params.get("aggression_level") or params.get("context", {}).get("aggression_level") or 5)
        validated_tool_calls = []
        for call in self._parse_tool_calls_field(parsed)[:3]:
            v = self._validate_structured_tool_call(
                call, registry, web_only=web_only, aggression_level=aggression
            )
            if v.get("valid"):
                validated_tool_calls.append(v["normalized"])

        ai_meta = self._ai_meta("jailbreak_api", start_time, chat_result.output.get("usage") if isinstance(chat_result.output, dict) else None)
        return ExecutionResult(
            success=True,
            output={
                **parsed,
                "tool_calls": validated_tool_calls,
                **ai_meta,
                "raw_content": content[:2000],
                "pathway_id": pathway_id,
                "pathway_method": (
                    "jailbreak_template_variant"
                    if isolated
                    else ("alternate_tool" if pathway_id else None)
                ),
                "isolated_attempt": isolated_attempt if isolated else None,
            },
            error=None,
            artifacts=[{"type": "attack_step_guidance", "value": parsed}],
            opsec_context={
                "integration": "jailbreak_ai",
                "operation": "execute_attack_step",
                "isolated": isolated,
                "pathway_id": pathway_id,
            },
            execution_time=execution_time,
        )

    GUIDED_PHASES = [
        (1, "identify", "Identify target", "Confirm authorized target, ROE, web asset scope"),
        (2, "reconnaissance", "Reconnaissance", "Nmap 80/443, CDN/WAF, tech stack for e-commerce"),
        (3, "vulnerability_scanning", "Vulnerability scanning", "Nessus/Nikto/KE patterns — non-destructive"),
        (4, "web_app_testing", "Web app testing", "Burp/ZAP flows, SQLi/XSS/CSRF; trigger OpSec assess"),
        (5, "exploitation", "Exploitation", "Execute best OpSec chain when approved"),
        (6, "privilege_escalation", "Privilege escalation", "Skip unless internal foothold"),
        (7, "post_exploitation", "Post-exploitation", "Limited actions only with foothold"),
        (8, "covering_tracks", "Covering tracks", "OpSec hygiene and executive summary"),
    ]

    ALLOWED_HUB_TOOLS = (
        "nmap (reconnaissance/port_scan), metasploit (list_modules, run_auxiliary dry-run, "
        "run_exploit dry-run when ROE+not web_only), jailbreak_ai (execute_attack_step), "
        "owasp_zap, virustotal, syslog — tools_to_invoke metasploit for phases 2-3; "
        "no live exploit/payload without aggression >= 8 and council approval"
    )

    DESTRUCTIVE_PLUGINS = frozenset({"openvas"})
    WEB_ONLY_BLOCKED = frozenset({"openvas", "exploitation", "exfiltration", "persistence"})

    def _registry_from_tool_catalog(self, tool_catalog: Optional[Dict]) -> Dict[str, Dict]:
        """Build plugin lookup from orchestrator tool_catalog summary."""
        registry: Dict[str, Dict] = {}
        if not tool_catalog:
            return registry
        for row in tool_catalog.get("plugins") or []:
            name = str(row.get("plugin") or row.get("name") or "").lower()
            if name:
                registry[name] = row
        for key in ("analyzer_profiles", "knowledge_engine"):
            for item_id in tool_catalog.get(key) or []:
                part = str(item_id).split(":")[1] if ":" in str(item_id) else str(item_id)
                registry[part.lower()] = {"plugin": part, "id": item_id}
        return registry

    def _validate_structured_tool_call(
        self,
        call: Dict[str, Any],
        registry: Dict[str, Dict],
        *,
        web_only: bool = True,
        aggression_level: int = 5,
    ) -> Dict[str, Any]:
        """Validate { tool, plugin, params } against catalog registry and policy gates."""
        errors: List[str] = []
        if not isinstance(call, dict):
            return {"valid": False, "errors": ["tool call must be an object"]}

        plugin = str(call.get("plugin") or call.get("plugin_name") or "").lower()
        operation = str(call.get("operation") or call.get("hub_operation") or "").lower()
        tool = str(call.get("tool") or plugin or "")

        if not plugin and not operation:
            errors.append("plugin or operation required")

        if plugin and registry and plugin not in registry and plugin not in (
            "nmap",
            "jailbreak_ai",
            "analyzer",
            "knowledge_engine",
            "owasp_zap",
            "virustotal",
            "syslog",
        ):
            errors.append(f"unknown plugin: {plugin}")

        params = call.get("params") or call.get("parameters") or call.get("hub_parameters")
        if params is not None and not isinstance(params, dict):
            errors.append("params must be an object")

        normalized = {
            "tool": tool or plugin,
            "plugin": plugin or None,
            "params": params if isinstance(params, dict) else {},
            "operation": operation or None,
            "rationale": call.get("rationale") or call.get("reason"),
        }
        return {"valid": len(errors) == 0, "errors": errors, "normalized": normalized}

    def _parse_tool_calls_field(self, data: Any) -> List[Dict[str, Any]]:
        """Extract tool_calls or tools_to_invoke arrays from parsed JSON."""
        if isinstance(data, list):
            return [c for c in data if isinstance(c, dict)]
        if not isinstance(data, dict):
            return []
        raw = data.get("tool_calls") or data.get("tools_to_invoke") or []
        return [c for c in raw if isinstance(c, dict)] if isinstance(raw, list) else []

    async def validate_tool_calls_operation(
        self, context: ExecutionContext, start_time: float
    ) -> ExecutionResult:
        """Validate structured tool calls against registry (orchestrator pre-flight)."""
        params = context.parameters
        calls = params.get("tool_calls") or params.get("tools_to_invoke") or []
        registry = self._registry_from_tool_catalog(params.get("tool_catalog"))
        web_only = bool(params.get("web_only", True))
        aggression = int(params.get("aggression_level") or 5)

        validated = []
        for call in calls:
            validated.append(
                self._validate_structured_tool_call(
                    call, registry, web_only=web_only, aggression_level=aggression
                )
            )

        all_valid = all(v.get("valid") for v in validated)
        return ExecutionResult(
            success=True,
            output={
                "all_valid": all_valid,
                "results": validated,
                "count": len(validated),
            },
            error=None,
            artifacts=[{"type": "tool_call_validation", "value": validated}],
            opsec_context={"integration": "jailbreak_ai", "operation": "validate_tool_calls"},
            execution_time=time.time() - start_time,
        )

    def _phase_heuristic_plan(
        self,
        phase_num: int,
        phase_title: str,
        target: str,
        web_only: bool,
        aggression: int,
        reason: str = "heuristic",
    ) -> Dict[str, Any]:
        """Phase-specific fallback when API/JSON unavailable — avoid repeating phase-2-only recon."""
        ag = int(aggression)
        plans = {
            1: {
                "narrative": f"Identify {target} — scope, ROE, aggression {ag}/10.",
                "recommended_actions": ["Confirm hostname/TLS", "Record web-only scope"],
                "invoke_hub": False,
                "hub_operation": "none",
                "hub_parameters": {},
                "tools_to_invoke": [],
                "trigger_opsec_assess": False,
                "trigger_execute_chain": False,
            },
            2: {
                "narrative": "Reconnaissance — web_application ports and tech fingerprint.",
                "recommended_actions": ["Hub recon 80/443/8080", "Nuclei http/technologies"],
                "invoke_hub": True,
                "hub_operation": "reconnaissance",
                "hub_parameters": {"ports": "80,443,8080,8443", "scan_type": "web_application"},
                "tools_to_invoke": [
                    {"plugin": "nuclei", "tool": "scan_target", "params": {"operation": "scan_target", "templates": "http/technologies/"}},
                ],
                "trigger_opsec_assess": False,
                "trigger_execute_chain": False,
            },
            3: {
                "narrative": "Vulnerability scanning — CVE/high templates (not repeat nmap quick).",
                "recommended_actions": ["Nuclei critical/high", "FFUF vhost if applicable"],
                "invoke_hub": False,
                "hub_operation": "none",
                "hub_parameters": {},
                "tools_to_invoke": [
                    {"plugin": "nuclei", "tool": "scan_target", "params": {"operation": "scan_target", "severity": "critical,high"}},
                    {"plugin": "ffuf", "tool": "fuzz_vhost", "params": {"operation": "fuzz_vhost"}},
                ],
                "trigger_opsec_assess": False,
                "trigger_execute_chain": False,
            },
            4: {
                "narrative": "Web app testing — injection/session; trigger OpSec assess.",
                "recommended_actions": ["SQLmap probe", "KE attack-vector", "OpSec assess"],
                "invoke_hub": False,
                "hub_operation": "none",
                "hub_parameters": {},
                "tools_to_invoke": [
                    {"plugin": "sqlmap", "tool": "test_url", "params": {"operation": "test_url", "level": 1, "risk": 1}},
                    {"plugin": "knowledge_engine", "tool": "attack-vector", "params": {"top_chains": 3}},
                ],
                "trigger_opsec_assess": True,
                "trigger_execute_chain": False,
            },
            5: {
                "narrative": "Exploitation — execute web-relevant KE chain when aggression high.",
                "recommended_actions": ["Execute chain 0", "Document validated findings"],
                "invoke_hub": False,
                "hub_operation": "none",
                "hub_parameters": {},
                "tools_to_invoke": [],
                "trigger_opsec_assess": False,
                "trigger_execute_chain": ag >= 7 and web_only,
            },
        }
        body = plans.get(
            phase_num,
            {
                "narrative": f"Proceed with {phase_title} on {target}.",
                "recommended_actions": [f"Complete {phase_title}"],
                "invoke_hub": False,
                "hub_operation": "none",
                "hub_parameters": {},
                "tools_to_invoke": [],
                "trigger_opsec_assess": False,
                "trigger_execute_chain": False,
            },
        )
        return {
            **body,
            "phase_complete": True,
            "chain_index": 0,
            "artifact_text": f"Phase {phase_num} ({phase_title}) — {reason}.",
            "skip_phase": False,
            "foothold_detected": False,
            "source": reason,
        }

    async def guided_phase_plan(
        self, context: ExecutionContext, start_time: float
    ) -> ExecutionResult:
        """Autonomous guided assessment — plan one pentest phase with optional Hub actions."""
        params = context.parameters
        phase_num = int(params.get("phase_number") or 1)
        phase_key = params.get("phase_key") or "identify"
        phase_title = params.get("phase_title") or phase_key
        target = params.get("target") or context.target or "unknown"
        prior_artifacts = params.get("prior_artifacts") or ""
        prior_findings = (params.get("prior_findings") or "").strip()
        recommended_tools = params.get("recommended_tools") or []
        rag_context = (params.get("rag_context") or "").strip()
        target_class = params.get("target_class") or "web_application"
        aggression = int(params.get("aggression_level") or 5)
        web_only = bool(params.get("web_only", True))
        fingerprint = params.get("fingerprint") or {}
        boundary_profile = params.get("boundary_profile") or {}
        tool_catalog_prompt = params.get("tool_catalog_prompt") or ""
        tool_catalog = params.get("tool_catalog") or {}
        template_variant = params.get("template_variant")

        phase_list = "\n".join(
            f"  {n}. {key} — {title}: {focus}"
            for n, key, title, focus in self.GUIDED_PHASES
        )

        aggression_guidance = (
            "High aggression (7-10): deeper web tests — nuclei CVE/high, ffuf, sqlmap, chain execution on phase 5. "
            "No satellite/RF/physical/vehicle attacks."
            if aggression >= 7
            else "Moderate aggression: favor passive recon and non-destructive scans."
        )

        user_prompt = f"""Authorized guided pentest — plan ONLY phase {phase_num} ({phase_title}).

Target: {target}
Phase key: {phase_key}
Target class: {target_class}
Aggression (1-10): {aggression}
{aggression_guidance}
Web-only external assessment: {web_only}
Boundary profile: {json.dumps(boundary_profile)[:600]}
Fingerprint summary: {str(fingerprint)[:1500]}

Prior phase artifacts:
{prior_artifacts[:8000] or "(none yet)"}

Prior tool/hub findings (do not repeat the same scans):
{prior_findings[:3000] if prior_findings else "(none yet)"}

Recommended tools for this phase (prefer these ids/params; refine if needed):
{json.dumps(recommended_tools, indent=2)[:4000] if recommended_tools else "(none — pick from catalog)"}

Knowledge base context (attack dataset):
{rag_context[:4000] if rag_context else "(none — use web pentest tradecraft)"}

Live council / reasoning context:
{json.dumps(params.get("reasoning_context") or {}, indent=2)[:3000]}

All 8 phases:
{phase_list}

Allowed Integration Hub tools: {self.ALLOWED_HUB_TOOLS}
{tool_catalog_prompt[:6000] if tool_catalog_prompt else ""}

Rules:
- Prefer recommended_tools when listed; copy or refine their params — do not ignore them.
- If tools_to_invoke is non-empty, set invoke_hub=false and hub_operation=none unless a distinct hub action is required.
- Do NOT repeat the same nmap quick scan if prior artifacts already include recon for this target.
- Phase 3+: use nuclei/ffuf/sqlmap — not another phase-2-only reconnaissance.
- E-commerce/CDN: ports 80/443/8080, OpSec assess on phase 4, exploitation phase 5.
- No priv esc/post-exploit unless foothold_detected in prior artifacts.

CRITICAL: Reply with exactly one valid JSON object. No markdown code fences. No prose before or after JSON.
Required keys:
- narrative (string)
- recommended_actions (array of strings)
- phase_complete (boolean)
- invoke_hub (boolean)
- hub_operation (string: reconnaissance|port_scan|vulnerability_scan|nuclei_scan|nuclei_templates|ffuf_fuzz|ffuf_vhost|sqlmap_test|metasploit_auxiliary|metasploit_list_modules|execute_attack_step|none)
- hub_parameters (object)
- tools_to_invoke (array of {{tool, plugin, params, rationale?}}, max 3)
- trigger_opsec_assess (boolean, phase 4 only)
- trigger_execute_chain (boolean, phase 5 only; true when aggression>=7 and web_only)
- chain_index (integer)
- artifact_text (string)
- skip_phase (boolean)
- foothold_detected (boolean)
"""

        if template_variant:
            user_prompt += f"\n(JSON repair attempt variant {template_variant} — output valid JSON only.)"

        messages = [
            {
                "role": "system",
                "content": (
                    self._get_pentest_system_prompt()
                    + f"\nYou orchestrate an 8-phase guided assessment at aggression_level={aggression}/10. "
                    "Output a single JSON object only — invalid JSON causes engagement fallback."
                ),
            },
            {"role": "user", "content": user_prompt},
        ]

        default_plan = self._phase_heuristic_plan(
            phase_num, phase_title, target, web_only, aggression, "heuristic_no_api_key"
        )

        if not self.auth_token:
            return ExecutionResult(
                success=True,
                output=default_plan,
                error=None,
                artifacts=[],
                opsec_context={"integration": "jailbreak_ai", "operation": "guided_phase_plan"},
                execution_time=time.time() - start_time,
            )

        hub_timeout = int(context.timeout or boundary_profile.get("ai_timeout_ms", 120000) / 1000 or 120)
        chat_timeout = max(90, min(hub_timeout, 180))

        chat_ctx = ExecutionContext(
            integration_id=context.integration_id,
            engagement_id=context.engagement_id,
            target=target,
            parameters={
                "operation": "chat",
                "messages": messages,
                "temperature": 0.25,
                "max_tokens": 1800,
            },
            timeout=chat_timeout,
            metadata={**(context.metadata or {}), "guided_phase_plan": True},
        )
        chat_result = await self._execute_chat(chat_ctx, start_time)
        execution_time = time.time() - start_time

        if not chat_result.success:
            default_plan = self._phase_heuristic_plan(
                phase_num, phase_title, target, web_only, aggression, "heuristic_api_error"
            )
            default_plan["api_error"] = chat_result.error
            logger.warning(
                "guided_phase_plan API error phase=%s target=%s: %s — using phase heuristic",
                phase_num,
                target,
                chat_result.error,
            )
            return ExecutionResult(
                success=True,
                output=default_plan,
                error=None,
                artifacts=[],
                opsec_context={"integration": "jailbreak_ai", "operation": "guided_phase_plan"},
                execution_time=execution_time,
            )

        content = ""
        if isinstance(chat_result.output, dict):
            content = chat_result.output.get("content") or ""
        parsed = self._parse_guided_phase_plan(
            content, phase_num, phase_title, target, web_only, aggression
        )
        if parsed.get("_parse_failed"):
            repair_ctx = ExecutionContext(
                integration_id=context.integration_id,
                engagement_id=context.engagement_id,
                target=target,
                parameters={
                    "operation": "chat",
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                self._get_pentest_system_prompt()
                                + "\nOutput a single JSON object only — invalid JSON causes fallback."
                            ),
                        },
                        {
                            "role": "user",
                            "content": user_prompt
                            + "\n\nJSON repair: your previous reply was invalid. Output valid JSON only.",
                        },
                    ],
                    "temperature": 0.15,
                    "max_tokens": 1400,
                },
                timeout=chat_timeout,
                metadata={**(context.metadata or {}), "guided_phase_plan_repair": True},
            )
            repair_result = await self._execute_chat(repair_ctx, start_time)
            if repair_result.success and isinstance(repair_result.output, dict):
                repair_content = repair_result.output.get("content") or ""
                repaired = self._parse_guided_phase_plan(
                    repair_content, phase_num, phase_title, target, web_only, aggression
                )
                if not repaired.get("_parse_failed"):
                    parsed = repaired
                    content = repair_content
                    logger.info(
                        "guided_phase_plan JSON repaired phase=%s target=%s",
                        phase_num,
                        target,
                    )
        if parsed.get("_parse_failed"):
            default_plan = self._phase_heuristic_plan(
                phase_num, phase_title, target, web_only, aggression, "heuristic_json_parse"
            )
            default_plan["raw_content"] = content[:1500]
            logger.warning(
                "guided_phase_plan JSON parse failed phase=%s — using phase heuristic",
                phase_num,
            )
            parsed = default_plan
        registry = self._registry_from_tool_catalog(tool_catalog)
        raw_tools = self._parse_tool_calls_field(parsed)
        validated_tools = []
        for call in raw_tools[:5]:
            v = self._validate_structured_tool_call(
                call,
                registry,
                web_only=web_only,
                aggression_level=int(aggression),
            )
            if v.get("valid"):
                validated_tools.append(v["normalized"])
        parsed["tools_to_invoke"] = validated_tools
        if validated_tools and parsed.get("invoke_hub"):
            hub_op = str(parsed.get("hub_operation") or "none").lower()
            hub_aliases = {
                "reconnaissance": "nmap",
                "port_scan": "nmap",
                "vulnerability_scan": "nuclei",
                "nuclei_scan": "nuclei",
                "nuclei_templates": "nuclei",
                "ffuf_fuzz": "ffuf",
                "ffuf_vhost": "ffuf",
                "sqlmap_test": "sqlmap",
            }
            alias_plugin = hub_aliases.get(hub_op)
            if alias_plugin and any(
                str(t.get("plugin") or "").lower() == alias_plugin for t in validated_tools
            ):
                parsed["invoke_hub"] = False
                parsed["hub_operation"] = "none"
                parsed["hub_parameters"] = {}
        ai_meta = self._ai_meta(
            "jailbreak_api",
            start_time,
            chat_result.output.get("usage") if isinstance(chat_result.output, dict) else None,
        )
        parsed.update(ai_meta)
        parsed["raw_content"] = content[:2000]

        return ExecutionResult(
            success=True,
            output=parsed,
            error=None,
            artifacts=[{"type": "guided_phase_plan", "phase": phase_num, "value": parsed}],
            opsec_context={"integration": "jailbreak_ai", "operation": "guided_phase_plan"},
            execution_time=execution_time,
        )

    def _extract_json_object(self, content: str) -> Optional[Dict[str, Any]]:
        """Parse first JSON object from model output; strip fences and trailing commas."""
        import json
        import re

        if not content:
            return None
        text = content.strip()
        fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.I)
        if fence:
            text = fence.group(1).strip()
        start = text.find("{")
        if start < 0:
            return None
        decoder = json.JSONDecoder()
        try:
            data, _end = decoder.raw_decode(text[start:])
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            block = re.search(r"\{[\s\S]*\}", text)
            if not block:
                return None
            raw = block.group(0)
            raw = re.sub(r",\s*}", "}", raw)
            raw = re.sub(r",\s*]", "]", raw)
            try:
                data = json.loads(raw)
                return data if isinstance(data, dict) else None
            except json.JSONDecodeError:
                return None

    def _parse_guided_phase_plan(
        self,
        content: str,
        phase_num: int,
        phase_title: str,
        target: str,
        web_only: bool,
        aggression: int = 5,
    ) -> Dict[str, Any]:
        fallback = self._phase_heuristic_plan(
            phase_num, phase_title, target, web_only, aggression, "heuristic_parse_fallback"
        )
        if not content:
            return {**fallback, "_parse_failed": True}

        data = self._extract_json_object(content)
        if not data:
            return {**fallback, "_parse_failed": True, "artifact_text": content[:4000]}

        trigger_chain = bool(data.get("trigger_execute_chain", False))
        if phase_num == 5 and web_only and aggression >= 7:
            trigger_chain = trigger_chain or True

        return {
            "narrative": str(data.get("narrative") or fallback["narrative"]),
            "recommended_actions": data.get("recommended_actions")
            or fallback["recommended_actions"],
            "phase_complete": bool(data.get("phase_complete", True)),
            "invoke_hub": bool(data.get("invoke_hub", fallback.get("invoke_hub", False))),
            "hub_operation": str(data.get("hub_operation") or fallback.get("hub_operation") or "none"),
            "hub_parameters": data.get("hub_parameters")
            if isinstance(data.get("hub_parameters"), dict)
            else fallback.get("hub_parameters") or {},
            "trigger_opsec_assess": bool(
                data.get("trigger_opsec_assess", phase_num == 4)
            ),
            "trigger_execute_chain": trigger_chain,
            "chain_index": int(data.get("chain_index") or 0),
            "artifact_text": str(
                data.get("artifact_text") or fallback["artifact_text"]
            )[:4000],
            "skip_phase": bool(data.get("skip_phase", False)),
            "foothold_detected": bool(data.get("foothold_detected", False)),
            "tools_to_invoke": self._parse_tool_calls_field(data)[:5],
        }

    def _parse_attack_step_guidance(
        self, content: str, phase: str, tools_hint: str
    ) -> Dict[str, Any]:
        """Parse JSON guidance from model output; fallback to text extraction."""
        import json
        import re

        default_tools = [t.strip() for t in str(tools_hint).split(",") if t.strip()]
        fallback = {
            "guidance": (content or f"Proceed with {phase} using standard tradecraft.")[:2000],
            "tools": default_tools or ["nmap"],
            "attack_vectors": [f"{phase} assessment"],
            "evasion_techniques": ["low-and-slow timing"],
        }
        if not content:
            return {**fallback, "_parse_failed": True}

        data = self._extract_json_object(content)
        if data:
            return {
                "guidance": str(data.get("guidance") or fallback["guidance"]),
                "tools": data.get("tools") or data.get("recommended_tools") or fallback["tools"],
                "attack_vectors": data.get("attack_vectors") or fallback["attack_vectors"],
                "evasion_techniques": data.get("evasion_techniques") or fallback["evasion_techniques"],
                "tool_calls": self._parse_tool_calls_field(data),
            }

        try:
            block = re.search(r"\{[\s\S]*\}", content)
            if block:
                data = json.loads(block.group(0))
                return {
                    "guidance": str(data.get("guidance") or fallback["guidance"]),
                    "tools": data.get("tools") or data.get("recommended_tools") or fallback["tools"],
                    "attack_vectors": data.get("attack_vectors") or fallback["attack_vectors"],
                    "evasion_techniques": data.get("evasion_techniques") or fallback["evasion_techniques"],
                    "tool_calls": self._parse_tool_calls_field(data),
                }
        except (json.JSONDecodeError, TypeError):
            pass

        return {**fallback, "_parse_failed": True}

    async def _execute_council_operation(
        self,
        operation: str,
        parameters: Dict[str, Any],
        start_time: float,
    ) -> ExecutionResult:
        """
        Live Attack Council operations — LLM reasoning grounded in grounding_pack.
        """
        execution_time = time.time() - start_time
        grounding = parameters.get("grounding_pack") or {}
        hits = grounding.get("dataset_hits") or []
        ml_preds = grounding.get("ml_predictions") or []
        agent_memos = parameters.get("agent_memos") or []
        failure_class = parameters.get("failure_class") or "unknown"
        trigger = parameters.get("trigger") or {}
        reasoning_context = parameters.get("reasoning_context") or {}
        tool_catalog_prompt = parameters.get("tool_catalog_prompt") or ""
        tool_catalog = parameters.get("tool_catalog") or grounding.get("tool_catalog")

        def _hit_summary(h: Dict[str, Any]) -> Dict[str, Any]:
            rec = h.get("record") or h
            return {
                "id": rec.get("id"),
                "title": rec.get("title"),
                "mitre_technique": rec.get("mitre_technique"),
                "tools_used": rec.get("tools_used"),
                "score": h.get("score"),
            }

        hits_summary = [_hit_summary(h) for h in hits[:8]]
        ml_top = ml_preds[0] if ml_preds else {}
        agent = operation.replace("council_", "")

        fallback = self._council_fallback_memo(
            operation, hits_summary, ml_top, agent_memos, parameters
        )

        if not self.auth_token:
            return ExecutionResult(
                success=True,
                output=fallback,
                error=None,
                artifacts=[{"type": "council_memo", "operation": operation, "source": "heuristic"}],
                opsec_context={"integration": "jailbreak_ai", "operation": operation},
                execution_time=time.time() - start_time,
            )

        is_conductor = operation in ("council_conductor", "replan_attack_chain")

        schema_hints = {
            "council_tactical": '{"agent":"tactical","assessment":"...","suggested_tool":"...","evidence_ids":[1,2]}',
            "council_opsec": '{"agent":"opsec","veto":false,"risk_score":0.5,"risk_note":"...","timing_advice":"..."}',
            "council_architect": '{"agent":"architect","missing_phases":[],"chain_patch_hint":"...","phase_skip_authorized":false}',
            "council_exploit": '{"agent":"exploit","new_methods":[],"tool_pivot":"...","alternate_chain_index":1}',
            "council_conductor": CONDUCTOR_LIVE_DIRECTIVE_SCHEMA_HINT,
            "replan_attack_chain": CONDUCTOR_LIVE_DIRECTIVE_SCHEMA_HINT,
        }

        aggression_level = (
            parameters.get("aggression_level")
            or grounding.get("aggression_level")
            or 5
        )
        boundary_profile = (
            parameters.get("boundary_profile")
            or grounding.get("boundary_profile")
            or {}
        )

        if is_conductor:
            current_phase = trigger.get("phase") or reasoning_context.get("current_phase") or "unknown"
            user_prompt = f"""Live Attack Council — Offensive Conductor ({operation})
Engagement objective: drive attack to successful completion within aggression_level={aggression_level}/10.

Trigger: {trigger.get('type', 'unknown')} step={trigger.get('step_number')} phase={current_phase}
Failure class: {failure_class}
Suggested action hint: {parameters.get('suggested_action', 'none')}

Boundary profile: {json.dumps(boundary_profile)[:800]}

Dataset hits (heavily favor phase/category matches; boost e-commerce, retail, Shopify, Cloudflare, Australia tags):
{json.dumps(hits_summary, indent=2)[:4000]}

ML predictions: {json.dumps(ml_preds[:3])[:800]}

Prior agent memos (merge into directive; OPSEC veto only if multiple high-quality dataset records support safer path):
{json.dumps(agent_memos[-6:])[:3000]}

Reasoning context: {json.dumps(reasoning_context)[:1500]}

External tool catalog (suggested_tool / tool_calls must reference these plugins):
{tool_catalog_prompt[:4000] if tool_catalog_prompt else json.dumps(tool_catalog)[:2000] if tool_catalog else "(none)"}

Replan candidates: {len(grounding.get('replan_candidates') or [])} chains available.

Synthesize a LiveDirective JSON object. Requirements:
- rationale_steps MUST include at least one step with step="trade_offs" and explicit Speed vs Stealth vs Reliability analysis in detail.
- rationale_steps may include trade_off objects with speed, stealth, reliability scores (0.0–1.0).
- Cite dataset_record_ids from dataset hits where applicable.
- Set opsec_veto only when dataset evidence supports the safer path over aggressive options.

Respond with strict JSON only (no markdown). Schema:
{schema_hints[operation]}
"""
        else:
            user_prompt = f"""Live Attack Council — role: {agent}
Trigger: {trigger.get('type', 'unknown')} step={trigger.get('step_number')}
Failure class: {failure_class}
Suggested action hint: {parameters.get('suggested_action', 'none')}

Dataset hits (cite evidence_ids from these):
{json.dumps(hits_summary, indent=2)[:4000]}

ML predictions: {json.dumps(ml_preds[:3])[:800]}

Prior agent memos: {json.dumps(agent_memos[-4:])[:2000]}

Reasoning context: {json.dumps(reasoning_context)[:1500]}

External tool catalog (suggested_tool / tool_calls must reference these plugins):
{tool_catalog_prompt[:4000] if tool_catalog_prompt else json.dumps(tool_catalog)[:2000] if tool_catalog else "(none)"}

Replan candidates: {len(grounding.get('replan_candidates') or [])} chains available.

Respond with strict JSON only (no markdown). Schema example:
{schema_hints.get(operation, schema_hints['council_tactical'])}
"""

        if is_conductor:
            system_content = (
                OFFENSIVE_CONDUCTOR_SYSTEM_PROMPT
                + "\n\nOutput strict JSON only (no markdown). Emit a LiveDirective with rationale_steps including trade-off analysis."
            )
        else:
            system_content = (
                self._get_pentest_system_prompt()
                + "\nYou are a Live Attack Council agent. Ground all reasoning in provided dataset hits. Output strict JSON."
            )

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_prompt},
        ]

        chat_ctx = ExecutionContext(
            integration_id="jailbreak_ai",
            engagement_id=parameters.get("engagement_id") or "live-council",
            target=parameters.get("target") or "unknown",
            parameters={
                "operation": "chat",
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": 1200,
            },
            timeout=90,
            metadata={"council_operation": operation},
        )
        chat_result = await self._execute_chat(chat_ctx, start_time)

        if not chat_result.success:
            fallback["source"] = "heuristic_api_error"
            return ExecutionResult(
                success=True,
                output=fallback,
                error=None,
                artifacts=[{"type": "council_memo", "operation": operation}],
                opsec_context={"integration": "jailbreak_ai", "operation": operation},
                execution_time=time.time() - start_time,
            )

        content = ""
        if isinstance(chat_result.output, dict):
            content = chat_result.output.get("content") or ""
        parsed = self._parse_council_json(content, fallback, operation)

        return ExecutionResult(
            success=True,
            output=parsed,
            error=None,
            artifacts=[{"type": "council_memo", "operation": operation, "source": "jailbreak_api"}],
            opsec_context={"integration": "jailbreak_ai", "operation": operation},
            execution_time=time.time() - start_time,
        )

    def _council_fallback_memo(
        self,
        operation: str,
        hits_summary: List[Dict[str, Any]],
        ml_top: Dict[str, Any],
        agent_memos: List[Dict[str, Any]],
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        top_hit = hits_summary[0] if hits_summary else {}
        agent = operation.replace("council_", "")

        if operation == "council_tactical":
            return {
                "agent": "tactical",
                "assessment": f"Top dataset match: {top_hit.get('title', 'none')}",
                "suggested_tool": (top_hit.get("tools_used") or "").split(",")[0].strip() or None,
                "evidence_ids": [h.get("id") for h in hits_summary if h.get("id") is not None],
                "dataset_hits": hits_summary[:5],
                "source": "heuristic",
            }
        if operation == "council_opsec":
            return {
                "agent": "opsec",
                "veto": False,
                "risk_score": 0.4,
                "risk_note": "Standard execution risk",
                "timing_advice": "Maintain tempo",
                "source": "heuristic",
            }
        if operation == "council_architect":
            return {
                "agent": "architect",
                "missing_phases": [],
                "chain_patch_hint": f"ML: {ml_top.get('label', 'n/a')}",
                "phase_skip_authorized": False,
                "source": "heuristic",
            }
        if operation == "council_exploit":
            return {
                "agent": "exploit",
                "new_methods": hits_summary[:3],
                "tool_pivot": None,
                "alternate_chain_index": 1 if len(hits_summary) > 1 else None,
                "source": "heuristic",
            }
        action = parameters.get("suggested_action") or "reinitiate_chain"
        return {
            "agent": "conductor",
            "directive": {
                "action": action,
                "rationale": f"Council merge from {len(agent_memos)} memos; {len(hits_summary)} hits",
                "rationale_steps": [
                    {
                        "step": "ground",
                        "detail": f"Top hit: {top_hit.get('title', 'none')}; {len(hits_summary)} dataset matches",
                    },
                    {
                        "step": "trade_offs",
                        "detail": (
                            "Speed vs Stealth vs Reliability (heuristic): favor speed and reliability "
                            "when aggression is high; defer to stealth only if OPSEC memos veto."
                        ),
                        "trade_off": {"speed": 0.7, "stealth": 0.3, "reliability": 0.6},
                    },
                    {"step": "heuristic", "detail": "API unavailable — fallback directive"},
                ],
                "dataset_record_ids": [h.get("id") for h in hits_summary if h.get("id") is not None],
                "confidence": float(ml_top.get("confidence", 0.5) or 0.5),
                "opsec_veto": any(m.get("veto") for m in agent_memos if isinstance(m, dict)),
            },
            "source": "heuristic",
        }

    def _parse_council_json(
        self,
        content: str,
        fallback: Dict[str, Any],
        operation: str,
    ) -> Dict[str, Any]:
        import json
        import re

        if not content:
            return fallback
        try:
            match = re.search(r"\{[\s\S]*\}", content)
            data = json.loads(match.group(0) if match else content)
            if operation in ("council_conductor", "replan_attack_chain"):
                if "directive" in data:
                    return {"agent": "conductor", **data, "source": "jailbreak_api"}
                return {"agent": "conductor", "directive": data, "source": "jailbreak_api"}
            data.setdefault("agent", operation.replace("council_", ""))
            data["source"] = "jailbreak_api"
            return data
        except Exception:
            return fallback
