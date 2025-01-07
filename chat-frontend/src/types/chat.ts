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
  reactions?: { [emoji: string]: string[] };
  attachments: string[];
  replyCount?: number;
}

export interface Channel {
  id: string;
  name: string;
  type: string;
  createdBy: string;
  createdAt: string;
  members: Array<{
    id: string;
    name: string;
  }>;
} 