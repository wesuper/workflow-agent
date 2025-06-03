// frontend/src/utils/apiClient.ts

// Ensure NEXT_PUBLIC_AGENT_API_BASE_URL is accessed correctly in a Next.js context
// For client-side code, process.env.NEXT_PUBLIC_... is correct.
// For server-side (e.g. API routes if you had them in Next.js pages router), you'd use process.env directly.
const AGENT_API_BASE_URL = process.env.NEXT_PUBLIC_AGENT_API_BASE_URL;

export interface ApiChatMessage {
    user_id: string;
    chat_id: string;
    message: string;
    platform?: string; // Optional, as FastAPI endpoint has a default
}

export interface ApiChatResponse {
    reply: string;
    chat_id: string;
    timestamp: string; // Assuming ISO string from FastAPI
}

export async function sendMessageToAgent(payload: ApiChatMessage): Promise<ApiChatResponse> {
    if (!AGENT_API_BASE_URL) {
        console.error("Agent API base URL is not configured. Check NEXT_PUBLIC_AGENT_API_BASE_URL environment variable.");
        // Fallback or throw error to indicate configuration issue to the user/developer
        // For a user-facing app, you might want to return a structured error response or a specific error object.
        throw new Error("API Error: Agent API base URL is not configured.");
    }

    try {
        const response = await fetch(`${AGENT_API_BASE_URL}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        if (!response.ok) {
            let errorData: any = { detail: 'Unknown error structure from API.' };
            try {
                // Attempt to parse error response from API, which might be JSON
                errorData = await response.json();
            } catch (e) {
                // If error response is not JSON, use statusText or a generic message
                errorData.detail = response.statusText || `HTTP error ${response.status}`;
            }
            console.error("API Error Data:", errorData);
            throw new Error(`API Error: ${response.status} ${response.statusText} - ${errorData.detail || 'Failed to send message'}`);
        }
        return response.json();
    } catch (error) {
        // Catch network errors or other issues with the fetch call itself
        console.error("Network or other error in sendMessageToAgent:", error);
        if (error instanceof Error) { // error is already an Error object
             throw error; // Re-throw the original error or a more specific one
        }
        throw new Error("Network error or unexpected issue sending message to agent.");
    }
}
