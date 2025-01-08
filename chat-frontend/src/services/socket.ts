import { io, Socket } from 'socket.io-client';
import { WS_URL } from '../config/api';
import { Message, Channel } from '../types/chat';

class SocketService {
  private socket: Socket | null = null;

  connect() {
    if (this.socket?.connected) {
      console.log('[SOCKET] Already connected');
      return;
    }

    const token = localStorage.getItem('token');
    if (!token) {
      console.log('[SOCKET] No token found, skipping connection');
      return;
    }

    console.log('[SOCKET] Connecting...');
    this.socket = io(WS_URL, {
      auth: { token },
      extraHeaders: {
        Authorization: `Bearer ${token}`
      }
    });

    this.socket.on('connect', () => {
      console.log('[SOCKET] Connected successfully');
      console.log('[SOCKET] Socket ID:', this.socket?.id);
    });

    this.socket.on('connect_error', (error) => {
      console.error('[SOCKET] Connection error:', error);
    });

    // Debug all incoming events
    this.socket.onAny((eventName, ...args) => {
      console.log(`[SOCKET] Received event "${eventName}":`, args);
    });

    this.socket.on('disconnect', () => {
      console.log('Socket disconnected');
    });
  }

  disconnect() {
    if (!this.socket) return;
    this.socket.disconnect();
    this.socket = null;
  }

  joinChannel(channelId: string) {
    if (!this.socket) return;
    this.socket.emit('channel.join', channelId);
  }

  leaveChannel(channelId: string) {
    if (!this.socket) return;
    this.socket.emit('channel.leave', channelId);
  }

  onNewMessage(callback: (message: Message) => void) {
    if (!this.socket) return;
    this.socket.on('message.new', callback);
  }

  offNewMessage(callback: (message: Message) => void) {
    if (!this.socket) return;
    this.socket.off('message.new', callback);
  }

  onMessageUpdate(callback: (message: Message) => void) {
    if (!this.socket) return;
    this.socket.on('message.update', callback);
  }

  offMessageUpdate(callback: (message: Message) => void) {
    if (!this.socket) return;
    this.socket.off('message.update', callback);
  }

  onNewChannel(callback: (channel: Channel) => void) {
    if (!this.socket) return;
    this.socket.on('channel.new', callback);
  }

  offNewChannel(callback: (channel: Channel) => void) {
    if (!this.socket) return;
    this.socket.off('channel.new', callback);
  }

  on(event: string, callback: (data: any) => void) {
    if (!this.socket) {
      console.log('[SOCKET] No socket connection when attempting to listen to:', event);
      return;
    }
    console.log(`[SOCKET] Adding listener for ${event}`);
    // Remove any existing listeners for this event
    this.socket.off(event);
    // Add the new listener
    this.socket.on(event, (...args) => {
      console.log(`[SOCKET] Handling ${event} with data:`, args);
      // The data is in the first argument, and if it's an array, take the first element
      const data = Array.isArray(args[0]) ? args[0][0] : args[0];
      callback(data);
    });
  }

  off(event: string, callback: (data: any) => void) {
    if (!this.socket) return;
    this.socket.off(event, callback);
  }

  emit(event: string, ...args: any[]) {
    if (!this.socket) return;
    this.socket.emit(event, ...args);
  }
}

export const socketService = new SocketService(); 