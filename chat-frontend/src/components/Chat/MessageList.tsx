import { Message } from '../../types/chat';
import { format } from 'date-fns';

interface MessageListProps {
  channelId: string;
  messages: Message[];
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
}

interface ThreadGroup {
  threadId: string;
  messages: Message[];
}

export const MessageList = ({ channelId, messages, setMessages }: MessageListProps) => {
  const threadGroups = messages.reduce((groups: ThreadGroup[], message) => {
    const group = groups.find(g => g.threadId === message.threadId);
    if (group) {
      group.messages.push(message);
    } else {
      groups.push({ threadId: message.threadId, messages: [message] });
    }
    return groups;
  }, []);

  const formatTime = (dateString: string) => {
    return format(new Date(dateString), 'h:mm a');
  };

  const renderThread = (thread: ThreadGroup) => {
    const [firstMessage, ...replies] = thread.messages;
    return (
      <div key={thread.threadId} className="mb-6">
        {/* First message */}
        <div className="flex items-start">
          <div className="h-10 w-10 rounded bg-gray-300 flex-shrink-0" />
          <div className="ml-3">
            <div className="flex items-center">
              <span className="font-bold">{firstMessage.user?.name}</span>
              <span className="ml-2 text-xs text-gray-500">
                {formatTime(firstMessage.createdAt)}
              </span>
            </div>
            <p className="text-gray-900">{firstMessage.content}</p>
          </div>
        </div>

        {/* Replies */}
        {replies.length > 0 && (
          <div className="ml-12 mt-2 space-y-2 border-l-2 border-gray-200 pl-4">
            {replies.map(reply => (
              <div key={reply.id} className="flex items-start">
                <div className="h-8 w-8 rounded bg-gray-300 flex-shrink-0" />
                <div className="ml-3">
                  <div className="flex items-center">
                    <span className="font-bold">{reply.user?.name}</span>
                    <span className="ml-2 text-xs text-gray-500">
                      {formatTime(reply.createdAt)}
                    </span>
                  </div>
                  <p className="text-gray-900">{reply.content}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="flex-1 overflow-y-auto px-6 py-4">
      {threadGroups.map(renderThread)}
    </div>
  );
}; 