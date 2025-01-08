import { useState, useEffect } from 'react';
import { Message } from '../../types/chat';
import { formatInTimeZone } from 'date-fns-tz';
import { format } from 'date-fns';
import { ThreadView } from './ThreadView';
import { api } from '../../services/api';
import { MessageReactions } from './MessageReactions';
import { ChatMessage } from './ChatMessage';

interface MessageListProps {
  channelId: string;
  messages: Message[];
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  currentChannelName: string;
  onThreadClick?: (messageId: string) => void;
}

interface ThreadGroup {
  threadId: string;
  messages: Message[];
}

export const MessageList = ({ channelId, messages, setMessages, currentChannelName, onThreadClick }: MessageListProps) => {

  const [selectedThread, setSelectedThread] = useState<Message | null>(null);
  const [expandedThreads, setExpandedThreads] = useState<Set<string>>(new Set());
  const currentUserId = localStorage.getItem('userId');

  const threadGroups = messages.reduce((groups: ThreadGroup[], message) => {
    const group = groups.find(g => g.threadId === message.threadId);
    if (group) {
      group.messages.push(message);
    } else {
      groups.push({ threadId: message.threadId, messages: [message] });
    }
    return groups;
  }, []);

  const formatTime = (dateString: string) => {
    const date = new Date(dateString);

    const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    
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

  const toggleThread = (threadId: string) => {
    setExpandedThreads(prev => {
      const next = new Set(prev);
      if (next.has(threadId)) {
        next.delete(threadId);
      } else {
        next.add(threadId);
      }
      return next;
    });
  };

  const renderMessage = (message: Message, isReply = false) => {
    return (
      <ChatMessage
        key={message.id}
        message={{
          ...message,
          attachments: message.attachments || []
        }}
        isReply={isReply}
        onReactionChange={async () => {
          const updatedMessages = await api.messages.list(channelId);
          setMessages(updatedMessages.map((msg: Message) => ({
            ...msg,
            attachments: msg.attachments || []
          })));
        }}
        onThreadClick={onThreadClick ? () => onThreadClick(message.id) : undefined}
      />
    );
  };

  const renderThread = (thread: ThreadGroup) => {
    const [firstMessage, ...replies] = thread.messages;
    const isExpanded = expandedThreads.has(thread.threadId);
    const replyCount = replies.length;
    const replyText = replyCount === 1 ? '1 reply' : `${replyCount} replies`;

    return (
      <div key={thread.threadId} className="mb-6">
        {/* First message */}
        {renderMessage(firstMessage)}

        <div className="flex items-center mt-1 space-x-3 ml-13">
          <button 
            onClick={() => setSelectedThread(firstMessage)}
            className="text-sm text-blue-500 hover:text-blue-700"
          >
            Reply in thread
          </button>
          {replies.length > 0 && (
            <button 
              onClick={() => toggleThread(thread.threadId)}
              className="text-sm text-gray-500 hover:text-gray-700 flex items-center"
            >
              <span className="mr-1">{replyText}</span>
              <span className="transform transition-transform duration-200" style={{
                transform: isExpanded ? 'rotate(180deg)' : 'none'
              }}>
                ▼
              </span>
            </button>
          )}
        </div>

        {/* Replies */}
        {replies.length > 0 && isExpanded && (
          <div className="ml-12 mt-2 space-y-2 border-l-2 border-gray-200 pl-4">
            {replies.map(reply => renderMessage(reply, true))}
          </div>
        )}
      </div>
    );
  };

  useEffect(() => {
    const fetchMessages = async () => {
      try {
        const data = await api.messages.list(channelId);
        setMessages(data);
      } catch (err) {
        console.error('Failed to fetch messages:', err);
      }
    };
    fetchMessages();
  }, [channelId]);

  return (
    <div className="flex h-full">
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {threadGroups.map(renderThread)}
      </div>
      
      {selectedThread && (
        <ThreadView 
          parentMessage={selectedThread}
          onClose={() => setSelectedThread(null)}
        />
      )}
    </div>
  );
}; 