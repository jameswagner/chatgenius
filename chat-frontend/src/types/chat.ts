export interface Reaction {
  messageId: string;
  userId: string;
  emoji: string;
  createdAt: string;
}

export interface Message {
  id: string;
  content: string;
  userId: string;
  channelId: string;
  threadId?: string;
  createdAt: string;
  user?: {
    name: string;
  };
  reactions?: { [emoji: string]: string[] }; // emoji -> array of userIds
} 