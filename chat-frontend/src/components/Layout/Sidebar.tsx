import { useState, useEffect, useCallback } from 'react';
import { Channel, Message } from '../../types/chat';
import { api } from '../../services/api';
import { UserSelector } from '../Chat/UserSelector';
import { socketService } from '../../services/socket';

export interface SidebarProps {
  currentChannel: string;
  onChannelSelect: (channelId: string, channelName: string, isDirectMessage: boolean) => void;
  channels: Channel[];
  messages: Message[];
}

export const Sidebar = ({ currentChannel, onChannelSelect }: SidebarProps) => {
  const currentUserId = localStorage.getItem('userId');
  const [joinedChannels, setJoinedChannels] = useState<Channel[]>([]);
  const [availableChannels, setAvailableChannels] = useState<Channel[]>([]);
  const [showCreateChannel, setShowCreateChannel] = useState(false);
  const [newChannelName, setNewChannelName] = useState('');
  const [error, setError] = useState('');
  const [showUserSelector, setShowUserSelector] = useState(false);
  const [dmChannels, setDmChannels] = useState<Channel[]>([]);
  const [isDMCollapsed, setIsDMCollapsed] = useState(false);
  const [isChannelsCollapsed, setIsChannelsCollapsed] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [workspaces, setWorkspaces] = useState<{ id: string; name: string }[]>([]);
  const [selectedWorkspace, setSelectedWorkspace] = useState<string>('NO_WORKSPACE');

  console.log('Initial availableChannels:', availableChannels);

  const fetchChannels = useCallback(async () => {
    try {
      const channels = await api.channels.listByWorkspace(selectedWorkspace);
      console.log('API Response for channels:', channels);

      const joined = channels.filter((channel: Channel) => channel.isMember);
      const available = channels.filter((channel: Channel) => !channel.isMember);

      setJoinedChannels(joined);
      setAvailableChannels(available);
      console.log('Updated availableChannels:', available);
      console.log('Joined Channels:', joined);
      console.log('Available Channels:', available);

      const dms = joined.filter((channel: Channel) => channel.type === 'dm');
      const regular = joined.filter((channel: Channel) => channel.type !== 'dm' && channel.name !== 'general');
      const general = joined.find((channel: Channel) => channel.name === 'general');

      const sortedRegular = general 
        ? [general, ...regular.sort((a, b) => a.name.localeCompare(b.name))]
        : regular.sort((a, b) => a.name.localeCompare(b.name));

      setDmChannels(dms);
      setJoinedChannels(sortedRegular);
    } catch (error) {
      console.error('Failed to fetch channels:', error);
    }
  }, [selectedWorkspace]);

  // Split into two effects - one for initial fetch and one for socket listeners
  useEffect(() => {
    fetchChannels();
  }, [currentChannel]);

  // Separate effect for socket listeners
  useEffect(() => {
    const handleNewChannel = (channel: Channel) => {
      if (channel.type === 'dm') {
        setDmChannels(prev => {
          const exists = prev.some(c => c.id === channel.id);
          if (exists) return prev;
          
          // Format the channel name before adding it
          const otherMember = channel.members?.find(member => member.id !== currentUserId);
          if (otherMember) {
            channel.name = otherMember.name;
          }
          
          return [...prev, channel];
        });
      } else {
        fetchChannels();
      }
    };

    socketService.onNewChannel(handleNewChannel);

    return () => {
      socketService.offNewChannel(handleNewChannel);
    };
  }, [fetchChannels]);

  const handleJoinChannel = async (channelId: string) => {
    try {
      await api.channels.join(channelId);
      await fetchChannels();
      // Find the channel name from available channels
      const channel = availableChannels.find(c => c.id === channelId);
      if (channel) {
        // Automatically select the joined channel
        onChannelSelect(channelId, channel.name, false);
      }
    } catch (err) {
      console.error('Failed to join channel:', err);
    }
  };

  const handleCreateChannel = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsCreating(true);
    
    try {
      const channel = await api.channels.create({ name: newChannelName });
      setShowCreateChannel(false);
      setNewChannelName('');
      await fetchChannels();
      // Automatically select the new channel
      onChannelSelect(channel.id, channel.name, false);
    } catch (err: any) {
      setError(err.message || 'Failed to create channel');
    } finally {
      setIsCreating(false);
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
    if (channel.type !== 'dm') return channel.name;
    const otherMember = channel.members?.find(member => member.id !== currentUserId);
    return otherMember?.name || channel.name;
  };

  const sortedDMChannels = [...dmChannels].sort((a, b) => {
    const nameA = formatDMChannelName(a);
    const nameB = formatDMChannelName(b);
    return nameA.localeCompare(nameB);
  });

  const hasUnreadMessages = (channel: Channel): boolean => {
    console.log('\nChecking unread status for channel:', {
      channelId: channel.id,
      channelName: channel.name,
      unreadCount: channel.unreadCount
    });
    
    return (channel.unreadCount || 0) > 0;
  };

  const renderChannelName = (channel: Channel) => {
    return (
      <div className="flex items-center gap-2">
        <span>#{channel.name}</span>
        {channel.type === 'private' && (
          <span className="text-xs bg-gray-200 text-gray-600 px-1.5 py-0.5 rounded">private</span>
        )}
      </div>
    );
  };

  const fetchWorkspaces = async () => {
    try {
      const workspaces = await api.workspaces.list();
      setWorkspaces(workspaces.map(ws => ({ id: ws.id, name: ws.name })));
    } catch (error) {
      console.error('Failed to fetch workspaces:', error);
    }
  };

  useEffect(() => {
    fetchWorkspaces();
  }, []);

  useEffect(() => {
    const fetchChannels = async () => {
      try {
        const channels = await api.channels.listByWorkspace(selectedWorkspace !== 'NO_WORKSPACE' ? selectedWorkspace : undefined);
        console.log('API Response for channels:', channels);
  
        const joined = channels.filter((channel: Channel) => channel.isMember);
        const available = channels.filter((channel: Channel) => !channel.isMember);
  
        // Update the state with the filtered channels
        setJoinedChannels(joined);
        setAvailableChannels(available);
      } catch (error) {
        console.error('Failed to fetch channels:', error);
      }
    };
    fetchChannels();
  }, [selectedWorkspace]);

  const handleWorkspaceChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedWorkspace(event.target.value);
  };

  useEffect(() => {
    console.log('Rendering availableChannels:', availableChannels);
  }, [availableChannels]);

  console.log('Workspaces before rendering:', workspaces);
  console.log('Workspaces before rendering dropdown:', workspaces);

  return (
    <div className="w-64 bg-gray-800 text-white flex flex-col h-full">
      <div className="p-4 border-b border-gray-700">
        <h1 className="text-xl font-bold">Chat App</h1>
      </div>

      <div className="flex-1 overflow-y-auto">
        {/* Workspace Selection */}
        <div className="p-4">
          <h2 className="font-bold mb-2">Select Workspace</h2>
          <select title="Select Workspace" value={selectedWorkspace} onChange={handleWorkspaceChange} className="workspace-dropdown p-2 border rounded bg-gray-700 text-white">
            {workspaces.map(workspace => (
              <option key={workspace.id} value={workspace.id} className="bg-gray-800 text-white">{workspace.name}</option>
            ))}
          </select>
        </div>

        {/* Direct Messages */}
        <div className="p-4">
          <div 
            className="flex justify-between items-center mb-2 cursor-pointer"
            onClick={() => setIsDMCollapsed(!isDMCollapsed)}
          >
            <h2 className="font-bold flex items-center">
              <span className="transform transition-transform duration-200 inline-block mr-2">
                {isDMCollapsed ? '▸' : '▾'}
              </span>
              Direct Messages
            </h2>
            <button
              onClick={(e) => {
                e.stopPropagation();
                setShowUserSelector(true);
              }}
              data-testid="new-dm-button"
              className="text-sm text-blue-400 hover:text-blue-300"
            >
              +
            </button>
          </div>
          {!isDMCollapsed && (
            <ul className="space-y-1">
              {sortedDMChannels.map(channel => (
                <li 
                  key={channel.id}
                  className={`p-2 rounded cursor-pointer flex items-center justify-between ${
                    channel.id === currentChannel ? 'bg-gray-700' : 'hover:bg-gray-700'
                  }`}
                  onClick={() => onChannelSelect(channel.id, formatDMChannelName(channel), true)}
                >
                  <div className="flex items-center gap-2">
                    <span>{formatDMChannelName(channel)}</span>
                    {channel.id !== currentChannel && hasUnreadMessages(channel) && (
                      <span className="w-2 h-2 bg-blue-500 rounded-full flex-shrink-0"></span>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Joined Channels */}
        <div className="p-4">
          <div 
            className="flex justify-between items-center mb-2 cursor-pointer"
            onClick={() => setIsChannelsCollapsed(!isChannelsCollapsed)}
          >
            <h2 className="font-bold flex items-center">
              <span className="transform transition-transform duration-200 inline-block mr-2">
                {isChannelsCollapsed ? '▸' : '▾'}
              </span>
              Your Channels
            </h2>
            <button
              data-testid="create-channel-button"
              onClick={(e) => {
                e.stopPropagation();
                setShowCreateChannel(true);
              }}
              className="text-sm text-blue-400 hover:text-blue-300"
            >
              +
            </button>
          </div>
          {!isChannelsCollapsed && (
            <ul className="space-y-1">
              {Array.isArray(joinedChannels) && joinedChannels.map(channel => (
                <li 
                  key={channel.id}
                  data-testid={`channel-${channel.name}`}
                  className={`p-2 rounded cursor-pointer flex items-center justify-between ${
                    channel.id === currentChannel ? 'bg-gray-700' : 'hover:bg-gray-700'
                  }`}
                  onClick={() => onChannelSelect(channel.id, channel.name, false)}
                >
                  <div className="flex items-center gap-2">
                    {renderChannelName(channel)}
                    {channel.id !== currentChannel && hasUnreadMessages(channel) && (
                      <span className="w-2 h-2 bg-blue-500 rounded-full flex-shrink-0"></span>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Available Channels */}
        {availableChannels.length > 0 && (
          <div className="p-4 border-t border-gray-700">
            <h2 className="font-bold mb-2">Available Channels</h2>
            <ul className="space-y-1">
              {availableChannels.map(channel => (
                <li 
                  key={channel.id}
                  data-testid={`channel-${channel.name}`}
                  className="p-2 rounded hover:bg-gray-700 cursor-pointer flex justify-between items-center"
                >
                  #{channel.name}
                  <button
                    data-testid={`join-channel-button-${channel.id}`}
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
      </div>

      {/* Keep modals outside the scrollable area */}
      {showCreateChannel && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-80 relative z-50">
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
                  disabled={isCreating}
                >
                  {isCreating ? 'Creating...' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
      
      {showUserSelector && (
        <UserSelector
          onClose={() => setShowUserSelector(false)}
          onUserSelect={handleStartDM}
        />
      )}
    </div>
  );
}; 