/**
 * services/websocket.ts
 * =====================
 * STEP 5 — WebSocket Real-Time Communication & Live Notifications
 *
 * Resilient, singleton WebSocket client with:
 * - Handshake using JWT access token: /api/v1/ws?token=<access_token>
 * - Exponential backoff reconnection with jitter (1s, 2s, 4s, 8s, 16s, max 30s)
 * - Automatic heartbeat ping/pong every 25 seconds
 * - Event deduplication cache (prevents processing duplicate event_ids)
 * - Clean subscriber registry with unsubscription callbacks
 * - Graceful fallback when WebSockets are unreachable
 */

export type ConnectionStatus = 'connected' | 'connecting' | 'disconnected' | 'reconnecting';

export interface WSEvent<T = any> {
  event: string;
  event_id: string;
  timestamp: string;
  data: T;
}

type EventCallback = (event: WSEvent) => void;
type StatusCallback = (status: ConnectionStatus) => void;

class WebSocketService {
  private socket: WebSocket | null = null;
  private status: ConnectionStatus = 'disconnected';
  private reconnectAttempt = 0;
  private reconnectTimeoutId: any = null;
  private pingIntervalId: any = null;
  private intentionalClose = false;

  // Deduplication cache (stores up to 250 recent event IDs)
  private processedEventIds = new Set<string>();

  // Event & Status Subscriptions
  private eventListeners = new Map<string, Set<EventCallback>>();
  private statusListeners = new Set<StatusCallback>();

  // Max backoff in milliseconds (30 seconds)
  private readonly MAX_BACKOFF_MS = 30000;
  private readonly BASE_DELAY_MS = 1000;

  /**
   * Resolves the WebSocket URL based on current host and protocol.
   */
  private getWsUrl(token: string): string {
    const isHttps = window.location.protocol === 'https:';
    const wsProto = isHttps ? 'wss:' : 'ws:';
    // VITE_WS_HOST allows explicit backend host (e.g. "backend:8000" in Docker).
    // Falls back to: localhost:8000 in dev (port 5173), else same host as frontend.
    const envHost = import.meta.env.VITE_WS_HOST;
    const host = envHost
      ? envHost
      : window.location.port === '5173'
      ? 'localhost:8000'
      : window.location.host;
    return `${wsProto}//${host}/api/v1/ws?token=${encodeURIComponent(token)}`;
  }

  /**
   * Connects to the WebSocket server using the provided access token.
   */
  public connect(token?: string | null): void {
    const accessToken = token || localStorage.getItem('token');
    if (!accessToken) {
      this.setStatus('disconnected');
      return;
    }

    // Avoid duplicate connections if already open or connecting
    if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this.intentionalClose = false;
    this.setStatus(this.reconnectAttempt > 0 ? 'reconnecting' : 'connecting');

    try {
      const url = this.getWsUrl(accessToken);
      this.socket = new WebSocket(url);

      this.socket.onopen = () => {
        this.reconnectAttempt = 0;
        this.setStatus('connected');
        this.startHeartbeat();
      };

      this.socket.onmessage = (messageEvent: MessageEvent) => {
        try {
          const raw = JSON.parse(messageEvent.data);
          this.handleIncomingEvent(raw);
        } catch {
          // ignore non-json messages
        }
      };

      this.socket.onerror = (err) => {
        // Log softly without spamming console
        console.debug('[WS] Socket encounter:', err);
      };

      this.socket.onclose = (closeEvent: CloseEvent) => {
        this.stopHeartbeat();
        this.socket = null;

        // Policy violation / unauthorized token (code 1008) -> do not reconnect aggressively
        if (closeEvent.code === 1008 || this.intentionalClose) {
          this.setStatus('disconnected');
          this.reconnectAttempt = 0;
          return;
        }

        this.setStatus('disconnected');
        this.scheduleReconnect();
      };
    } catch {
      this.setStatus('disconnected');
      this.scheduleReconnect();
    }
  }

  /**
   * Cleanly closes the WebSocket connection (e.g. on user logout).
   */
  public disconnect(): void {
    this.intentionalClose = true;
    this.reconnectAttempt = 0;
    if (this.reconnectTimeoutId) {
      clearTimeout(this.reconnectTimeoutId);
      this.reconnectTimeoutId = null;
    }
    this.stopHeartbeat();
    if (this.socket) {
      try {
        this.socket.close(1000, 'User logged out');
      } catch {
        /* silent */
      }
      this.socket = null;
    }
    this.setStatus('disconnected');
  }

  /**
   * Schedules a reconnection attempt using exponential backoff with random jitter.
   */
  private scheduleReconnect(): void {
    if (this.intentionalClose) return;

    if (this.reconnectTimeoutId) {
      clearTimeout(this.reconnectTimeoutId);
    }

    const backoff = Math.min(
      this.MAX_BACKOFF_MS,
      this.BASE_DELAY_MS * Math.pow(2, this.reconnectAttempt)
    );
    // Add 10-25% random jitter to prevent thundering herd
    const jitter = Math.floor(Math.random() * (backoff * 0.25));
    const delay = backoff + jitter;

    this.setStatus('reconnecting');
    this.reconnectAttempt++;

    this.reconnectTimeoutId = setTimeout(() => {
      this.connect();
    }, delay);
  }

  /**
   * Heartbeat keep-alive pinging the server every 25 seconds.
   */
  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.pingIntervalId = setInterval(() => {
      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
        this.socket.send(JSON.stringify({ type: 'ping', timestamp: Date.now() }));
      }
    }, 25000);
  }

  private stopHeartbeat(): void {
    if (this.pingIntervalId) {
      clearInterval(this.pingIntervalId);
      this.pingIntervalId = null;
    }
  }

  /**
   * Handles incoming event envelopes and routes to registered listeners.
   */
  private handleIncomingEvent(event: WSEvent): void {
    if (!event || !event.event) return;

    // Deduplication check
    if (event.event_id) {
      if (this.processedEventIds.has(event.event_id)) {
        return; // Duplicate event skipped
      }
      this.processedEventIds.add(event.event_id);
      if (this.processedEventIds.size > 250) {
        // Prune oldest
        const [first] = this.processedEventIds;
        this.processedEventIds.delete(first);
      }
    }

    // Specific listeners
    const listeners = this.eventListeners.get(event.event);
    if (listeners) {
      listeners.forEach((callback) => {
        try {
          callback(event);
        } catch (e) {
          console.error(`[WS] Error in event listener for ${event.event}:`, e);
        }
      });
    }

    // Wildcard listeners ('*')
    const wildcardListeners = this.eventListeners.get('*');
    if (wildcardListeners) {
      wildcardListeners.forEach((callback) => {
        try {
          callback(event);
        } catch (e) {
          console.error('[WS] Error in wildcard event listener:', e);
        }
      });
    }
  }

  /**
   * Subscribes to a specific event type or '*' for all events.
   * Returns an unsubscription function.
   */
  public on(eventType: string, callback: EventCallback): () => void {
    if (!this.eventListeners.has(eventType)) {
      this.eventListeners.set(eventType, new Set());
    }
    this.eventListeners.get(eventType)!.add(callback);

    return () => {
      const set = this.eventListeners.get(eventType);
      if (set) {
        set.delete(callback);
        if (set.size === 0) {
          this.eventListeners.delete(eventType);
        }
      }
    };
  }

  /**
   * Subscribes to connection state changes.
   */
  public onStatusChange(callback: StatusCallback): () => void {
    this.statusListeners.add(callback);
    callback(this.status);
    return () => {
      this.statusListeners.delete(callback);
    };
  }

  private setStatus(newStatus: ConnectionStatus): void {
    if (this.status !== newStatus) {
      this.status = newStatus;
      this.statusListeners.forEach((cb) => {
        try {
          cb(newStatus);
        } catch {
          /* silent */
        }
      });
    }
  }

  public getStatus(): ConnectionStatus {
    return this.status;
  }
}

export const wsService = new WebSocketService();
