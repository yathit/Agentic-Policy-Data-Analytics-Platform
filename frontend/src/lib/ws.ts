import ReconnectingWebSocket from 'reconnecting-websocket';
import type { AgentEvent } from './types';
import { getWebSocketUrl } from './api';

export type WebSocketStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

export interface WebSocketClientOptions {
  onEvent: (event: AgentEvent) => void;
  onSnapshot?: (snapshot: { run: unknown; events: AgentEvent[] }) => void;
  onStatus?: (status: { status: string; finished_at?: string }) => void;
  onHeartbeat?: (ts: string) => void;
  onStatusChange?: (status: WebSocketStatus) => void;
  onError?: (error: Error) => void;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
}

export class WebSocketClient {
  private ws: ReconnectingWebSocket | null = null;
  private runId: string;
  private options: WebSocketClientOptions;

  constructor(runId: string, options: WebSocketClientOptions) {
    this.runId = runId;
    this.options = {
      reconnectInterval: 3000,
      maxReconnectAttempts: 5,
      ...options,
    };
  }

  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      return;
    }

    this.options.onStatusChange?.('connecting');

    const url = getWebSocketUrl(this.runId);
    const minDelay = this.options.reconnectInterval ?? 3000;
    const maxRetries = this.options.maxReconnectAttempts ?? 5;
    this.ws = new ReconnectingWebSocket(url, [], {
      minReconnectionDelay: minDelay,
      maxReconnectionDelay: minDelay,
      maxRetries,
    });

    this.ws.onopen = () => {
      this.options.onStatusChange?.('connected');
    };

    this.ws.onmessage = (messageEvent) => {
      try {
        const message = JSON.parse(messageEvent.data) as {
          type?: string;
          event?: AgentEvent;
          run?: unknown;
          events?: AgentEvent[];
          status?: string;
          finished_at?: string;
          ts?: string;
        };

        if (message.type === 'event' && message.event) {
          this.options.onEvent(message.event);
          return;
        }

        if (message.type === 'snapshot' && message.run) {
          this.options.onSnapshot?.({
            run: message.run,
            events: message.events ?? [],
          });
          return;
        }

        if (message.type === 'status') {
          this.options.onStatus?.({
            status: message.status ?? 'unknown',
            finished_at: message.finished_at,
          });
          return;
        }

        if (message.type === 'heartbeat' && message.ts) {
          this.options.onHeartbeat?.(message.ts);
          return;
        }

        // Fallback for legacy messages that are raw AgentEvent
        if (message && (message as AgentEvent).agent) {
          this.options.onEvent(message as AgentEvent);
        }
      } catch (err) {
        console.error('Failed to parse WebSocket message:', err);
      }
    };

    this.ws.onerror = () => {
      const error = new Error('WebSocket connection error');
      this.options.onError?.(error);
      this.options.onStatusChange?.('error');
    };

    this.ws.onclose = () => {
      this.options.onStatusChange?.('disconnected');
    };
  }

  disconnect(): void {
    if (this.ws) {
      this.ws.close(1000, 'manual disconnect');
      this.ws = null;
    }
  }

  getStatus(): WebSocketStatus {
    if (!this.ws) return 'disconnected';

    switch (this.ws.readyState) {
      case WebSocket.CONNECTING:
        return 'connecting';
      case WebSocket.OPEN:
        return 'connected';
      default:
        return 'disconnected';
    }
  }
}

// Hook-like function for creating a managed WebSocket connection
export function createEventStream(
  runId: string,
  onEvent: (event: AgentEvent) => void,
  options?: Partial<Omit<WebSocketClientOptions, 'onEvent'>>
): WebSocketClient {
  return new WebSocketClient(runId, { onEvent, ...options });
}
