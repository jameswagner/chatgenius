import { useState } from 'react';
import { Message } from '../../types/chat';
import { api } from '../../services/api';
import data from '@emoji-mart/data';
import Picker from '@emoji-mart/react';
import { ReactionTooltip } from './ReactionTooltip';

interface MessageReactionsProps {
  message: Message;
  onReactionChange: () => void;
}

export const MessageReactions = ({ message, onReactionChange }: MessageReactionsProps) => {
  const [showPicker, setShowPicker] = useState(false);
  const [hoveredEmoji, setHoveredEmoji] = useState<string | null>(null);
  const currentUserId = localStorage.getItem('userId');

  // Mock user names - in real app, you'd want to get these from your user store
  const userNames: { [key: string]: string } = {
    [message.userId]: message.user?.name || 'Unknown',
    // ... other users
  };

  const handleAddReaction = async (emoji: string) => {
    try {
      await api.reactions.add(message.id, emoji);
      onReactionChange();
      setShowPicker(false);
    } catch (err) {
      console.error('Failed to add reaction:', err);
    }
  };

  const handleRemoveReaction = async (emoji: string) => {
    try {
      await api.reactions.remove(message.id, emoji);
      onReactionChange();
    } catch (err) {
      console.error('Failed to remove reaction:', err);
    }
  };

  const hasUserReacted = (emoji: string) => {
    return message.reactions?.[emoji]?.includes(currentUserId || '');
  };

  return (
    <div className="relative">
      <div className="flex flex-wrap gap-1 mt-1">
        {Object.entries(message.reactions || {}).map(([emoji, users]) => (
          <button
            key={emoji}
            onClick={() => hasUserReacted(emoji) ? handleRemoveReaction(emoji) : handleAddReaction(emoji)}
            onMouseEnter={() => setHoveredEmoji(emoji)}
            onMouseLeave={() => setHoveredEmoji(null)}
            className={`relative px-2 py-0.5 rounded text-sm ${
              hasUserReacted(emoji) 
                ? 'bg-blue-100 hover:bg-blue-200' 
                : 'bg-gray-100 hover:bg-gray-200'
            }`}
          >
            {emoji} {users.length}
            {hoveredEmoji === emoji && (
              <ReactionTooltip 
                userIds={users}
                currentUserId={currentUserId}
                userNames={userNames}
              />
            )}
          </button>
        ))}
        <button
          onClick={() => setShowPicker(!showPicker)}
          className="px-2 py-0.5 rounded text-sm bg-gray-100 hover:bg-gray-200"
        >
          +
        </button>
      </div>

      {showPicker && (
        <div className="absolute bottom-full mb-2 z-10">
          <Picker
            data={data}
            onEmojiSelect={(emoji: any) => handleAddReaction(emoji.native)}
            theme="light"
            previewPosition="none"
            skinTonePosition="none"
          />
        </div>
      )}
    </div>
  );
}; 