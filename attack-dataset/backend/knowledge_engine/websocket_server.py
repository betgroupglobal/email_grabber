"""
WebSocket server for real-time dashboard updates
Broadcasts attack events, agent status, and system updates to connected clients
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Set, Dict, Any
import websockets
from websockets.server import WebSocketServerProtocol

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Store connected clients
connected_clients: Set[WebSocketServerProtocol] = set()

# Store subscriptions for each client
client_subscriptions: Dict[WebSocketServerProtocol, Set[str]] = {}

class WebSocketMessage:
    """Standard WebSocket message format"""
    def __init__(self, message_type: str, data: Any):
        self.type = message_type
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.data = data
    
    def to_json(self) -> str:
        return json.dumps({
            "type": self.type,
            "timestamp": self.timestamp,
            "data": self.data
        })

async def broadcast_message(message_type: str, data: Any):
    """Broadcast a message to all connected clients"""
    message = WebSocketMessage(message_type, data)
    message_json = message.to_json()
    
    # Send to all connected clients
    disconnected = set()
    for client in connected_clients:
        try:
            await client.send(message_json)
        except websockets.exceptions.ConnectionClosed:
            disconnected.add(client)
        except Exception as e:
            logger.error(f"Error sending message to client: {e}")
            disconnected.add(client)
    
    # Remove disconnected clients
    for client in disconnected:
        connected_clients.remove(client)
        if client in client_subscriptions:
            del client_subscriptions[client]

async def send_to_subscribers(message_type: str, data: Any):
    """Send message only to clients subscribed to the message type"""
    message = WebSocketMessage(message_type, data)
    message_json = message.to_json()
    
    disconnected = set()
    for client, subscriptions in client_subscriptions.items():
        if message_type in subscriptions or "*" in subscriptions:
            try:
                await client.send(message_json)
            except websockets.exceptions.ConnectionClosed:
                disconnected.add(client)
            except Exception as e:
                logger.error(f"Error sending message to client: {e}")
                disconnected.add(client)
    
    # Remove disconnected clients
    for client in disconnected:
        connected_clients.remove(client)
        if client in client_subscriptions:
            del client_subscriptions[client]

async def handle_client(websocket: WebSocketServerProtocol, path: str):
    """Handle individual client connections"""
    # Register client
    connected_clients.add(websocket)
    client_subscriptions[websocket] = set()
    client_address = websocket.remote_address
    
    logger.info(f"Client connected: {client_address}")
    
    try:
        # Send initial connection confirmation
        await websocket.send(WebSocketMessage("connected", {
            "message": "WebSocket connection established",
            "server_time": datetime.now(timezone.utc).isoformat()
        }).to_json())
        
        # Handle incoming messages
        async for message in websocket:
            try:
                data = json.loads(message)
                
                # Handle subscription requests
                if data.get("type") == "subscribe":
                    channels = data.get("channels", [])
                    client_subscriptions[websocket].update(channels)
                    logger.info(f"Client {client_address} subscribed to: {channels}")
                    
                    # Send current state for subscribed channels
                    if "agents" in channels:
                        await send_agent_status(websocket)
                    if "system" in channels:
                        await send_system_status(websocket)
                
                # Handle other message types
                elif data.get("type") == "ping":
                    await websocket.send(WebSocketMessage("pong", {}).to_json())
                    
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON received from {client_address}")
            except Exception as e:
                logger.error(f"Error handling message from {client_address}: {e}")
    
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"Client disconnected: {client_address}")
    except Exception as e:
        logger.error(f"Error with client {client_address}: {e}")
    finally:
        # Cleanup
        connected_clients.discard(websocket)
        if websocket in client_subscriptions:
            del client_subscriptions[websocket]

async def send_agent_status(websocket: WebSocketServerProtocol = None):
    """Send current agent status"""
    try:
        # Provide mock agent data for stable WebSocket operation
        agent_status = [
            {
                "id": "recon-1",
                "type": "RECON",
                "name": "Recon Agent Alpha",
                "status": "idle",
                "capabilities": [
                    {"id": "port_scan", "name": "Port Scanning", "description": "Nmap-based port discovery", "successRate": 0.95, "avgExecutionTime": 120},
                    {"id": "service_enum", "name": "Service Enumeration", "description": "Detailed service fingerprinting", "successRate": 0.85, "avgExecutionTime": 180},
                ],
                "performance": {
                    "totalTasks": 3,
                    "successfulTasks": 3,
                    "avgDuration": 126,
                    "lastActive": datetime.now(timezone.utc).isoformat()
                }
            },
            {
                "id": "exploit-1",
                "type": "EXPLOIT", 
                "name": "Exploit Agent Beta",
                "status": "idle",
                "capabilities": [
                    {"id": "remote_exploit", "name": "Remote Exploitation", "description": "Exploit remote vulnerabilities", "successRate": 0.60, "avgExecutionTime": 300},
                ],
                "performance": {
                    "totalTasks": 2,
                    "successfulTasks": 1,
                    "avgDuration": 317,
                    "lastActive": datetime.now(timezone.utc).isoformat()
                }
            }
        ]
        
        message = WebSocketMessage("agent_status", {
            "agents": agent_status,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        if websocket:
            await websocket.send(message.to_json())
        else:
            await send_to_subscribers("agent_status", agent_status)
            
    except Exception as e:
        logger.error(f"Error sending agent status: {e}")

async def send_system_status(websocket: WebSocketServerProtocol = None):
    """Send system status"""
    try:
        message = WebSocketMessage("system_status", {
            "stats": {
                "totalAttacks": 0,
                "activeSessions": 0,
                "detectedThreats": 0,
                "blockedAttacks": 0,
                "avgResponseTime": 0
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        if websocket:
            await websocket.send(message.to_json())
        else:
            await send_to_subscribers("system_status", message.data)
            
    except Exception as e:
        logger.error(f"Error sending system status: {e}")

async def simulate_attack_events():
    """Simulate attack events for testing (replace with real event source)"""
    while True:
        await asyncio.sleep(5)  # Send event every 5 seconds
        
        current_time = datetime.now(timezone.utc)
        
        # Simulate attack event
        event = {
            "event": {
                "id": f"event-{current_time.timestamp()}",
                "timestamp": current_time.isoformat(),
                "type": ["scan", "exploit", "persistence", "exfiltration", "detection"][
                    int(current_time.timestamp()) % 5
                ],
                "severity": ["low", "medium", "high", "critical"][
                    int(current_time.timestamp()) % 4
                ],
                "source": "Security Monitor",
                "target": "192.168.1.100",
                "description": "Simulated attack event for testing",
                "details": {
                    "port": 443,
                    "protocol": "TCP",
                    "payloadSize": 1024
                },
                "responseTime": 150
            }
        }
        
        await send_to_subscribers("attack_event", event)

async def start_websocket_server(host: str = "localhost", port: int = 3003):
    """Start the WebSocket server"""
    logger.info(f"Starting WebSocket server on {host}:{port}")
    
    # Start the server
    server = await websockets.serve(handle_client, host, port)
    
    # Start background task to simulate events (replace with real event source)
    asyncio.create_task(simulate_attack_events())
    
    logger.info(f"WebSocket server running on ws://{host}:{port}")
    await server.wait_closed()

def run_websocket_server():
    """Run the WebSocket server (blocking call)"""
    asyncio.run(start_websocket_server())

if __name__ == "__main__":
    run_websocket_server()