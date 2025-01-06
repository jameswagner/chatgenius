import { useState } from 'react';
import { PaperAirplaneIcon } from '@heroicons/react/24/outline';

interface MessageInputProps {
  channelId: string;
  threadId?: string;
  onSendMessage: (content: string) => void;
  placeholder?: string;
}

export const MessageInput = ({ 
  channelId, 
  threadId,
  onSendMessage, 
  placeholder = `Message #${channelId}`
}: MessageInputProps) => {
  const [message, setMessage] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (message.trim()) {
      onSendMessage(message);
      setMessage('');
    }
  };

  return (
    <form onSubmit={handleSubmit} className="px-4 py-3 border-t border-gray-200">
      <div className="flex items-center bg-white rounded-lg border border-gray-300">
        <input
          type="text"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder={threadId ? "Reply in thread..." : placeholder}
          className="flex-1 px-4 py-2 bg-transparent outline-none"
        />
        <button type="submit" className="p-2 hover:bg-gray-100 rounded-r-lg">
          <PaperAirplaneIcon className="h-5 w-5 text-gray-500" />
        </button>
      </div>
    </form>
  );
}; 