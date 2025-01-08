import { useState, useEffect } from 'react';
import { Sidebar } from '../Layout/Sidebar';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import { api } from '../../services/api';
import { socketService } from '../../services/socket';
import { Message, Channel } from '../../types/chat';
import { useNavigate } from 'react-router-dom';
import { StatusSelector } from './StatusSelector';
import { SearchBar } from './SearchBar';
import { ChatMessage } from './ChatMessage';

interface GroupedSearchResults {
  dms: { [channelId: string]: Message[] };
  memberChannels: { [channelId: string]: Message[] };
  otherChannels: { [channelId: string]: Message[] };
}

// Move this outside the component
const getChannelDisplayName = (channel: Channel, isDm: boolean) => {
  if (isDm) {
    const currentUserId = localStorage.getItem('userId');
    const otherMember = channel.members?.find(member => member.id !== currentUserId);
    return otherMember?.name || channel.name;
  }
  return channel.name;
};

export const ChatLayout = () => {
  const [currentChannel, setCurrentChannel] = useState<string | null>(() => localStorage.getItem('currentChannel'));
  const [currentChannelName, setCurrentChannelName] = useState<string>(() => localStorage.getItem('currentChannelName') || '');
  const [currentChannelType, setCurrentChannelType] = useState<string>(() => localStorage.getItem('currentChannelType') || 'public');
  const [messages, setMessages] = useState<Message[]>([]);
  const [channels, setChannels] = useState<Channel[]>([]);
  const [searchResults, setSearchResults] = useState<Message[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [collapsedChannels, setCollapsedChannels] = useState<Set<string>>(new Set());
  const [channelNames, setChannelNames] = useState<{ [channelId: string]: string }>({});
  const navigate = useNavigate();

  // Single WebSocket connection and event listeners
  useEffect(() => {
    socketService.connect();

    // Listen for new channels
    socketService.on('channel.new', (channel: Channel) => {
      if (!channel) return; // Guard against undefined channel

      setChannels(prevChannels => {
        // Guard against undefined prevChannels
        if (!prevChannels) return [channel];
        
        // Check if channel already exists
        if (prevChannels.some(c => c?.id === channel.id)) {
          return prevChannels;
        }
        return [...prevChannels, channel];
      });
    });

    // Listen for status updates
    socketService.on('user.status', (data: { userId: string; status: string }) => {
      // Update status in existing messages
      setMessages(prevMessages => 
        prevMessages.map(msg => {
          if (msg.userId === data.userId && msg.user) {
            return {
              ...msg,
              user: {
                ...msg.user,
                status: data.status
              }
            };
          }
          return msg;
        })
      );

      // Also update status in search results if any
      setSearchResults(prevResults =>
        prevResults.map(msg => {
          if (msg.userId === data.userId && msg.user) {
            return {
              ...msg,
              user: {
                ...msg.user,
                status: data.status
              }
            };
          }
          return msg;
        })
      );
    });

    return () => {
      socketService.off('channel.new', () => {});
      socketService.off('user.status', () => {});
      socketService.disconnect();
    };
  }, []);

  // Join channel and listen for messages
  useEffect(() => {
    if (currentChannel) {
      socketService.joinChannel(currentChannel);
      
      const handleNewMessage = (message: Message) => {
        if (message.channelId === currentChannel) {
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

      const handleMessageUpdate = (message: Message) => {
        if (message.channelId === currentChannel) {
          setMessages(prev => prev.map(m => 
            m.id === message.id ? { ...message, isEdited: true, user: m.user, reactions: message.reactions || m.reactions } : m
          ));
        }
      };

      socketService.onNewMessage(handleNewMessage);
      socketService.on('message.reaction', handleReaction);
      socketService.onMessageUpdate(handleMessageUpdate);

      return () => {
        socketService.leaveChannel(currentChannel);
        socketService.offNewMessage(handleNewMessage);
        socketService.off('message.reaction', handleReaction);
        socketService.offMessageUpdate(handleMessageUpdate);
      };
    }
  }, [currentChannel]);

  // Initial messages load
  useEffect(() => {
    if (currentChannel) {
      const fetchMessages = async () => {
        try {
          const data = await api.messages.list(currentChannel);
          if (Array.isArray(data)) {
            setMessages(data);
          }
        } catch (err) {
          console.error('Failed to fetch messages:', err);
        }
      };
      fetchMessages();
    }
  }, [currentChannel]);

  const handleSendMessage = async (content: string, files: File[], threadId?: string) => {
    if (!currentChannel) return;
    
    try {
      const formData = new FormData();
      formData.append('content', content);
      if (threadId) {
        formData.append('thread_id', threadId);
      }
      
      files.forEach(file => {
        formData.append('files', file);
      });

      await api.messages.create(currentChannel, formData);
    } catch (error) {
      console.error('Failed to send message:', error);
    }
  };

  // Update WebSocket message handler to ensure attachments is always an array
  useEffect(() => {
    socketService.on('message.new', (message: Message) => {
      setMessages(prevMessages => [...prevMessages, {
        ...message,
        attachments: message.attachments || []
      }]);
    });

    return () => {
      socketService.off('message.new', () => {});
    };
  }, []);

  const handleChannelSelect = (channelId: string, channelName: string, isDirectMessage: boolean) => {
    setCurrentChannel(channelId);
    setCurrentChannelName(channelName);
    setCurrentChannelType(isDirectMessage ? 'dm' : 'public');
    setMessages([]);

    // Persist channel selection
    localStorage.setItem('currentChannel', channelId);
    localStorage.setItem('currentChannelName', channelName);
    localStorage.setItem('currentChannelType', isDirectMessage ? 'dm' : 'public');
  };

  const handleLogout = async () => {
    try {
      await api.auth.logout();
    } catch (error) {
      console.error('Error during logout:', error);
    } finally {
      localStorage.removeItem('token');
      localStorage.removeItem('userId');
      localStorage.removeItem('currentChannel');
      localStorage.removeItem('currentChannelName');
      localStorage.removeItem('currentChannelType');
      navigate('/auth');
    }
  };

  const handleSearchResults = async (messages: Message[]) => {
    // Ensure we have channels loaded
    if (channels.length === 0) {
      try {
        const fetchedChannels = await api.channels.list();
        setChannels(fetchedChannels);
      } catch (err) {
        console.error('Failed to fetch channels:', err);
      }
    }
    
    setSearchResults(messages);
    setIsSearching(true);
  };

  const organizeSearchResults = (messages: Message[]): GroupedSearchResults => {
    console.log('Organizing search results with channels:', channels);
    
    const grouped: GroupedSearchResults = {
      dms: {},
      memberChannels: {},
      otherChannels: {}
    };

    messages.forEach(message => {
      const channel = channels.find(c => c.id === message.channelId);
      console.log('Found channel for message:', { messageChannelId: message.channelId, channel });
      
      if (!channel) {
        console.log('No channel found for message:', message);
        return;
      }

      // Determine if the current user is a member of this channel
      const currentUserId = localStorage.getItem('userId');
      const isMember = channel.members?.some(member => member.id === currentUserId);

      // Determine which group to use
      let targetGroup;
      if (channel.type === 'dm') {
        targetGroup = grouped.dms;
      } else if (isMember) {
        targetGroup = grouped.memberChannels;
      } else {
        targetGroup = grouped.otherChannels;
      }

      if (!targetGroup[channel.id]) {
        targetGroup[channel.id] = [];
        const displayName = getChannelDisplayName(channel, channel.type === 'dm');
        channelNames[channel.id] = displayName;
      }
      targetGroup[channel.id].push(message);
    });

    return grouped;
  };

  // Update channelNames when search results change
  useEffect(() => {
    if (searchResults.length > 0) {
      const newChannelNames: { [key: string]: string } = {};
      searchResults.forEach(message => {
        const channel = channels.find(c => c.id === message.channelId);
        if (channel && !newChannelNames[channel.id]) {
          newChannelNames[channel.id] = getChannelDisplayName(channel, channel.type === 'dm');
        }
      });
      setChannelNames(newChannelNames);
    }
  }, [searchResults, channels]);

  const handleSearchResultClick = (channelId: string, channelName: string, isDirectMessage: boolean, messageId: string) => {
    // First switch to the channel
    handleChannelSelect(channelId, channelName, isDirectMessage);
    setIsSearching(false);
    
    // Create a function to attempt scrolling
    const scrollToMessage = () => {
      const messageElement = document.getElementById(`message-${messageId}`);
      if (messageElement) {
        messageElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
        messageElement.classList.add('bg-yellow-50');
        setTimeout(() => messageElement.classList.remove('bg-yellow-50'), 2000);
        return true;
      }
      return false;
    };

    // Try scrolling multiple times over a few seconds
    let attempts = 0;
    const maxAttempts = 10;
    const attemptInterval = setInterval(() => {
      if (scrollToMessage() || attempts >= maxAttempts) {
        clearInterval(attemptInterval);
      }
      attempts++;
    }, 500);
  };

  return (
    <div className="flex h-screen">
      <Sidebar 
        currentChannel={currentChannel || ''}
        onChannelSelect={handleChannelSelect}
        channels={channels}
      />
      <div className="flex-1 flex flex-col">
        <div className="p-4 border-b flex justify-between items-center bg-white">
          <div className="flex-1 max-w-2xl">
            <SearchBar onResultsFound={handleSearchResults} />
          </div>
          <div className="flex items-center gap-4 ml-4">
            <StatusSelector />
            <button
              onClick={handleLogout}
              className="text-gray-600 hover:text-gray-900"
            >
              Logout
            </button>
          </div>
        </div>

        {currentChannel ? (
          <>
            {isSearching ? (
              <div className="flex-1 overflow-y-auto p-4">
                <div className="mb-4 flex justify-between items-center">
                  <h2 className="text-lg font-semibold">
                    Search Results ({searchResults.length})
                  </h2>
                  <button
                    onClick={() => setIsSearching(false)}
                    className="text-blue-500 hover:text-blue-600"
                  >
                    Back to Chat
                  </button>
                </div>

                {(() => {
                  const grouped = organizeSearchResults(searchResults);
                  console.log(grouped);
                  console.log(searchResults);
                  return (
                    <>
                      {/* DMs */}
                      {Object.entries(grouped.dms).length > 0 && (
                        <div className="mb-6">
                          <h3 className="text-md font-semibold mb-2">Direct Messages</h3>
                          {Object.entries(grouped.dms).map(([channelId, messages]) => (
                            <div key={channelId} className="mb-4">
                              <div 
                                className="flex items-center cursor-pointer hover:bg-gray-50 p-2 rounded"
                                onClick={() => setCollapsedChannels(prev => {
                                  const next = new Set(prev);
                                  if (next.has(channelId)) {
                                    next.delete(channelId);
                                  } else {
                                    next.add(channelId);
                                  }
                                  return next;
                                })}
                              >
                                <span className="transform transition-transform duration-200 inline-block mr-2">
                                  {collapsedChannels.has(channelId) ? '▸' : '▾'}
                                </span>
                                <span className="font-medium">{channelNames[channelId]}</span>
                                <span className="text-gray-500 text-sm ml-2">
                                  ({messages.length} results)
                                </span>
                              </div>
                              {!collapsedChannels.has(channelId) && (
                                <div className="ml-6">
                                  {messages.map(message => (
                                    <ChatMessage
                                      key={message.id}
                                      message={message}
                                      onReactionChange={() => {}}
                                      isReply={false}
                                      isHighlighted={false}
                                      onClick={() => {
                                        const channel = channels.find(c => c.id === message.channelId);
                                        if (channel) {
                                          handleSearchResultClick(
                                            message.channelId,
                                            channelNames[message.channelId],
                                            channel.type === 'dm',
                                            message.id
                                          );
                                        }
                                      }}
                                    />
                                  ))}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Member Channels */}
                      {Object.entries(grouped.memberChannels).length > 0 && (
                        <div className="mb-6">
                          <h3 className="text-md font-semibold mb-2">Channels</h3>
                          {Object.entries(grouped.memberChannels).map(([channelId, messages]) => (
                            <div key={channelId} className="mb-4">
                              <div 
                                className="flex items-center cursor-pointer hover:bg-gray-50 p-2 rounded"
                                onClick={() => setCollapsedChannels(prev => {
                                  const next = new Set(prev);
                                  if (next.has(channelId)) {
                                    next.delete(channelId);
                                  } else {
                                    next.add(channelId);
                                  }
                                  return next;
                                })}
                              >
                                <span className="transform transition-transform duration-200 inline-block mr-2">
                                  {collapsedChannels.has(channelId) ? '▸' : '▾'}
                                </span>
                                <span className="font-medium">#{channelNames[channelId]}</span>
                                <span className="text-gray-500 text-sm ml-2">
                                  ({messages.length} results)
                                </span>
                              </div>
                              {!collapsedChannels.has(channelId) && (
                                <div className="ml-6">
                                  {messages.map(message => (
                                    <ChatMessage
                                      key={message.id}
                                      message={message}
                                      onReactionChange={() => {}}
                                      isReply={false}
                                      isHighlighted={false}
                                      onClick={() => {
                                        const channel = channels.find(c => c.id === message.channelId);
                                        if (channel) {
                                          handleSearchResultClick(
                                            message.channelId,
                                            channelNames[message.channelId],
                                            channel.type === 'dm',
                                            message.id
                                          );
                                        }
                                      }}
                                    />
                                  ))}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Other Channels */}
                      {Object.entries(grouped.otherChannels).length > 0 && (
                        <div className="mb-6">
                          <h3 className="text-md font-semibold mb-2">Other Channels</h3>
                          {Object.entries(grouped.otherChannels).map(([channelId, messages]) => (
                            <div key={channelId} className="mb-4">
                              <div 
                                className="flex items-center cursor-pointer hover:bg-gray-50 p-2 rounded"
                                onClick={() => setCollapsedChannels(prev => {
                                  const next = new Set(prev);
                                  if (next.has(channelId)) {
                                    next.delete(channelId);
                                  } else {
                                    next.add(channelId);
                                  }
                                  return next;
                                })}
                              >
                                <span className="transform transition-transform duration-200 inline-block mr-2">
                                  {collapsedChannels.has(channelId) ? '▸' : '▾'}
                                </span>
                                <span className="font-medium">#{channelNames[channelId]}</span>
                                <span className="text-gray-500 text-sm ml-2">
                                  ({messages.length} results)
                                </span>
                              </div>
                              {!collapsedChannels.has(channelId) && (
                                <div className="ml-6">
                                  {messages.map(message => (
                                    <ChatMessage
                                      key={message.id}
                                      message={message}
                                      onReactionChange={() => {}}
                                      isReply={false}
                                      isHighlighted={false}
                                      onClick={() => {
                                        const channel = channels.find(c => c.id === message.channelId);
                                        if (channel) {
                                          handleSearchResultClick(
                                            message.channelId,
                                            channelNames[message.channelId],
                                            channel.type === 'dm',
                                            message.id
                                          );
                                        }
                                      }}
                                    />
                                  ))}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </>
                  );
                })()}
              </div>
            ) : (
              <MessageList 
                channelId={currentChannel}
                messages={messages}
                setMessages={setMessages}
                currentChannelName={currentChannelName}
              />
            )}

            {!isSearching && (
              <MessageInput 
                channelId={currentChannel}
                onSendMessage={handleSendMessage}
                currentChannelName={currentChannelName}
              />
            )}
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-gray-500">
            Select a channel to start chatting
          </div>
        )}
      </div>
    </div>
  );
}; 