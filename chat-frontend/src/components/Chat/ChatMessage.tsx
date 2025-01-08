import { Message as MessageType } from '../../types/chat';
import { DocumentIcon, ChatBubbleLeftIcon } from '@heroicons/react/24/outline';
import { MessageReactions } from './MessageReactions';
import { API_BASE_URL } from '../../config/api';
import { formatMessageTimestamp } from '../../utils/dateUtils';
import { useState, useEffect, useCallback } from 'react';

const STATUS_ICONS: { [key: string]: string } = {
  online: '🟢',
  away: '🌙',
  busy: '⛔',
  offline: '⭘'
};

interface ChatMessageProps {
  message: MessageType;
  isReply?: boolean;
  onReactionChange: () => void;
  onThreadClick?: () => void;
  isHighlighted?: boolean;
  onClick?: () => void;
}

export const ChatMessage = ({ message, isReply = false, onReactionChange, onThreadClick, isHighlighted = false, onClick }: ChatMessageProps) => {
  const currentUserId = localStorage.getItem('userId');
  const isCurrentUser = message.userId === currentUserId;

  const getFileUrl = (filename: string) => `${API_BASE_URL}/uploads/${filename}`;

  const handleFileClick = useCallback(async (e: React.MouseEvent, filename: string) => {
    e.preventDefault();
    try {
      const response = await fetch(`${API_BASE_URL}/uploads/${filename}`);
      const data = await response.json();
      if (data.url) {
        window.open(data.url, '_blank');
      }
    } catch (err) {
      console.error('Failed to get file URL:', err);
    }
  }, []);

  return (
    <div 
      id={`message-${message.id}`}
      className={`flex items-start p-2 ${
        isCurrentUser ? 'bg-blue-50' : ''
      } ${
        isHighlighted ? 'bg-yellow-50' : ''
      } ${
        onClick ? 'cursor-pointer hover:bg-gray-50' : ''
      }`}
      onClick={onClick}
    >
      <div className={`${isReply ? 'h-8 w-8' : 'h-10 w-10'} rounded bg-gray-300 flex-shrink-0 flex items-center justify-center`}>
        <span className="text-gray-500 font-medium">
          {(message.user?.name ?? '?').charAt(0).toUpperCase()}
        </span>
      </div>
      <div className="ml-3 flex-1">
        <div className="flex items-center gap-2">
          <span className={`font-bold ${isCurrentUser ? 'text-blue-700' : ''}`}>
            {message.user?.name}
          </span>
          <span className="text-sm text-gray-500">
            {STATUS_ICONS[message.user?.status || 'offline']}
          </span>
          <span className="text-xs text-gray-500">
            {formatMessageTimestamp(message.createdAt)}
          </span>
        </div>
        <p className={`mt-1 ${isCurrentUser ? 'text-blue-900' : 'text-gray-900'}`}>
          {message.content}
        </p>

        {/* Attachments */}
        {message.attachments && message.attachments.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-2">
            {message.attachments.map(filename => {
              const isImage = /\.(jpg|jpeg|png|gif|webp)$/i.test(filename);
              const fileUrl = getFileUrl(filename);
              const [imageUrl, setImageUrl] = useState<string>('');

              useEffect(() => {
                const fetchImageUrl = async () => {
                  try {
                    const response = await fetch(`${API_BASE_URL}/uploads/${filename}`);
                    const data = await response.json();
                    if (data.url) {
                      setImageUrl(data.url);
                    }
                  } catch (err) {
                    console.error('Failed to fetch image URL:', err);
                  }
                };

                fetchImageUrl();
              }, [filename]);
              
              return isImage ? (
                <a 
                  key={filename}
                  href={fileUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block"
                >
                  {imageUrl ? (
                    <img 
                      src={imageUrl} 
                      alt="attachment" 
                      className="max-h-32 rounded border border-gray-200"
                      onError={(e) => console.log('Image load error:', e)}
                    />
                  ) : (
                    <div>Loading...</div>
                  )}
                </a>
              ) : (
                <a
                  key={filename}
                  href="#"
                  onClick={(e) => handleFileClick(e, filename)}
                  className="flex items-center gap-1 text-blue-500 hover:text-blue-600"
                >
                  <DocumentIcon className="h-5 w-5" />
                  <span className="text-sm">{filename}</span>
                </a>
              );
            })}
          </div>
        )}

        <MessageReactions 
          message={message}
          onReactionChange={onReactionChange}
        />

        {onThreadClick && (
          <button
            onClick={onThreadClick}
            className="mt-1 text-gray-400 hover:text-gray-600 flex items-center gap-1"
          >
            <ChatBubbleLeftIcon className="h-4 w-4" />
            <span className="text-sm">
              {message.replyCount 
                ? `${message.replyCount} ${message.replyCount === 1 ? 'reply' : 'replies'}`
                : 'Reply'
              }
            </span>
          </button>
        )}
      </div>
    </div>
  );
}; 