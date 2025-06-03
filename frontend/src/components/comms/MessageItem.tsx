"use client";

import React from 'react';

export interface Message {
  id: string;
  text: string;
  sender: "user" | "agent";
  timestamp?: string; // Optional: ISO string format
}

interface MessageItemProps {
  message: Message;
}

const MessageItem: React.FC<MessageItemProps> = ({ message }) => {
  const isUser = message.sender === 'user';

  // Basic date formatting, can be enhanced with a library like date-fns or moment
  const formatTimestamp = (isoString?: string) => {
    if (!isoString) return '';
    try {
      return new Date(isoString).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch (e) {
      return ''; // Invalid date string
    }
  };

  return (
    <div className={`flex my-2 ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[70%] p-3 rounded-lg shadow-md break-words
                    ${isUser
                      ? 'bg-mech-accent text-white rounded-br-none'
                      : 'bg-mech-secondary text-mech-text-light rounded-bl-none'
                    }`}
      >
        <p className="text-sm whitespace-pre-wrap">{message.text}</p>
        {message.timestamp && (
          <p className={`text-xs mt-1 ${isUser ? 'text-blue-100' : 'text-mech-text-dark'}`}>
            {formatTimestamp(message.timestamp)}
          </p>
        )}
      </div>
    </div>
  );
};

export default MessageItem;
