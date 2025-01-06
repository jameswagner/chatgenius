import { useState, useEffect } from 'react';
import { Message } from '../../types/chat';
import { MessageInput } from './MessageInput';
import { format } from 'date-fns';
import { api } from '../../services/api';

interface ThreadViewProps {
  parentMessage: Message;
  onClose: () => void;
}

export const ThreadView = ({ parentMessage, onClose }: ThreadViewProps) => {
  const [replies, setReplies] = useState<Message[]>([]);

  // Fetch thread messages periodically
  useEffect(() => {
    const fetchReplies = async () => {
      try {
        const data = await api.messages.getThreadMessages(parentMessage.id);
        setReplies(data);
      } catch (err) {
        console.error('Failed to fetch replies:', err);
      }
    };
    fetchReplies();

    const interval = setInterval(fetchReplies, 3000);
    return () => clearInterval(interval);
  }, [parentMessage.id]);

  const handleReply = async (content: string) => {
    try {
      const reply = await api.messages.createThreadReply(parentMessage.id, { content });
      setReplies(prev => [...prev, reply]);
    } catch (err) {
      console.error('Failed to send reply:', err);
    }
  };

  const formatTime = (dateString: string) => {
    return format(new Date(dateString), 'h:mm a');
  };

  return (
    <div className="w-96 border-l border-gray-200 flex flex-col h-full">
      <div className="p-4 border-b border-gray-200 flex justify-between items-center">
        <h3 className="font-bold">Thread</h3>
        <button onClick={onClose} className="text-gray-500 hover:text-gray-700">✕</button>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {/* Parent Message */}
        <div className="mb-4 pb-4 border-b border-gray-200">
          <div className="flex items-start">
            <div className="h-10 w-10 rounded bg-gray-300 flex-shrink-0" />
            <div className="ml-3">
              <div className="flex items-center">
                <span className="font-bold">{parentMessage.user?.name}</span>
                <span className="ml-2 text-xs text-gray-500">
                  {formatTime(parentMessage.createdAt)}
                </span>
              </div>
              <p className="text-gray-900">{parentMessage.content}</p>
            </div>
          </div>
        </div>

        {/* Replies */}
        {replies.map(reply => (
          <div key={reply.id} className="mb-4">
            <div className="flex items-start">
              <div className="h-8 w-8 rounded bg-gray-300 flex-shrink-0" />
              <div className="ml-3">
                <div className="flex items-center">
                  <span className="font-bold">{reply.user?.name}</span>
                  <span className="ml-2 text-xs text-gray-500">
                    {formatTime(reply.createdAt)}
                  </span>
                </div>
                <p className="text-gray-900">{reply.content}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="p-4 border-t border-gray-200">
        <MessageInput 
          channelId={parentMessage.channelId}
          threadId={parentMessage.id}
          onSendMessage={handleReply}
          placeholder="Reply in thread..."
        />
      </div>
    </div>
  );
}; 