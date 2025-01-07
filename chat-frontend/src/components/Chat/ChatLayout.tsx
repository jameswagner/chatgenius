import { useState, useEffect } from 'react';
import { Sidebar } from '../Layout/Sidebar';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import { api } from '../../services/api';
import { socketService } from '../../services/socket';
import { Message } from '../../types/chat';
import { useNavigate } from 'react-router-dom';

export const ChatLayout = () => {
  const [currentChannel, setCurrentChannel] = useState<string>('general');
  const [messages, setMessages] = useState<Message[]>([]);
  const navigate = useNavigate();

  // Connect to WebSocket when component mounts
  useEffect(() => {
    socketService.connect();
    return () => socketService.disconnect();
  }, []);

  // Join channel and listen for messages
  useEffect(() => {
    socketService.joinChannel(currentChannel);
    
    const handleNewMessage = (message: Message) => {
      if (message.channelId === currentChannel) {
        setMessages(prev => [...prev, message]);
      }
    };

    socketService.onNewMessage(handleNewMessage);

    return () => {
      socketService.leaveChannel(currentChannel);
      socketService.offNewMessage(handleNewMessage);
    };
  }, [currentChannel]);

  // Initial messages load
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
  }, [currentChannel]);

  const handleSendMessage = async (content: string, threadId?: string) => {
    try {
      await api.messages.create(currentChannel, { content, threadId });
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
    navigate('/login');
  };

  return (
    <div className="flex h-screen">
      <Sidebar 
        currentChannel={currentChannel}
        onChannelSelect={handleChannelSelect}
      />
      <div className="flex-1 flex flex-col">
        <div className="p-4 border-b flex justify-between items-center">
          <h2 className="text-xl font-bold">#{currentChannel}</h2>
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