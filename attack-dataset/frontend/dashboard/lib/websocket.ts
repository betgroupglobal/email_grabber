/**
 * WebSocket connection utility for real-time dashboard updates
 * Handles connection management, reconnection, and message processing
 */

export type WebSocketMessage = {
  type: "attack_event" | "agent_status" | "chain_update" | "system_status" | "error" | "connection";
  timestamp: string;
  data: any;
};

export type WebSocketCallback = (message: WebSocketMessage) => void;

export class DashboardWebSocket {
  private ws: WebSocket | null = null;
  private url: string;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private baseReconnectDelay = 2000;
  private callbacks: Map<string, Set<WebSocketCallback>> = new Map();
  private isConnecting = false;
  private isManualClose = false;
  private lastErrorTime = 0;
  private errorDebounceMs = 1000;

  constructor(url: string = "ws://localhost:3001") {
    this.url = url;
  }

  private getReconnectDelay(): number {
    // Exponential backoff: 2s, 4s, 8s, 16s, 32s
    return this.baseReconnectDelay * Math.pow(2, this.reconnectAttempts);
  }

  private shouldThrottleError(): boolean {
    const now = Date.now();
    if (now - this.lastErrorTime < this.errorDebounceMs) {
      return true;
    }
    this.lastErrorTime = now;
    return false;
  }

  connect(): void {
    if (this.isConnecting || (this.ws && this.ws.readyState === WebSocket.OPEN)) {
      return;
    }

    this.isConnecting = true;
    this.isManualClose = false;

    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        this.isConnecting = false;
        this.reconnectAttempts = 0;
        this.notifyCallbacks({
          type: "connection",
          timestamp: new Date().toISOString(),
          data: { state: "connected", url: this.url }
        });

        // Send initial subscription message
        this.send({
          type: "subscribe",
          channels: ["attacks", "agents", "chains", "system"]
        });
      };

      this.ws.onmessage = (event: MessageEvent) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          this.handleMessage(message);
        } catch (error) {
          // Silently ignore unparsable messages — the dashboard should not crash on bad data
          if (!this.shouldThrottleError()) {
            console.warn("WebSocket: failed to parse message", error);
          }
        }
      };

      this.ws.onerror = () => {
        // WebSocket error events carry no useful payload — onclose handles the aftermath.
        // Avoid logging here to prevent console noise. Connection errors are surfaced via
        // the "connection" callback if max reconnection is reached.
        this.isConnecting = false;
      };

      this.ws.onclose = (event: CloseEvent) => {
        this.isConnecting = false;

        if (this.isManualClose) {
          this.notifyCallbacks({
            type: "connection",
            timestamp: new Date().toISOString(),
            data: { state: "disconnected", code: event.code }
          });
          return;
        }

        if (this.reconnectAttempts < this.maxReconnectAttempts) {
          this.reconnectAttempts++;
          const delay = this.getReconnectDelay();
          setTimeout(() => this.connect(), delay);
        } else {
          // Only surface the final failure to subscribers
          this.notifyCallbacks({
            type: "connection",
            timestamp: new Date().toISOString(),
            data: {
              state: "failed",
              message: `Unable to connect to WebSocket at ${this.url} after ${this.maxReconnectAttempts} attempts`,
              code: event.code
            }
          });
        }
      };
    } catch (error) {
      this.isConnecting = false;
      if (!this.shouldThrottleError()) {
        console.warn("WebSocket: failed to create connection", error);
      }
    }
  }

  disconnect(): void {
    this.isManualClose = true;
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  send(data: any): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    } else {
      console.warn("WebSocket is not connected, cannot send message");
    }
  }

  subscribe(type: string, callback: WebSocketCallback): () => void {
    if (!this.callbacks.has(type)) {
      this.callbacks.set(type, new Set());
    }
    this.callbacks.get(type)!.add(callback);

    // Return unsubscribe function
    return () => {
      this.callbacks.get(type)?.delete(callback);
      if (this.callbacks.get(type)?.size === 0) {
        this.callbacks.delete(type);
      }
    };
  }

  private handleMessage(message: WebSocketMessage): void {
    // Notify all callbacks for this message type
    const callbacks = this.callbacks.get(message.type);
    if (callbacks) {
      callbacks.forEach(callback => callback(message));
    }

    // Also notify general callbacks
    const generalCallbacks = this.callbacks.get("*");
    if (generalCallbacks) {
      generalCallbacks.forEach(callback => callback(message));
    }
  }

  private notifyCallbacks(message: WebSocketMessage): void {
    const callbacks = this.callbacks.get(message.type);
    if (callbacks) {
      callbacks.forEach(callback => callback(message));
    }
  }

  getConnectionState(): "connecting" | "open" | "closing" | "closed" {
    if (!this.ws) return "closed";
    switch (this.ws.readyState) {
      case WebSocket.CONNECTING:
        return "connecting";
      case WebSocket.OPEN:
        return "open";
      case WebSocket.CLOSING:
        return "closing";
      case WebSocket.CLOSED:
        return "closed";
      default:
        return "closed";
    }
  }

  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }
}

// Singleton instance
let wsInstance: DashboardWebSocket | null = null;

export function getWebSocket(url?: string): DashboardWebSocket {
  if (!wsInstance) {
    wsInstance = new DashboardWebSocket(url);
  }
  return wsInstance;
}

export function connectWebSocket(url?: string): void {
  const ws = getWebSocket(url);
  ws.connect();
}

export function disconnectWebSocket(): void {
  if (wsInstance) {
    wsInstance.disconnect();
  }
}