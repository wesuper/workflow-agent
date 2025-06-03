"use client";

import React, { useEffect, useRef, ReactNode } from 'react';
import WebSocketManager from '@/utils/webSocketClient';
import { useEventStore, AgentEvent } from '@/hooks/useEventStore';
// import { toast } from 'react-hot-toast'; // Optional, if toasts are used

const WebSocketProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const addEvent = useEventStore((state) => state.addEvent);
    const setConnected = useEventStore((state) => state.setConnected);
    const wsManagerRef = useRef<WebSocketManager | null>(null);

    useEffect(() => {
        // Ensure this effect runs only once on client-side
        if (typeof window === "undefined" || wsManagerRef.current) {
            return;
        }

        const wsUrl = process.env.NEXT_PUBLIC_AGENT_WEBSOCKET_URL;
        if (!wsUrl) {
            console.error("WebSocketProvider: NEXT_PUBLIC_AGENT_WEBSOCKET_URL is not configured in .env.local. WebSocket will not connect.");
            // toast.error("WebSocket URL not configured!");
            return;
        }

        console.log("WebSocketProvider: Initializing WebSocketManager...");
        const manager = new WebSocketManager(wsUrl, {
            onOpen: () => {
                console.log("WebSocketProvider: Connection opened.");
                setConnected(true);
                // toast.success('Agent event stream connected!', { id: 'websocket-provider-status' });
            },
            onMessage: (data: Omit<AgentEvent, 'id'>) => { // Data from server doesn't have client-side 'id'
                // console.log("WebSocketProvider: Event received from server:", data);
                addEvent(data);
            },
            onClose: (event) => {
                console.log("WebSocketProvider: Connection closed.", event.reason);
                setConnected(false);
                // if (!event.wasClean) {
                //    toast.error('Agent event stream disconnected unexpectedly.', { id: 'websocket-provider-status' });
                // } else {
                //    toast.success('Agent event stream disconnected.', { id: 'websocket-provider-status' });
                // }
            },
            onError: (event) => {
                console.error("WebSocketProvider: Connection error.", event);
                setConnected(false);
                // toast.error('Agent event stream connection error.', { id: 'websocket-provider-status' });
            },
        });

        manager.connect();
        wsManagerRef.current = manager;

        // Cleanup function for when the component unmounts or dependencies change
        return () => {
            console.log("WebSocketProvider: Cleanup - disconnecting WebSocket.");
            if (wsManagerRef.current) {
                wsManagerRef.current.disconnect();
                wsManagerRef.current = null; // Clear the ref
            }
        };
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []); // Empty dependency array ensures this runs once on mount and cleans up on unmount

    return <>{children}</>;
};

export default WebSocketProvider;
