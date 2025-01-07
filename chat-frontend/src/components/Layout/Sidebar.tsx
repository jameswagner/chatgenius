import { useState, useEffect } from 'react';
import { Channel } from '../../types/chat';
import { api } from '../../services/api';
import { UserSelector } from '../Chat/UserSelector';

interface SidebarProps {
  currentChannel: string;
  onChannelSelect: (channelId: string, channelName: string, isDirectMessage: boolean) => void;
}

export const Sidebar = ({ currentChannel, onChannelSelect }: SidebarProps) => {
  const [joinedChannels, setJoinedChannels] = useState<Channel[]>([]);
  const [availableChannels, setAvailableChannels] = useState<Channel[]>([]);
  const [showCreateChannel, setShowCreateChannel] = useState(false);
  const [newChannelName, setNewChannelName] = useState('');
  const [error, setError] = useState('');
  const [showUserSelector, setShowUserSelector] = useState(false);
  const [dmChannels, setDmChannels] = useState<Channel[]>([]);

  const fetchChannels = async () => {
    try {
      const [joined, available] = await Promise.all([
        api.channels.list(),
        api.channels.available()
      ]);

      console.log('All joined channels:', joined.map(c => ({ name: c.name, type: c.type }))); // More detailed debug

      // Separate DM channels from regular channels
      const dms = joined.filter(channel => {
        console.log(`Channel ${channel.name} has type: ${channel.type}`); // Debug each channel's type
        return channel.type === 'dm';
      });
      const regular = joined.filter(channel => channel.type !== 'dm' && channel.name !== 'general');
      const general = joined.find(channel => channel.name === 'general');

      console.log('DM channels:', dms.map(c => ({ name: c.name, type: c.type })));
      console.log('Regular channels:', regular.map(c => ({ name: c.name, type: c.type })));

      // Sort regular channels
      const sortedRegular = general 
        ? [general, ...regular.sort((a, b) => a.name.localeCompare(b.name))]
        : regular.sort((a, b) => a.name.localeCompare(b.name));

      setJoinedChannels(sortedRegular);
      setDmChannels(dms);
      setAvailableChannels(available);

      // If no channel is selected, select general
      if (!currentChannel && sortedRegular.length > 0) {
        const generalChannel = sortedRegular.find(c => c.name === 'general');
        if (generalChannel) {
          onChannelSelect(generalChannel.id, generalChannel.name, false);
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

  const handleCreateChannel = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    
    try {
      await api.channels.create({ name: newChannelName });
      setNewChannelName('');
      setShowCreateChannel(false);
      await fetchChannels();
    } catch (err: any) {
      setError(err.message || 'Failed to create channel');
    }
  };

  const handleStartDM = async (userId: string, userName: string) => {
    try {
      console.log('Starting DM with type: dm'); // Debug log
      const channel = await api.channels.create({
        name: `dm-${crypto.randomUUID()}`,
        type: 'dm',  // Make sure this is being set
        otherUserId: userId
      });
      console.log('Created channel:', channel); // Debug log
      await fetchChannels();
      onChannelSelect(channel.id, userName, true);
      setShowUserSelector(false);
    } catch (err) {
      console.error('Failed to create DM:', err);
    }
  };

  const formatDMChannelName = (channel: Channel) => {
    console.log('Formatting DM channel:', channel); // Debug log
    if (channel.type !== 'dm') return channel.name;
    
    // Find the other user in the members list
    const otherMember = channel.members?.find(member => member.id !== currentUserId);
    console.log('Other member found:', otherMember); // Debug log
    return otherMember?.name || channel.name;
  };

  const currentUserId = localStorage.getItem('userId');

  return (
    <div className="w-64 bg-gray-800 text-white flex flex-col">
      <div className="p-4 border-b border-gray-700">
        <h1 className="text-xl font-bold">Chat App</h1>
      </div>

      {/* Direct Messages */}
      <div className="p-4">
        <div className="flex justify-between items-center mb-2">
          <h2 className="font-bold">Direct Messages</h2>
          <button
            onClick={() => setShowUserSelector(true)}
            className="text-sm text-blue-400 hover:text-blue-300"
          >
            +
          </button>
        </div>
        <ul className="space-y-1">
          {dmChannels.map(channel => (
            <li 
              key={channel.id}
              className={`p-2 rounded cursor-pointer ${
                channel.id === currentChannel ? 'bg-gray-700' : 'hover:bg-gray-700'
              }`}
              onClick={() => onChannelSelect(channel.id, formatDMChannelName(channel), channel.type === 'dm')}
            >
              {formatDMChannelName(channel)}
            </li>
          ))}
        </ul>
      </div>

      {/* Joined Channels */}
      <div className="p-4">
        <div className="flex justify-between items-center mb-2">
          <h2 className="font-bold">Your Channels</h2>
          <button
            onClick={() => setShowCreateChannel(true)}
            className="text-sm text-blue-400 hover:text-blue-300"
          >
            +
          </button>
        </div>
        <ul className="space-y-1">
          {joinedChannels.map(channel => (
            <li 
              key={channel.id}
              className={`flex justify-between items-center p-2 rounded cursor-pointer ${
                channel.id === currentChannel ? 'bg-gray-700' : 'hover:bg-gray-700'
              }`}
            >
              <span 
                onClick={() => onChannelSelect(channel.id, channel.name, false)}
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

      {/* Create Channel Modal */}
      {showCreateChannel && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center">
          <div className="bg-white rounded-lg p-6 w-80">
            <h3 className="text-lg font-bold text-gray-900 mb-4">Create Channel</h3>
            {error && (
              <div className="mb-4 text-red-500 text-sm">{error}</div>
            )}
            <form onSubmit={handleCreateChannel}>
              <input
                type="text"
                value={newChannelName}
                onChange={(e) => setNewChannelName(e.target.value)}
                placeholder="Channel name"
                className="w-full p-2 border rounded mb-4 text-gray-900"
                required
              />
              <div className="flex justify-end space-x-2">
                <button
                  type="button"
                  onClick={() => {
                    setShowCreateChannel(false);
                    setNewChannelName('');
                    setError('');
                  }}
                  className="px-4 py-2 text-gray-600 hover:text-gray-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
                >
                  Create
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

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

      {/* User Selector Modal */}
      {showUserSelector && (
        <UserSelector
          onClose={() => setShowUserSelector(false)}
          onUserSelect={handleStartDM}
        />
      )}
    </div>
  );
}; 