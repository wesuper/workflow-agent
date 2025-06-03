"use client";

import ChatWindow from "@/components/comms/ChatWindow";
import { useEventStore, AgentEvent } from "@/hooks/useEventStore"; // Import store and event type
import { useEffect } from "react"; // For potential client-side only rendering of store data

export default function Home() {
  const events = useEventStore((state) => state.events);
  const isConnected = useEventStore((state) => state.isConnected);
  const clearEvents = useEventStore((state) => state.clearEvents);

  // This is to ensure events are only rendered on the client side after hydration
  const [isClient, setIsClient] = React.useState(false);
  useEffect(() => {
    setIsClient(true);
  }, []);

  return (
    <main className="flex min-h-screen flex-col items-center justify-start p-4 md:p-8 lg:p-12 bg-mech-primary space-y-4">
      <div className="w-full max-w-4xl text-center mb-4">
        <p className={`text-sm p-2 rounded-md ${isConnected ? 'bg-green-500/30 text-green-300' : 'bg-red-500/30 text-red-300'}`}>
          WebSocket Connected: {isConnected ? 'Yes' : 'No'}
        </p>
      </div>

      <ChatWindow />

      {isClient && ( // Only render event log on client side
        <div className="w-full max-w-4xl mt-6 p-4 bg-mech-secondary border border-mech-accent/30 rounded-lg shadow-md">
          <div className="flex justify-between items-center mb-2">
            <h3 className="text-lg font-semibold text-mech-text-light">Agent Event Log (Last {events.length} events):</h3>
            <button
              onClick={clearEvents}
              className="px-3 py-1 text-xs bg-red-600/70 hover:bg-red-500/70 text-white rounded-md transition-colors"
            >
              Clear Log
            </button>
          </div>
          <pre
            className="max-h-48 overflow-y-auto bg-mech-primary/50 p-3 rounded text-xs text-mech-text-dark scrollbar-thin scrollbar-thumb-mech-accent/50 scrollbar-track-mech-primary"
            style={{ scrollbarWidth: 'thin' }} // For Firefox
          >
            {events.length === 0 && <p>No events yet...</p>}
            {events.map((e) => (
              <div key={e.id} className="py-1 border-b border-mech-accent/10 last:border-b-0">
                <span className="font-semibold text-mech-accent/80">{e.type}</span>
                <span className="text-mech-text-dark/70 ml-2 text-[0.7rem]">({new Date(e.timestamp).toLocaleTimeString()})</span>
                {e.chat_id && <span className="text-blue-400/70 ml-2 text-[0.7rem]">Chat: {e.chat_id}</span>}
                <div className="pl-2 text-mech-text-dark/90 text-[0.75rem] whitespace-pre-wrap break-all">
                  {JSON.stringify(e.data, null, 2)}
                </div>
              </div>
            ))}
          </pre>
        </div>
      )}
    </main>
  );
}

// Added React to imports for useState/useEffect
import React from 'react';
