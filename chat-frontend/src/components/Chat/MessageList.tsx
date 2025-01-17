import { useState, useEffect, useRef } from 'react';
import { Message } from '../../types/chat';
import { ThreadView } from './ThreadView';
import { api } from '../../services/api';
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
  // Log raw messages at component start
  console.log('\nMessageList received raw messages:', messages.map(m => ({
    id: m.id, 
    threadId: m.threadId,
    content: m.content.substring(0, 20) + '...'
  })));

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
    
    if (isNewMessage) {
      console.log('Scrolling due to new message');
      scrollToBottom();
    }

    prevMessagesRef.current = messages;
  }, [messages]);

  const toggleThread = async (threadId: string) => {
    console.log('Toggling thread:', threadId);
    
    // Refresh messages to ensure we have latest data
    const updatedMessages = await api.messages.list(channelId);
    console.log('Refreshed messages:', updatedMessages.map(m => ({
      id: m.id,
      threadId: m.threadId,
      content: m.content.substring(0, 20) + '...'
    })));
    setMessages(updatedMessages);

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



  // Only include parent messages (those without a threadId) in the main list
  const threadGroups = messages
    .filter(message => !message.threadId) // Filter out replies
    .map(message => ({
      threadId: message.id,
      messages: [message, ...(message.replyMessages || [])]
    }));

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
            data-testid={`reply-in-thread-button-${firstMessage.id}`}
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
          {replyCount > 0 && (
            <button 
              data-testid={`show-replies-button-${thread.threadId}`}
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
          channelName={currentChannelName}
        />
      )}
    </div>
  );
}; 