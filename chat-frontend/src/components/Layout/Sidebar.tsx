import { useState, useEffect } from 'react';
import { Channel } from '../../types/chat';
import { api } from '../../services/api';

interface SidebarProps {
  currentChannel: string;
  onChannelSelect: (channelId: string, channelName: string) => void;
}

export const Sidebar = ({ currentChannel, onChannelSelect }: SidebarProps) => {
  const [joinedChannels, setJoinedChannels] = useState<Channel[]>([]);
  const [availableChannels, setAvailableChannels] = useState<Channel[]>([]);
  const [showCreateChannel, setShowCreateChannel] = useState(false);
  const [newChannelName, setNewChannelName] = useState('');

  const fetchChannels = async () => {
    try {
      const [joined, available] = await Promise.all([
        api.channels.list(),
        api.channels.available()
      ]);

      // Sort channels to ensure 'general' appears first
      const sortedJoined = [...joined].sort((a, b) => {
        if (a.name === 'general') return -1;
        if (b.name === 'general') return 1;
        return a.name.localeCompare(b.name);
      });

      setJoinedChannels(sortedJoined);
      setAvailableChannels(available);

      // If no channel is selected, select general
      if (!currentChannel && sortedJoined.length > 0) {
        const generalChannel = sortedJoined.find(c => c.name === 'general');
        if (generalChannel) {
          onChannelSelect(generalChannel.id, generalChannel.name);
        }
      }
    } catch (err) {
      console.error('Failed to fetch channels:', err);
    }
  };

  useEffect(() => {
    fetchChannels();
  }, []);

  const handleJoinChannel = async (channelId: string) => {
    try {
      await api.channels.join(channelId);
      await fetchChannels();
    } catch (err) {
      console.error('Failed to join channel:', err);
    }
  };

  const handleLeaveChannel = async (channelId: string) => {
    try {
      await api.channels.leave(channelId);
      await fetchChannels();
    } catch (err) {
      console.error('Failed to leave channel:', err);
    }
  };

  return (
    <div className="w-64 bg-gray-800 text-white flex flex-col">
      <div className="p-4 border-b border-gray-700">
        <h1 className="text-xl font-bold">Chat App</h1>
      </div>

      {/* Joined Channels */}
      <div className="p-4">
        <h2 className="font-bold mb-2">Your Channels</h2>
        <ul className="space-y-1">
          {joinedChannels.map(channel => (
            <li 
              key={channel.id}
              className={`flex justify-between items-center p-2 rounded cursor-pointer ${
                channel.id === currentChannel ? 'bg-gray-700' : 'hover:bg-gray-700'
              }`}
            >
              <span 
                onClick={() => onChannelSelect(channel.id, channel.name)}
                className="flex-1"
              >
                # {channel.name}
              </span>
              {channel.name !== 'general' && (
                <button
                  onClick={() => handleLeaveChannel(channel.id)}
                  className="text-sm text-gray-400 hover:text-white"
                >
                  Leave
                </button>
              )}
            </li>
          ))}
        </ul>
      </div>

      {/* Available Channels */}
      {availableChannels.length > 0 && (
        <div className="p-4 border-t border-gray-700">
          <h2 className="font-bold mb-2">Available Channels</h2>
          <ul className="space-y-1">
            {availableChannels.map(channel => (
              <li 
                key={channel.id}
                className="flex justify-between items-center p-2 rounded hover:bg-gray-700"
              >
                <span># {channel.name}</span>
                <button
                  onClick={() => handleJoinChannel(channel.id)}
                  className="text-sm text-blue-400 hover:text-blue-300"
                >
                  Join
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Create Channel button and form */}
      {/* ... existing create channel UI ... */}
    </div>
  );
}; 