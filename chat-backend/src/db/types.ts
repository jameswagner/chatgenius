export interface Message {
  id: string;
  content: string;
  userId: string;
  channelId: string;
  threadId: string;
  createdAt: string;
  user?: {
    name: string;
  };
} 