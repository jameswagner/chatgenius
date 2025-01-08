export interface Reaction {
  messageId: string;
  userId: string;
  emoji: string;
  createdAt: string;
}

export interface User {
  id: string;
  name: string;
  status?: string;
  lastActive?: string;
}

export interface Message {
  id: string;
  content: string;
  userId: string;
  channelId: string;
  threadId?: string;
  createdAt: string;
  reactions?: { [emoji: string]: string[] };
  attachments: string[];
  replyCount?: number;
  user?: User;
}

export interface Channel {
  id: string;
  name: string;
  type: string;
  members?: User[];
  created_by?: string;
  created_at?: string;
} 