import {create} from 'zustand'; // Default import

export interface AgentEvent { // Exporting for potential use elsewhere
    type: string;
    timestamp: number | string; // Allow both number (e.g. loop.time()) or string (ISO format)
    chat_id?: string;
    data: any;
    // Add a unique ID for React list keys, assigned client-side
    id: string;
}

interface EventStoreState {
    events: AgentEvent[];
    isConnected: boolean;
    maxEvents: number; // To control the size of the events array
    addEvent: (event: Omit<AgentEvent, 'id'>) => void; // Input event doesn't have client-side id yet
    setConnected: (status: boolean) => void;
    clearEvents: () => void;
}

let eventIdCounter = 0;

export const useEventStore = create<EventStoreState>((set, get) => ({
    events: [],
    isConnected: false,
    maxEvents: 100, // Default max number of events to keep in the store
    addEvent: (eventData) => {
        const newEventWithId: AgentEvent = {
            ...eventData,
            id: `evt-${Date.now()}-${eventIdCounter++}` // More unique ID
        };
        set((state) => ({
            events: [...state.events, newEventWithId].slice(-state.maxEvents)
        }));
    },
    setConnected: (status) => set({ isConnected: status }),
    clearEvents: () => set({ events: [] }),
}));
