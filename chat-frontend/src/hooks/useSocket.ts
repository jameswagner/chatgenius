import { useEffect, useRef } from 'react';
import io, { Socket } from 'socket.io-client';
import { WS_URL } from '../config/api';

export const useSocket = (channelId: string, onNewMessage: (message: any) => void) => {
  const socketRef = useRef<Socket>();

  useEffect(() => {
    // Create socket if it doesn't exist
    if (!socketRef.current) {
      socketRef.current = io(WS_URL, {
        query: {
          token: localStorage.getItem('token')
        }
      });
    }

    const socket = socketRef.current;

    // Leave previous channel if any
    socket.emit('channel.leave', channelId);
    // Join new channel
    socket.emit('channel.join', channelId);

    socket.on('message.new', onNewMessage);

    return () => {
      socket.off('message.new');
      socket.emit('channel.leave', channelId);
    };
  }, [channelId, onNewMessage]);

  return socketRef.current;
}; 