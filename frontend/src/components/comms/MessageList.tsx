"use client";

import React, { useEffect, useRef } from 'react';
import MessageItem, { Message } from './MessageItem'; // Import Message interface

interface MessageListProps {
  messages: Message[];
}

const MessageList: React.FC<MessageListProps> = ({ messages }) => {
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]); // Scroll to bottom whenever messages change

  return (
    <div className="flex-grow p-4 space-y-2 overflow-y-auto bg-mech-primary border border-mech-secondary rounded-md shadow-inner">
      {messages.length === 0 && (
        <div className="flex justify-center items-center h-full">
          <p className="text-mech-text-dark">No messages yet. Send one to start the conversation!</p>
        </div>
      )}
      {messages.map((msg) => (
        <MessageItem key={msg.id} message={msg} />
      ))}
      <div ref={messagesEndRef} />
    </div>
  );
};

export default MessageList;
