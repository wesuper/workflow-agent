"use client"; // Required for components with state and event handlers in Next.js App Router

import React, { useState } from 'react';

interface MessageInputProps {
  onSendMessage: (message: string) => void;
  isLoading: boolean;
}

const MessageInput: React.FC<MessageInputProps> = ({ onSendMessage, isLoading }) => {
  const [inputText, setInputText] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (inputText.trim() && !isLoading) {
      onSendMessage(inputText.trim());
      setInputText('');
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex items-center p-2 bg-mech-secondary border-t border-mech-accent/50">
      <input
        type="text"
        value={inputText}
        onChange={(e) => setInputText(e.target.value)}
        placeholder={isLoading ? "Agent is thinking..." : "Type your message..."}
        disabled={isLoading}
        className="flex-grow p-3 bg-mech-primary/80 text-mech-text-light border border-mech-accent/70 rounded-l-md focus:ring-1 focus:ring-mech-accent focus:outline-none placeholder-mech-text-dark transition-colors duration-150"
      />
      <button
        type="submit"
        disabled={isLoading}
        className={`p-3 px-6 bg-mech-accent text-white rounded-r-md hover:bg-opacity-80 focus:outline-none focus:ring-2 focus:ring-mech-accent/70 focus:ring-offset-2 focus:ring-offset-mech-secondary transition-all duration-150 ease-in-out
                    ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}
                    active:scale-95`}
      >
        {isLoading ? (
          <svg className="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
        ) : (
          'Send'
        )}
      </button>
    </form>
  );
};

export default MessageInput;
