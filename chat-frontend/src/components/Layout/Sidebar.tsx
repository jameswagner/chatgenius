import { useState, useEffect } from 'react';
import { api, ApiError } from '../../services/api';
import { ChannelBrowser } from '../Chat/ChannelBrowser';

interface Channel {
  id: string;
  name: string;
  type: string;
}

interface SidebarProps {
  onChannelSelect: (channelId: string) => void;
}

export const Sidebar = ({ onChannelSelect }: SidebarProps) => {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [isCreating, setIsCreating] = useState(false);
  const [showBrowser, setShowBrowser] = useState(false);
  const [newChannelName, setNewChannelName] = useState('');

  useEffect(() => {
    const fetchChannels = async () => {
      try {
        const data = await api.channels.list();
        setChannels(data);
      } catch (err) {
        console.error('Failed to fetch channels:', err);
      }
    };
    fetchChannels();
  }, []);

  const handleCreateChannel = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const channel = await api.channels.create({
        name: newChannelName.toLowerCase().replace(/\s+/g, '-'),
        type: 'public'
      });
      setChannels(prev => [...prev, channel]);
      setNewChannelName('');
      setIsCreating(false);
    } catch (err) {
      if (err instanceof ApiError && err.message.includes('already exists')) {
        alert('A channel with this name already exists');
      } else {
        console.error('Failed to create channel:', err);
      }
    }
  };

  return (
    <div className="w-64 bg-purple-800 text-purple-100 flex flex-col">
      <div className="p-4 border-b border-purple-700">
        <h1 className="text-xl font-bold">Chat App</h1>
      </div>
      
      <div className="p-4">
        <div className="flex justify-between items-center mb-4">
          <h2 className="font-semibold">Channels</h2>
          <div className="flex gap-2">
            <button 
              onClick={() => setShowBrowser(true)}
              className="text-sm hover:text-white"
              title="Browse Channels"
            >
              🔍
            </button>
            <button 
              onClick={() => setIsCreating(true)}
              className="text-sm hover:text-white"
              title="Create Channel"
            >
              +
            </button>
          </div>
        </div>

        {isCreating && (
          <form onSubmit={handleCreateChannel} className="mb-4">
            <input
              type="text"
              value={newChannelName}
              onChange={(e) => setNewChannelName(e.target.value)}
              placeholder="channel-name"
              className="w-full p-2 rounded bg-purple-900 text-white mb-2"
            />
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setIsCreating(false)}
                className="text-sm hover:text-white"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="bg-purple-600 px-3 py-1 rounded text-sm hover:bg-purple-500"
              >
                Create
              </button>
            </div>
          </form>
        )}

        <ul className="space-y-1">
          {channels.map(channel => (
            <li 
              key={channel.id}
              onClick={() => onChannelSelect(channel.name)}
              className="cursor-pointer hover:bg-purple-700 px-2 py-1 rounded"
            >
              # {channel.name}
            </li>
          ))}
        </ul>
      </div>

      {showBrowser && (
        <ChannelBrowser 
          onClose={() => setShowBrowser(false)}
          onJoinChannel={async (channelId) => {
            await api.channels.join(channelId);
            const data = await api.channels.list();
            setChannels(data);
            setShowBrowser(false);
          }}
        />
      )}
    </div>
  );
}; 