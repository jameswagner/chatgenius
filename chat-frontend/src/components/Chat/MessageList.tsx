import { useState, useEffect, useRef } from 'react';
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
  setMessages: (messages: Message[]) => void;
  currentChannelName: string;
  onThreadClick?: (messageId: string) => void;
}

interface ThreadGroup {
  threadId: string;
  messages: Message[];
}

export const MessageList = ({ channelId, messages, setMessages, currentChannelName, onThreadClick }: MessageListProps) => {
  const [expandedThreads, setExpandedThreads] = useState<Set<string>>(new Set());
  const [selectedThread, setSelectedThread] = useState<Message | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Track previous messages for comparison
  const prevMessagesRef = useRef(messages);

  const scrollToBottom = () => {
    console.log('Attempting to scroll to bottom');
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // Scroll to bottom when messages change
  useEffect(() => {
    const prevMessages = prevMessagesRef.current;
    const isNewMessage = messages.length > prevMessages.length;
    
    console.log('Messages changed:', {
      prevLength: prevMessages.length,
      newLength: messages.length,
      isNewMessage,
      lastMessage: messages[messages.length - 1]
    });
    
    if (isNewMessage) {
      console.log('Scrolling due to new message');
      scrollToBottom();
    } else {
      console.log('Not scrolling - message was edited or no new message');
    }

    prevMessagesRef.current = messages;
  }, [messages]);

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

  // Group messages by thread
  const threadGroups = messages.reduce((groups: ThreadGroup[], message) => {
    if (!message.threadId || message.threadId === message.id) {
      // This is a parent message
      groups.push({
        threadId: message.id,
        messages: [message]
      });
    } else {
      // This is a reply
      const parentGroup = groups.find(g => g.threadId === message.threadId);
      if (parentGroup) {
        parentGroup.messages.push(message);
      }
    }
    return groups;
  }, []);

  const renderMessage = (message: Message, isReply = false) => {
    return (
      <ChatMessage
        key={message.id}
        message={message}
        isReply={isReply}
        onReactionChange={async () => {
          const updatedMessages = await api.messages.list(channelId);
          setMessages(updatedMessages);
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
        {renderMessage(firstMessage)}

        <div className="flex items-center mt-1 space-x-3 ml-13">
          <button 
            onClick={() => {
              if (onThreadClick) {
                onThreadClick(firstMessage.id);
              } else {
                setSelectedThread(firstMessage);
              }
            }}
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

        {replies.length > 0 && isExpanded && (
          <div className="ml-12 mt-2 space-y-2 border-l-2 border-gray-200 pl-4">
            {replies.map(reply => renderMessage(reply, true))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="flex h-full">
      <div className="flex-1 overflow-y-auto p-4 message-list">
        {threadGroups.map(thread => renderThread(thread))}
        <div ref={messagesEndRef} />
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