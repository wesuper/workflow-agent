// frontend/src/utils/webSocketClient.ts
// import { toast } from 'react-hot-toast'; // Optional: for user notifications

interface WebSocketManagerOptions {
    onOpen?: (event: Event) => void;
    onMessage?: (eventData: any) => void; // Assuming JSON data
    onError?: (event: Event) => void;
    onClose?: (event: CloseEvent) => void;
    reconnectInterval?: number;
    maxReconnectAttempts?: number;
}

class WebSocketManager {
    private ws: WebSocket | null = null;
    private url: string;
    private options: WebSocketManagerOptions;
    private reconnectAttempts = 0;
    private explicitlyClosed = false;
    private reconnectTimeoutId: NodeJS.Timeout | null = null;


    constructor(url: string, options: WebSocketManagerOptions = {}) {
        this.url = url;
        this.options = {
            reconnectInterval: options.reconnectInterval || 5000, // Default 5 seconds
            maxReconnectAttempts: options.maxReconnectAttempts || 10, // Default 10 attempts
            ...options,
        };
        // console.log("WebSocketManager instance created.");
    }

    public connect() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            console.log("WebSocket already connected.");
            return;
        }
        if (this.ws && this.ws.readyState === WebSocket.CONNECTING) {
            console.log("WebSocket connection attempt already in progress.");
            return;
        }

        this.explicitlyClosed = false;
        this.ws = new WebSocket(this.url);
        console.log(`Attempting to connect to WebSocket: ${this.url}`);
        // toast.loading('Connecting to agent event stream...', { id: 'websocket-status' });

        this.ws.onopen = (event) => {
            console.log("WebSocket connected successfully.");
            // toast.success('Agent event stream connected!', { id: 'websocket-status' });
            this.reconnectAttempts = 0; // Reset on successful connection
            if (this.reconnectTimeoutId) {
                clearTimeout(this.reconnectTimeoutId);
                this.reconnectTimeoutId = null;
            }
            if (this.options.onOpen) {
                this.options.onOpen(event);
            }
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data as string);
                // console.debug("WebSocket message received:", data); // Can be very verbose
                if (this.options.onMessage) {
                    this.options.onMessage(data);
                }
            } catch (error) {
                console.error("Error parsing WebSocket message:", error, event.data);
            }
        };

        this.ws.onerror = (event) => {
            console.error("WebSocket error:", event);
            // toast.error('Agent event stream connection error.', { id: 'websocket-status' });
            if (this.options.onError) {
                this.options.onError(event);
            }
            // The 'onclose' event will usually follow an error, which handles reconnection logic.
            // If it doesn't, we might need to trigger reconnection attempt here too after a delay.
        };

        this.ws.onclose = (event) => {
            console.log(`WebSocket disconnected. Code: ${event.code}, Reason: '${event.reason}', WasClean: ${event.wasClean}`);
            // toast.dismiss('websocket-status'); // Dismiss any loading/status toasts
            if (this.options.onClose) {
                this.options.onClose(event);
            }
            if (!this.explicitlyClosed && this.reconnectAttempts < this.options.maxReconnectAttempts!) {
                this.reconnectAttempts++;
                console.log(`WebSocket attempting to reconnect (${this.reconnectAttempts}/${this.options.maxReconnectAttempts})...`);
                // toast.loading(`Agent event stream disconnected. Reconnecting (${this.reconnectAttempts})...`, { id: 'websocket-status' });
                if (this.reconnectTimeoutId) clearTimeout(this.reconnectTimeoutId); // Clear existing timeout if any
                this.reconnectTimeoutId = setTimeout(() => this.connect(), this.options.reconnectInterval);
            } else if (!this.explicitlyClosed) {
                console.error("WebSocket max reconnect attempts reached. Won't try again unless explicitly connected.");
                // toast.error('Failed to reconnect to agent event stream.', { id: 'websocket-status', duration: 10000 });
            }
        };
    }

    public disconnect() {
        this.explicitlyClosed = true;
        if (this.reconnectTimeoutId) {
            clearTimeout(this.reconnectTimeoutId);
            this.reconnectTimeoutId = null;
        }
        if (this.ws) {
            this.ws.close();
            console.log("WebSocket explicitly disconnected by client.");
        } else {
            console.log("WebSocket already disconnected or never connected.");
        }
    }

    public sendMessage(message: string | object) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            const messageStr = typeof message === 'string' ? message : JSON.stringify(message);
            this.ws.send(messageStr);
        } else {
            console.error("WebSocket not connected. Cannot send message.");
            // toast.error("Cannot send message: Not connected to agent event stream.");
        }
    }

    public getReadyState(): number | null {
        return this.ws ? this.ws.readyState : null;
    }
}
export default WebSocketManager;
