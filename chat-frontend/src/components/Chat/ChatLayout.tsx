import { useState, useEffect } from 'react';
import { Sidebar } from '../Layout/Sidebar';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import { api } from '../../services/api';
import { Message } from '../../types/chat';
import { useNavigate } from 'react-router-dom';

export const ChatLayout = () => {
  const [currentChannel, setCurrentChannel] = useState<string>('general');
  const [messages, setMessages] = useState<Message[]>([]);
  const navigate = useNavigate();

  // Fetch messages when channel changes
  useEffect(() => {
    const fetchMessages = async () => {
      try {
        const data = await api.messages.list(currentChannel);
        setMessages(data);
      } catch (err) {
        console.error('Failed to fetch messages:', err);
      }
    };
    fetchMessages();

    // Set up polling for new messages
    const interval = setInterval(fetchMessages, 3000);
    return () => clearInterval(interval);
  }, [currentChannel]);

  const handleSendMessage = async (content: string, threadId?: string) => {
    try {
      const message = await api.messages.create(currentChannel, { 
        content,
        threadId 
      });
      setMessages(prev => [...prev, message]);
    } catch (error) {
      console.error('Failed to send message:', error);
    }
  };

  const handleChannelSelect = (channelId: string) => {
    setCurrentChannel(channelId);
    setMessages([]);
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('userId');
    navigate('/auth');
  };

  return (
    <div className="flex h-screen">
      <Sidebar onChannelSelect={handleChannelSelect} />
      <div className="flex-1 flex flex-col">
        <div className="h-12 flex items-center justify-between px-6 border-b border-gray-200">
          <h2 className="font-bold"># {currentChannel}</h2>
          <button
            onClick={handleLogout}
            className="text-gray-600 hover:text-gray-900"
          >
            Logout
          </button>
        </div>

        <MessageList 
          channelId={currentChannel}
          messages={messages}
          setMessages={setMessages}
        />
        <MessageInput 
          channelId={currentChannel}
          onSendMessage={handleSendMessage}
        />
      </div>
    </div>
  );
}; 