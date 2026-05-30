"""
Lifecycle manager for plugin execution with hooks.
"""

import logging
import time
from typing import Dict, Any

from .base import BasePlugin, ExecutionContext, ExecutionResult


logger = logging.getLogger(__name__)


class LifecycleManager:
    """Manages plugin lifecycle and hook execution."""
    
    def __init__(self):
        pass
    
    async def execute_with_hooks(
        self,
        plugin: BasePlugin,
        context: ExecutionContext
    ) -> ExecutionResult:
        """Execute plugin with lifecycle hooks."""
        start_time = time.time()
        
        try:
            # Before execution hook
            context = await plugin.before_execution(context)
            
            # Execute the plugin
            result = await plugin.execute(context)
            
            # After execution hook
            result = await plugin.after_execution(result, context)
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            
            # On error hook
            await plugin.on_error(e, context)
            
            # Return error result
            return ExecutionResult(
                success=False,
                output=None,
                error=str(e),
                artifacts=[],
                opsec_context=None,
                execution_time=execution_time
            )