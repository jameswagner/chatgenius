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
  const [currentChannelName, setCurrentChannelName] = useState<string>('general');
  const [currentChannelType, setCurrentChannelType] = useState<string>('public');
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
        console.log('Received new message through WebSocket:', message); // Debug
        // If it's a thread reply, update the parent message's thread count
        if (message.threadId && message.threadId !== message.id) {
          setMessages(prev => prev.map(m => {
            if (m.id === message.threadId) {
              return {
                ...m,
                replyCount: (m.replyCount || 0) + 1
              };
            }
            return m;
          }));
        }
        // Add the new message to the list
        setMessages(prev => {
          console.log('Current messages:', prev); // Debug
          console.log('Adding new message:', message); // Debug
          return [...prev, message];
        });
      }
    };

    const handleReaction = (message: Message) => {
      if (message.channelId === currentChannel) {
        // Update the message in the messages array
        setMessages(prev => prev.map(m => 
          m.id === message.id ? message : m
        ));
      }
    };

    socketService.onNewMessage(handleNewMessage);
    socketService.on('message.reaction', handleReaction);

    return () => {
      socketService.leaveChannel(currentChannel);
      socketService.offNewMessage(handleNewMessage);
      socketService.off('message.reaction', handleReaction);
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

  const handleSendMessage = async (content: string, files: File[], threadId?: string) => {
    try {
      const formData = new FormData();
      formData.append('content', content);
      if (threadId) {
        formData.append('thread_id', threadId);
      }
      files.forEach(file => {
        console.log('Appending file:', file.name, file.size); // Debug files being sent
        formData.append('files', file);
      });

      console.log('FormData entries:');
      for (let pair of formData.entries()) {
        console.log(pair[0], pair[1]); // Debug FormData contents
      }

      const response = await api.messages.create(currentChannel, formData);
      console.log('Message created with response:', response); // Debug server response
    } catch (error) {
      console.error('Failed to send message:', error);
    }
  };

  const handleChannelSelect = (channelId: string, channelName: string, isDirectMessage: boolean) => {
    setCurrentChannel(channelId);
    setCurrentChannelName(channelName);
    setCurrentChannelType(isDirectMessage ? 'dm' : 'public');
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
          <h2 className="text-xl font-bold">
            {currentChannelType !== 'dm' ? `#${currentChannelName}` : currentChannelName}
          </h2>
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
          currentChannelName={currentChannelName}
        />
        <MessageInput 
          channelId={currentChannel}
          onSendMessage={handleSendMessage}
          currentChannelName={currentChannelName}
        />
      </div>
    </div>
  );
}; 