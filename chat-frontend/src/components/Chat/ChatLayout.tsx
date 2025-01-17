import { useState, useEffect, useRef } from 'react';
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
  const [isLoadingChannel, setIsLoadingChannel] = useState(false);
  const [collapsedChannels, setCollapsedChannels] = useState<Set<string>>(new Set());
  const [channelNames, setChannelNames] = useState<{ [channelId: string]: string }>({});
  const navigate = useNavigate();

  // Cache for user data
  const userCache = useRef<{ [userId: string]: any }>({});

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
        console.log('\nNew message received:', {
          messageId: message.id,
          threadId: message.threadId,
          channelId: message.channelId,
          userId: message.userId,
          content: message.content,
          createdAt: message.createdAt
        });
        
        // Cache user data
        if (message.user) {
          userCache.current[message.userId] = message.user;
        }

        const currentUserId = localStorage.getItem('userId');
        const isOwnMessage = message.userId === currentUserId;

        // If this is for the current channel, add it to messages
        if (message.channelId === currentChannel) {
          setMessages(prev => {
            // If it's a reply, find the parent message and add to its replies
            if (message.threadId) {
              return prev.map(m => {
                if (m.id === message.threadId) {
                  return {
                    ...m,
                    replies: [...(m.replies || []), message.id]
                  };
                }
                return m;
              });
            }
            // If it's a parent message, add it to the array
            return [...prev, message];
          });

          // Only mark as read if it's our own message or we're viewing it
          if (isOwnMessage) {
            
          } else {
            
            api.channels.markRead(message.channelId)
              .then(() => {
                console.log('Channel marked as read:', message.channelId);
                // Update channel list to reflect read status
                setChannels(prevChannels => {
                  const updatedChannels = prevChannels.map(channel => 
                    channel.id === message.channelId 
                      ? { ...channel, lastRead: new Date().toISOString() }
                      : channel
                  );
                  return updatedChannels;
                });
              })
              .catch(err => console.error('Failed to mark channel as read:', err));
          }
        } else if (!isOwnMessage) {
          // Only mark other channels as unread if the message is from someone else
          setChannels(prevChannels => {
            const updatedChannels = prevChannels.map(channel => 
              channel.id === message.channelId 
                ? { ...channel, lastRead: undefined }
                : channel
            );
            return updatedChannels;
          });
        }
      };

      const handleReaction = (message: Message) => {
        if (message.channelId === currentChannel) {
          setMessages(prev => prev.map(m => 
            m.id === message.id ? {
              ...m,
              reactions: message.reactions || {}
            } : m
          ));
        }
      };

      const handleMessageUpdate = (message: Message) => {
        if (message.channelId === currentChannel) {
          setMessages(prev => prev.map(m => 
            m.id === message.id ? {
              ...m,
              content: message.content,
              isEdited: true,
              editedAt: message.editedAt,
              reactions: message.reactions || m.reactions
            } : m
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
    return () => {
      // Keep empty cleanup to satisfy TypeScript
    };
  }, []);

  const handleChannelSelect = async (channelId: string, channelName: string, isDirectMessage: boolean, isBot: boolean = false) => {
    console.log('Selecting channel:', { channelId, channelName, isDirectMessage, isBot });
    setIsLoadingChannel(true);
    try {
      // Mark previous channel as read before switching
      if (currentChannel && currentChannel !== channelId) {
        console.log('Marking previous channel as read:', currentChannel);
        await api.channels.markRead(currentChannel);
      }
      
      // Store channel info
      localStorage.setItem('currentChannel', channelId);
      localStorage.setItem('currentChannelName', channelName);
      localStorage.setItem('currentChannelType', isDirectMessage ? 'dm' : isBot ? 'bot' : 'public');
      
      setCurrentChannel(channelId);
      setCurrentChannelName(channelName);
      setCurrentChannelType(isDirectMessage ? 'dm' : isBot ? 'bot' : 'public');
      
      // Load messages
      const messages = await api.messages.list(channelId);
      console.log('Loaded messages:', messages);
      setMessages(messages);

      // Mark new channel as read
      console.log('Marking new channel as read:', channelId);
      await api.channels.markRead(channelId);
      
      // Update channel list to reflect read status
      setChannels(prevChannels => {
        const updatedChannels = prevChannels.map(channel => 
          channel.id === channelId 
            ? { ...channel, lastRead: new Date().toISOString() }
            : channel
        );
        console.log('Updated channels after marking as read:', updatedChannels);
        return updatedChannels;
      });
      
      // Join socket room for this channel
      socketService.joinChannel(channelId);
      
    } catch (error) {
      console.error('Failed to load channel:', error);
    } finally {
      setIsLoadingChannel(false);
    }
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

      // Since backend only returns messages from channels the user is a member of,
      // we can simply check if it's a DM or not
      let targetGroup;
      if (channel.type === 'dm') {
        targetGroup = grouped.dms;
      } else {
        targetGroup = grouped.memberChannels;
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

  // Cache user data when messages are loaded
  useEffect(() => {
    messages.forEach(message => {
      if (message.user) {
        userCache.current[message.userId] = message.user;
      }
    });
  }, [messages]);


  return (
    <div className="flex h-screen">
      <Sidebar 
        currentChannel={currentChannel || ''}
        onChannelSelect={handleChannelSelect}
        channels={channels}
        messages={messages}
      />
      <div className="flex-1 flex flex-col">
        <div className="p-4 border-b flex items-center bg-white">
          <div className="w-48">
            {currentChannel && (
              <h2 className="font-bold text-lg">
                {currentChannelType === 'dm' ? currentChannelName : currentChannelType === 'bot' ? 'Ask our chatbot' : `#${currentChannelName}`}
              </h2>
            )}
          </div>
          <div className="flex-1 flex justify-center">
            <div className="w-96">
              <SearchBar onResultsFound={handleSearchResults} />
            </div>
          </div>
          <div className="flex items-center gap-4">
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
              <>
                {isLoadingChannel ? (
                  <div className="flex-1 flex items-center justify-center">
                    <div className="flex flex-col items-center gap-3">
                      <svg className="animate-spin h-8 w-8 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      <span className="text-gray-500">Loading messages...</span>
                    </div>
                  </div>
                ) : (
                  <MessageList 
                    channelId={currentChannel}
                    messages={messages}
                    setMessages={setMessages}
                    currentChannelName={currentChannelName}
                  />
                )}
              </>
            )}

            {!isSearching && (
              <MessageInput 
                onSendMessage={handleSendMessage}
                currentChannelName={currentChannelName}
                isDM={currentChannelType === 'dm'}
                isBot={currentChannelType === 'bot'}
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