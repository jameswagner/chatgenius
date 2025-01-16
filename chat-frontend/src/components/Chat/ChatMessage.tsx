import { Message as MessageType } from '../../types/chat';
import { DocumentIcon, ChatBubbleLeftIcon, PencilIcon } from '@heroicons/react/24/outline';
import { MessageReactions } from './MessageReactions';
import { API_BASE_URL } from '../../config/api';
import { formatMessageTimestamp } from '../../utils/dateUtils';
import { useState, useEffect, useCallback } from 'react';
import { api } from '../../services/api';

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
  const [isEditing, setIsEditing] = useState(false);
  const [editContent, setEditContent] = useState(message.content);
  const [imageUrls, setImageUrls] = useState<{ [key: string]: string }>({});

  // Fetch presigned URLs for images when message loads
  useEffect(() => {
    const fetchImageUrls = async () => {
      if (message.attachments) {
        const imageFiles = message.attachments.filter(filename => 
          /\.(jpg|jpeg|png|gif|webp)$/i.test(filename)
        );
        
        for (const filename of imageFiles) {
          try {
            const response = await fetch(`${API_BASE_URL}/uploads/${filename}`);
            const data = await response.json();
            if (data.url) {
              setImageUrls(prev => ({ ...prev, [filename]: data.url }));
            }
          } catch (err) {
            console.error('Failed to get image URL:', err);
          }
        }
      }
    };
    
    fetchImageUrls();
  }, [message.attachments]);

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

  const handleEdit = async () => {
    if (!isCurrentUser) {
      console.error('Cannot edit message: not the message owner');
      return;
    }

    if (!isEditing) {
      setIsEditing(true);
      return;
    }

    const trimmedContent = editContent.trim();
    if (!trimmedContent || trimmedContent === message.content) {
      setIsEditing(false);
      setEditContent(message.content);
      return;
    }

    try {
      await api.messages.update(message.id, {
        content: trimmedContent
      });
      setIsEditing(false);
    } catch (error) {
      console.error('Failed to update message:', error);
      setEditContent(message.content);
      setIsEditing(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!isCurrentUser) return;

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleEdit();
    } else if (e.key === 'Escape') {
      setIsEditing(false);
      setEditContent(message.content);
    }
  };

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
          {message.isEdited && (
            <span className="text-xs text-gray-400">(edited)</span>
          )}
          {isCurrentUser && !isEditing && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                handleEdit();
              }}
              className="text-gray-400 hover:text-gray-600"
            >
              <PencilIcon className="h-4 w-4" />
            </button>
          )}
        </div>
        {isEditing ? (
          <div className="mt-1">
            <textarea
              value={editContent}
              onChange={(e) => setEditContent(e.target.value)}
              onKeyDown={handleKeyDown}
              className="w-full p-2 border rounded focus:outline-none focus:border-blue-500"
              rows={3}
              autoFocus
            />
            <div className="mt-2 flex gap-2">
              <button
                onClick={handleEdit}
                className="px-3 py-1 bg-blue-500 text-white rounded hover:bg-blue-600"
              >
                Save
              </button>
              <button
                onClick={() => {
                  setIsEditing(false);
                  setEditContent(message.content);
                }}
                className="px-3 py-1 bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <p className={`mt-1 ${isCurrentUser ? 'text-blue-900' : 'text-gray-900'}`}>
            {message.content}
          </p>
        )}

        {/* Attachments */}
        {message.attachments && message.attachments.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-2">
            {message.attachments.map(filename => {
              const isImage = /\.(jpg|jpeg|png|gif|webp)$/i.test(filename);
              return isImage ? (
                <div key={filename} className="relative group">
                  <img
                    src={imageUrls[filename] || getFileUrl(filename)}
                    alt={filename}
                    className="max-h-32 rounded cursor-pointer hover:opacity-90"
                    onClick={(e) => handleFileClick(e, filename)}
                  />
                </div>
              ) : (
                <button
                  key={filename}
                  onClick={(e) => handleFileClick(e, filename)}
                  className="flex items-center gap-1 bg-gray-100 px-2 py-1 rounded hover:bg-gray-200"
                >
                  <DocumentIcon className="h-4 w-4 text-gray-500" />
                  <span className="text-sm text-gray-700">{filename}</span>
                </button>
              );
            })}
          </div>
        )}

        {/* Reactions */}
        <MessageReactions 
          message={message}
          onReactionChange={onReactionChange}
        />

        {/* Thread indicator */}
       
      </div>
    </div>
  );
}; 