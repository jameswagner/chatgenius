import axios from 'axios';
import { API_BASE_URL } from '../config/api';
import { AuthResponse } from '../types/auth';

// Types
interface Channel {
  id: string;
  name: string;
  type: string;
  createdBy: string;
  createdAt: string;
}

interface Message {
  id: string;
  content: string;
  userId: string;
  channelId: string;
  threadId?: string;
  createdAt: string;
}

interface Reaction {
  messageId: string;
  userId: string;
  emoji: string;
  createdAt: string;
}

// API Client
const client = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json'
  }
});

// Add auth token to all requests
client.interceptors.request.use(config => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

const snakeToCamel = (obj: any): any => {
  if (Array.isArray(obj)) {
    return obj.map(snakeToCamel);
  }
  
  const camelObj: any = {};
  for (const key in obj) {
    const camelKey = key.replace(/_([a-z])/g, g => g[1].toUpperCase());
    camelObj[camelKey] = obj[key];
  }
  return camelObj;
};

// API Methods
export const api = {
  auth: {
    login: async (email: string, password: string): Promise<AuthResponse> => {
      try {
        const response = await client.post('/auth/login', { email, password });
        if (!response.data.token || !response.data.user_id) {
          throw new Error('Invalid server response');
        }
        return response.data;
      } catch (error: any) {
        if (error.response?.data?.error) {
          throw new Error(error.response.data.error);
        }
        throw error;
      }
    },
    register: async (name: string, email: string, password: string): Promise<AuthResponse> => {
      const response = await client.post('/auth/register', { 
        name, 
        email, 
        password 
      });
      return response.data;
    },
  },

  // Channel operations
  channels: {
    list: async (): Promise<Channel[]> => {
      const response = await client.get('/channels');
      return snakeToCamel(response.data);
    },

    available: async (): Promise<Channel[]> => {
      const response = await client.get('/channels/available');
      return snakeToCamel(response.data);
    },

    create: async (data: { name: string; type?: string }): Promise<Channel> => {
      const response = await client.post('/channels', {
        ...data,
        type: 'public'
      });
      return snakeToCamel(response.data);
    },

    join: async (channelId: string): Promise<void> => {
      await client.post(`/channels/${channelId}/join`);
    },

    leave: async (channelId: string): Promise<void> => {
      await client.post(`/channels/${channelId}/leave`);
    }
  },

  // Message operations
  messages: {
    list: async (channelId: string, params?: { before?: string; limit?: number }): Promise<Message[]> => {
      const response = await client.get(`/channels/${channelId}/messages`, { params });
      return snakeToCamel(response.data);
    },

    create: async (channelId: string, data: { content: string; threadId?: string }): Promise<Message> => {
      const response = await client.post(`/channels/${channelId}/messages`, data);
      return snakeToCamel(response.data);
    },

    getThread: async (messageId: string): Promise<Message[]> => {
      const response = await client.get(`/messages/${messageId}/thread`);
      return response.data;
    },

    createThreadReply: async (messageId: string, data: { content: string }): Promise<Message> => {
      const response = await client.post(`/messages/${messageId}/thread`, data);
      return snakeToCamel(response.data);
    },

    getThreadMessages: async (messageId: string): Promise<Message[]> => {
      const response = await client.get(`/messages/${messageId}/thread`);
      return snakeToCamel(response.data);
    },

    getThreadSummary: async (messageId: string): Promise<Message['threadSummary']> => {
      const response = await client.get(`/messages/${messageId}/thread/summary`);
      return snakeToCamel(response.data);
    },

    get: async (messageId: string): Promise<Message> => {
      const response = await client.get(`/messages/${messageId}`);
      return snakeToCamel(response.data);
    },
  },

  // Reaction operations
  reactions: {
    add: async (messageId: string, emoji: string): Promise<Reaction> => {
      const response = await client.post(`/messages/${messageId}/reactions`, { emoji });
      return response.data;
    },

    remove: async (messageId: string, emoji: string): Promise<void> => {
      await client.delete(`/messages/${messageId}/reactions/${emoji}`);
    },
  },
};

// Error handling
export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

// Add global error handling
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      throw new ApiError(error.response.status, error.response.data.error);
    }
    throw error;
  }
);

export default api; 