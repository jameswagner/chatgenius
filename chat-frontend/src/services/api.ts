import axios from 'axios';
import { API_BASE_URL } from '../config/api';
import { AuthResponse } from '../types/auth';
import { Message, Channel, Reaction, Workspace } from '../types/chat';

// API Client
const client = axios.create({
  baseURL: API_BASE_URL
});

// Add auth token to all requests
client.interceptors.request.use(config => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  
  // Set Content-Type to application/json for non-FormData requests
  if (!(config.data instanceof FormData)) {
    config.headers['Content-Type'] = 'application/json';
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
        if (!response.data.token || !response.data.user.id) {
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
      console.log(client)
      return response.data;
    },
    logout: async (): Promise<void> => {
      await client.post('/auth/logout');
    },
    loginAsPersona: async (email: string) => {
      const response = await fetch(`${API_BASE_URL}/auth/login/persona`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email }),
      });
      
      if (!response.ok) {
        throw new Error('Failed to login as persona');
      }
      
      return response.json();
    },
  },

  personas: {
    list: async () => {
      const response = await fetch(`${API_BASE_URL}/personas`);
      
      if (!response.ok) {
        throw new Error('Failed to fetch personas');
      }
      
      return response.json();
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

    create: async (data: { name: string; workspaceId: string; type?: string; otherUserId?: string }): Promise<Channel> => {
      console.log('Creating channel with data:', data); // Debug log
      const response = await client.post('/channels', {
        name: data.name,
        type: data.type || 'public',  // Make sure we're sending the type
        otherUserId: data.otherUserId,
        workspaceId: data.workspaceId
      });
      return snakeToCamel(response.data);
    },

    join: async (channelId: string): Promise<void> => {
      await client.post(`/channels/${channelId}/join`);
    },

    leave: async (channelId: string): Promise<void> => {
      await client.post(`/channels/${channelId}/leave`);
    },

    markRead: async (channelId: string): Promise<void> => {
      if (!channelId) return;
      await client.post(`/channels/${channelId}/read`);
    },

    listByWorkspace: async (workspaceId?: string): Promise<Channel[] > => {
        const response = await client.get(`/channels/workspace/${workspaceId}`);
        return response.data;
      }
  },

  // Message operations
  messages: {
    list: async (channelId: string): Promise<Message[]> => {
      const response = await client.get(`/channels/${channelId}/messages`, {
        params: {
          limit: 1000  // Request up to 1000 messages
        }
      });
      console.log('Raw message data from backend:', response.data);
      const transformed = snakeToCamel(response.data);
      console.log('Transformed message data:', transformed);
      for (const message of transformed) {
        if (message.replies) {
          message.replyMessages = transformed.filter((m: Message) => message.replies.includes(m.id));
        }
      }
      return transformed;
    },

    create: async (channelId: string, data: FormData): Promise<Message> => {
      console.log('DEBUG_ATTACH: Creating message with FormData');
      
      // Log FormData contents
      console.log('DEBUG_ATTACH: FormData entries before sending:');
      for (let pair of data.entries()) {
        console.log('DEBUG_ATTACH: FormData entry -', pair[0], ':', pair[1] instanceof File ? `File: ${pair[1].name}` : pair[1]);
      }

      const token = localStorage.getItem('token');
      const response = await client.post(
        `/channels/${channelId}/messages`,
        data,
        {
          headers: {
            Authorization: token ? `Bearer ${token}` : '',
            // Let the browser set the Content-Type with boundary
          },
        }
      );
      
      console.log('DEBUG_ATTACH: Response from server:', response.data);
      const processedResponse = snakeToCamel(response.data);
      console.log('DEBUG_ATTACH: Processed response:', processedResponse);
      
      return processedResponse;
    },

    update: async (messageId: string, data: { content: string }): Promise<Message> => {
      try {
        const response = await client.put(`/messages/${messageId}`, data);
        return snakeToCamel(response.data);
      } catch (error: any) {
        throw error;
      }
    },

    search: async (query: string, workspaceId: string): Promise<Message[]> => {
      const response = await client.get(`/search/messages`, { params: { q: query, workspace_id: workspaceId } });
      return snakeToCamel(response.data);
    },

    getThreadMessages: async (messageId: string): Promise<Message[]> => {
      const response = await client.get(`/messages/${messageId}/thread`);
      return snakeToCamel(response.data);
    },

    get: async (messageId: string): Promise<Message> => {
      const response = await client.get(`/messages/${messageId}`);
      return snakeToCamel(response.data);
    },

    createThreadReply: async (messageId: string, data: { content: string }): Promise<Message> => {
      const response = await client.post(`/messages/${messageId}/thread`, data);
      return snakeToCamel(response.data);
    },
  },

  // Reaction operations
  reactions: {
    add: async (messageId: string, emoji: string, threadId?: string): Promise<Reaction> => {
      const response = await client.post(
        `/messages/${messageId}/reactions`, 
        { emoji },
        { params: threadId ? { thread_id: threadId } : undefined }
      );
      return response.data;
    },

    remove: async (messageId: string, emoji: string, threadId?: string): Promise<void> => {
      await client.delete(
        `/messages/${messageId}/reactions/${emoji}`,
        { params: threadId ? { thread_id: threadId } : undefined }
      );
    },
  },

  // Add to existing api object
  users: {
    list: async () => {
      const response = await client.get('/users');
      return snakeToCamel(response.data);
    },
    updateStatus: async (status: string): Promise<void> => {
      await client.put('/users/status', { status });
    },
    getOnline: async () => {
      const response = await client.get('/users/online');
      return snakeToCamel(response.data);
    },
    getCurrentUser: async () => {
      const response = await client.get('/users/me');
      return snakeToCamel(response.data);
    },
  },

  workspaces: {
    list: async (): Promise<Workspace[]> => {
      const response = await client.get('/workspaces');
      return response.data;
    },
    listChannels: async (workspaceId: string): Promise<Channel[]> => {
      const response = await client.get(`/channel/workspace/${workspaceId}`);
      return snakeToCamel(response.data);
    }
  },

  qa: {
    askAboutChannel: async (channelId: string): Promise<any> => {
      const response = await client.post(`/qa/channels/${channelId}/ask`, {
        question: "Please summarize the contents of this channel",
        get_all: true
      });
      return response.data;
    }
  },

  async createBotChannel(workspaceId: string): Promise<Channel> {
    const response = await client.post('/channels/bot', { workspace_id: workspaceId });
    return snakeToCamel(response.data);
  },

  async getBotChannel(workspaceId: string): Promise<Channel | null> {
    const response = await client.get('/channels/bot', { params: { workspace_id: workspaceId } });
    return response.data ? snakeToCamel(response.data) : null;
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

// Add a response interceptor to log responses
client.interceptors.response.use(
  response => {
    console.log('API Response:', response);
    return response;
  },
  error => {
    console.error('API Error:', error);
    return Promise.reject(error);
  }
);

export const healthCheck = async () => {
    try {
        const response = await axios.get('/health');
        return response.status === 200;
    } catch (error) {
        return false;
    }
};

export default api; 