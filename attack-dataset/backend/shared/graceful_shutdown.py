"""
Graceful shutdown handling for OpsecAI services.

Provides consistent shutdown behavior across all services with proper
resource cleanup and connection termination.
"""
from __future__ import annotations

import signal
import asyncio
import logging
from typing import Callable, Optional, List, Any
from contextlib import contextmanager
from datetime import datetime
import time


# ── Shutdown Manager ─────────────────────────────────────────────────────────

class ShutdownManager:
    """Manages graceful shutdown for services."""
    
    def __init__(self, service_name: str, timeout: float = 30.0):
        self.service_name = service_name
        self.timeout = timeout
        self.shutdown_requested = False
        self.shutdown_start_time: Optional[float] = None
        self.cleanup_handlers: List[Callable] = []
        self.logger = logging.getLogger(f"shutdown.{service_name}")
    
    def register_cleanup(self, handler: Callable):
        """Register a cleanup handler to be called during shutdown."""
        self.cleanup_handlers.append(handler)
    
    def request_shutdown(self, signum=None, frame=None):
        """Request graceful shutdown."""
        if self.shutdown_requested:
            self.logger.warning("Shutdown already requested, forcing exit...")
            return  # Force exit if already requested
        
        self.shutdown_requested = True
        self.shutdown_start_time = time.time()
        
        signal_name = signal.Signals(signum).name if signum else "unknown"
        self.logger.info(f"Shutdown requested via {signal_name}")
    
    async def graceful_shutdown(self):
        """Perform graceful shutdown with timeout."""
        if not self.shutdown_requested:
            return
        
        self.logger.info(f"Starting graceful shutdown for {self.service_name}...")
        
        # Run cleanup handlers
        for handler in self.cleanup_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler()
                else:
                    handler()
            except Exception as e:
                self.logger.error(f"Error in cleanup handler: {e}")
        
        elapsed = time.time() - self.shutdown_start_time
        self.logger.info(f"Graceful shutdown completed in {elapsed:.2f}s")
    
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        signal.signal(signal.SIGINT, self.request_shutdown)
        signal.signal(signal.SIGTERM, self.request_shutdown)
        
        self.logger.info("Signal handlers registered for SIGINT and SIGTERM")
    
    def is_shutdown_requested(self) -> bool:
        """Check if shutdown has been requested."""
        return self.shutdown_requested
    
    def get_remaining_time(self) -> float:
        """Get remaining time before timeout."""
        if not self.shutdown_start_time:
            return self.timeout
        
        elapsed = time.time() - self.shutdown_start_time
        return max(0.0, self.timeout - elapsed)


# ── FastAPI Integration ───────────────────────────────────────────────────────

def setup_graceful_shutdown_fastapi(
    app,
    service_name: str,
    timeout: float = 30.0,
    on_shutdown: Optional[Callable] = None
):
    """
    Setup graceful shutdown for FastAPI applications.
    
    Args:
        app: FastAPI application instance
        service_name: Name of the service
        timeout: Shutdown timeout in seconds
        on_shutdown: Optional callback to call during shutdown
    """
    shutdown_manager = ShutdownManager(service_name, timeout)
    
    # Register custom shutdown handler
    if on_shutdown:
        shutdown_manager.register_cleanup(on_shutdown)
    
    # Setup signal handlers
    shutdown_manager.setup_signal_handlers()
    
    # Add shutdown handler to lifespan
    original_lifespan = app.router.lifespan_context
    
    async def extended_lifespan(app):
        async with original_lifespan(app) as state:
            # Store shutdown manager in app state
            app.state.shutdown_manager = shutdown_manager
            yield state
            
            # Perform shutdown
            if shutdown_manager.is_shutdown_requested():
                await shutdown_manager.graceful_shutdown()
    
    app.router.lifespan_context = extended_lifespan
    
    return shutdown_manager


# ── Go Integration Example (Documentation) ───────────────────────────────────

def create_go_shutdown_example():
    """
    Example for implementing graceful shutdown in Go.
    
    ```go
    package main
    
    import (
        "context"
        "log"
        "os"
        "os/signal"
        "syscall"
        "time"
    )
    
    type ShutdownManager struct {
        service_name   string
        timeout       time.Duration
        shutdown_chan  chan struct{}
        cleanup_funcs  []func() error
    }
    
    func NewShutdownManager(service_name string, timeout time.Duration) *ShutdownManager {
        return &ShutdownManager{
            service_name:  service_name,
            timeout:      timeout,
            shutdown_chan: make(chan struct{}),
        }
    }
    
    func (sm *ShutdownManager) RegisterCleanup(fn func() error) {
        sm.cleanup_funcs = append(sm.cleanup_funcs, fn)
    }
    
    func (sm *ShutdownManager) Start() {
        sigChan := make(chan os.Signal, 1)
        signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
        
        go func() {
            sig := <-sigChan
            log.Printf("[%s] Shutdown requested via %v", sm.service_name, sig)
            close(sm.shutdown_chan)
            
            ctx, cancel := context.WithTimeout(context.Background(), sm.timeout)
            defer cancel()
            
            sm.gracefulShutdown(ctx)
        }()
    }
    
    func (sm *ShutdownManager) gracefulShutdown(ctx context.Context) {
        log.Printf("[%s] Starting graceful shutdown...", sm.service_name)
        start := time.Now()
        
        for _, fn := range sm.cleanup_funcs {
            if err := fn(); err != nil {
                log.Printf("[%s] Error in cleanup handler: %v", sm.service_name, err)
            }
        }
        
        elapsed := time.Since(start)
        log.Printf("[%s] Graceful shutdown completed in %v", sm.service_name, elapsed)
    }
    
    func (sm *ShutdownManager) ShutdownRequested() <-chan struct{} {
        return sm.shutdown_chan
    }
    
    func main() {
        shutdownMgr := NewShutdownManager("service-name", 30*time.Second)
        shutdownMgr.Start()
        
        // Your service logic here
        <-shutdownMgr.ShutdownRequested()
        
        log.Println("Service shutting down")
    }
    ```
    """
    return create_go_shutdown_example.__doc__


# ── Common Cleanup Handlers ─────────────────────────────────────────────────────

async def close_database_connection(conn):
    """Close database connection gracefully."""
    try:
        if hasattr(conn, 'close'):
            conn.close()
            logging.info("Database connection closed")
    except Exception as e:
        logging.error(f"Error closing database connection: {e}")


async def close_http_client(client):
    """Close HTTP client gracefully."""
    try:
        if hasattr(client, 'close'):
            await client.close()
            logging.info("HTTP client closed")
    except Exception as e:
        logging.error(f"Error closing HTTP client: {e}")


async def close_websocket_connections(websockets):
    """Close WebSocket connections gracefully."""
    try:
        for ws in websockets:
            if hasattr(ws, 'close'):
                await ws.close()
        logging.info(f"Closed {len(websockets)} WebSocket connections")
    except Exception as e:
        logging.error(f"Error closing WebSocket connections: {e}")


async def flush_logs(logger):
    """Flush any buffered logs."""
    try:
        for handler in logger.handlers:
            handler.flush()
        logging.info("Logs flushed")
    except Exception as e:
        logging.error(f"Error flushing logs: {e}")


# ── Context Manager for Temporary Shutdown Testing ─────────────────────────────

@contextmanager
def temporary_shutdown_signal(service_name: str):
    """
    Context manager for testing shutdown signals without actual signals.
    
    Usage:
        with temporary_shutdown_signal("test-service"):
            # Simulate shutdown
            pass
    """
    manager = ShutdownManager(service_name, timeout=5.0)
    manager.request_shutdown()
    
    yield manager
    
    # Reset for testing
    manager.shutdown_requested = False


# ── Shutdown State Tracking ───────────────────────────────────────────────────

class ShutdownState:
    """Track shutdown state across a service."""
    
    def __init__(self):
        self.shutdown_requested = False
        self.shutdown_start_time: Optional[float] = None
        self.shutdown_complete = False
        self.inflight_requests = 0
        self.connections_open = 0
    
    def request_shutdown(self):
        """Request shutdown."""
        if not self.shutdown_requested:
            self.shutdown_requested = True
            self.shutdown_start_time = time.time()
    
    def complete_shutdown(self):
        """Mark shutdown as complete."""
        self.shutdown_complete = True
    
    def add_inflight_request(self):
        """Track an inflight request."""
        self.inflight_requests += 1
    
    def remove_inflight_request(self):
        """Track completion of an inflight request."""
        self.inflight_requests = max(0, self.inflight_requests - 1)
    
    def add_connection(self):
        """Track an open connection."""
        self.connections_open += 1
    
    def remove_connection(self):
        """Track closure of a connection."""
        self.connections_open = max(0, self.connections_open - 1)
    
    def can_shutdown_now(self) -> bool:
        """Check if service can safely shutdown now."""
        return (
            self.inflight_requests == 0 and
            self.connections_open == 0
        )
    
    def get_status(self) -> Dict[str, Any]:
        """Get current shutdown status."""
        return {
            "shutdown_requested": self.shutdown_requested,
            "shutdown_complete": self.shutdown_complete,
            "inflight_requests": self.inflight_requests,
            "connections_open": self.connections_open,
            "can_shutdown_now": self.can_shutdown_now(),
            "elapsed_seconds": (time.time() - self.shutdown_start_time) if self.shutdown_start_time else 0
        }