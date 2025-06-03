"use client";

import React, { useState, useEffect } from 'react';
import MessageList from './MessageList';
import MessageInput from './MessageInput';
import { Message } from './MessageItem'; // Shared interface
import { sendMessageToAgent, ApiChatMessage } from '@/utils/apiClient'; // Using import alias

const ChatWindow: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Example: Load initial greeting or persisted messages (not implemented here)
  // useEffect(() => {
  //   setMessages([
  //     { id: 'agent-greeting', text: 'Hello! I am IM-Agent. How can I assist you today?', sender: 'agent', timestamp: new Date().toISOString() }
  #   ]);
  // }, []);

  const handleSendMessage = async (inputText: string) => {
    if (!inputText.trim()) return;

    const userMessage: Message = {
      id: `user-${Date.now()}`, // Simple unique ID
      text: inputText,
      sender: 'user',
      timestamp: new Date().toISOString(),
    };

    setMessages((prevMessages) => [...prevMessages, userMessage]);
    setIsLoading(true);
    setError(null); // Clear previous errors

    const apiPayload: ApiChatMessage = {
      user_id: "frontend_user_01", // Hardcoded for now
      chat_id: "session_frontend_default", // Hardcoded for now
      message: inputText,
      platform: "frontend_chat_window" // Specify platform
    };

    try {
      const response = await sendMessageToAgent(apiPayload);
      const agentMessage: Message = {
        id: `agent-${Date.now()}`,
        text: response.reply,
        sender: 'agent',
        timestamp: response.timestamp || new Date().toISOString(), // Use server timestamp if available
      };
      setMessages((prevMessages) => [...prevMessages, agentMessage]);
    } catch (err: any) {
      console.error("Failed to send message or get reply:", err);
      const errorMessage: Message = {
        id: `error-${Date.now()}`,
        text: `Error: ${err.message || 'Could not connect to agent.'}`,
        sender: 'agent', // Display error as an agent message for now
        timestamp: new Date().toISOString(),
      };
      setMessages((prevMessages) => [...prevMessages, errorMessage]);
      setError(err.message || 'Could not connect to agent.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-100px)] max-w-3xl mx-auto bg-mech-secondary shadow-2xl rounded-lg border border-mech-accent/30">
      {/* Optional Header */}
      <div className="p-3 border-b border-mech-accent/50 text-center">
        <h1 className="text-xl font-semibold text-mech-text-light">IM-AGENT COMMS CONSOLE</h1>
      </div>

      {error && (
        <div className="p-2 bg-red-500/20 text-red-300 text-center text-sm">
          {error}
        </div>
      )}

      <div className="flex-grow overflow-hidden"> {/* Container for MessageList to manage its own scroll */}
        <MessageList messages={messages} />
      </div>

      <MessageInput onSendMessage={handleSendMessage} isLoading={isLoading} />
    </div>
  );
};

export default ChatWindow;
