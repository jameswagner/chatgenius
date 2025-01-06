import { useState, useEffect } from 'react';
import { api } from '../../services/api';

interface Channel {
  id: string;
  name: string;
  type: string;
}

interface ChannelBrowserProps {
  onClose: () => void;
  onJoinChannel: (channelId: string) => Promise<void>;
}

export const ChannelBrowser = ({ onClose, onJoinChannel }: ChannelBrowserProps) => {
  const [channels, setChannels] = useState<Channel[]>([]);

  useEffect(() => {
    const fetchChannels = async () => {
      const data = await api.channels.list();
      setChannels(data);
    };
    fetchChannels();
  }, []);

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center">
      <div className="bg-white rounded-lg p-6 w-96">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-bold text-gray-900">Browse Channels</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-700">✕</button>
        </div>
        <div className="space-y-2">
          {channels.map(channel => (
            <div 
              key={channel.id}
              className="p-2 hover:bg-gray-100 rounded cursor-pointer flex justify-between items-center"
              onClick={() => onJoinChannel(channel.id)}
            >
              <span className="text-gray-900">#{channel.name}</span>
              <button className="text-purple-600 hover:text-purple-700">Join</button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}; 