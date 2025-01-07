import { useState, useEffect } from 'react';
import { Message } from '../../types/chat';
import { MessageInput } from './MessageInput';
import { format } from 'date-fns';
import { api } from '../../services/api';
import { MessageReactions } from './MessageReactions';

interface ThreadViewProps {
  parentMessage: Message;
  onClose: () => void;
}

export const ThreadView = ({ parentMessage, onClose }: ThreadViewProps) => {
  const [replies, setReplies] = useState<Message[]>([]);
  const currentUserId = localStorage.getItem('userId');
  const [parentWithReactions, setParentWithReactions] = useState(parentMessage);

  // Fetch thread messages and parent message periodically
  useEffect(() => {
    const fetchMessages = async () => {
      try {
        const [threadReplies, updatedParent] = await Promise.all([
          api.messages.getThreadMessages(parentMessage.id),
          api.messages.get(parentMessage.id)
        ]);
        // Filter out the parent message from replies
        const actualReplies = threadReplies.filter(msg => msg.id !== parentMessage.id);
        setReplies(actualReplies);
        setParentWithReactions(updatedParent);
      } catch (err) {
        console.error('Failed to fetch messages:', err);
      }
    };
    fetchMessages();

    const interval = setInterval(fetchMessages, 3000);
    return () => clearInterval(interval);
  }, [parentMessage.id]);

  const handleReactionChange = async () => {
    try {
      const [threadReplies, updatedParent] = await Promise.all([
        api.messages.getThreadMessages(parentMessage.id),
        api.messages.get(parentMessage.id)
      ]);
      setReplies(threadReplies);
      setParentWithReactions(updatedParent);
    } catch (err) {
      console.error('Failed to update reactions:', err);
    }
  };

  const handleReply = async (content: string) => {
    try {
      const reply = await api.messages.createThreadReply(parentMessage.id, { content });
      setReplies(prev => [...prev, reply]);
    } catch (err) {
      console.error('Failed to send reply:', err);
    }
  };

  const formatTime = (dateString: string) => {
    const date = new Date(dateString);
    
    // Format in local timezone
    const formatted = format(date, 'h:mm a');
    
    // Check if date is before today
    const today = new Date();
    if (date.toDateString() < today.toDateString()) {
      const dateFormatted = format(date, 'MMM d');
      return `${dateFormatted} ${formatted}`;
    }
    
    return formatted;
  };

  const renderMessage = (message: Message, isParent = false) => {
    const isCurrentUser = message.userId === currentUserId;
    
    return (
      <div className="flex items-start">
        <div className={`${isParent ? 'h-10 w-10' : 'h-8 w-8'} rounded bg-gray-300 flex-shrink-0`} />
        <div className={`ml-3 flex-1 ${isCurrentUser ? 'bg-blue-50 p-2 rounded' : ''}`}>
          <div className="flex items-center">
            <span className={`font-bold ${isCurrentUser ? 'text-blue-700' : ''}`}>
              {message.user?.name}
            </span>
            <span className="ml-2 text-xs text-gray-500">
              {formatTime(message.createdAt)}
            </span>
          </div>
          <p className={`${isCurrentUser ? 'text-blue-900' : 'text-gray-900'}`}>
            {message.content}
          </p>
        </div>
      </div>
    );
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
          {renderMessage(parentWithReactions, true)}
          <MessageReactions 
            message={parentWithReactions}
            onReactionChange={handleReactionChange}
          />
        </div>

        {/* Replies */}
        {replies.map(reply => (
          <div key={reply.id} className="mb-4">
            {renderMessage(reply)}
            <MessageReactions 
              message={reply}
              onReactionChange={handleReactionChange}
            />
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