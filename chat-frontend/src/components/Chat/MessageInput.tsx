import { useState, useRef } from 'react';
import { PaperAirplaneIcon, PaperClipIcon, DocumentIcon } from '@heroicons/react/24/outline';

interface MessageInputProps {
  channelId: string;
  onSendMessage: (content: string, files: File[], threadId?: string) => void;
  threadId?: string;
  placeholder?: string;
  currentChannelName: string;
  isDM?: boolean;
  testId?: string;
}

export const MessageInput = ({ channelId, onSendMessage, threadId, placeholder, currentChannelName, isDM = false, testId = "message-input" }: MessageInputProps) => {
  const [message, setMessage] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [isSending, setIsSending] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newFiles = Array.from(e.target.files || []);
    const totalFiles = [...files, ...newFiles];
    
    if (totalFiles.length > 5) {
      alert('Maximum 5 files allowed');
      return;
    }
    
    setFiles(totalFiles);
  };

  const removeFile = (index: number) => {
    setFiles(files.filter((_, i) => i !== index));
  };

  const handleSubmit = async () => {
    const trimmedMessage = message.trim();
    if (!trimmedMessage && files.length === 0) return;
    
    setIsSending(true);
    try {
      // Call onSendMessage immediately for optimistic update
      onSendMessage(trimmedMessage, files, threadId);
      // Clear the input immediately
      setMessage('');
      setFiles([]);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    } finally {
      setIsSending(false);
    }
  };

  const isDisabled = (!message.trim() && files.length === 0) || isSending;

  return (
    <div className="p-4 border-t">
      {files.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-2">
          {files.map((file, index) => (
            <div key={index} className="flex items-center gap-1 bg-gray-100 px-2 py-1 rounded">
              <DocumentIcon className="h-4 w-4 text-gray-500" />
              <span className="text-sm text-gray-700">{file.name}</span>
              <button
                onClick={() => removeFile(index)}
                className="ml-1 text-gray-400 hover:text-gray-600"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}
      <div className="flex gap-2">
        <input
          type="text"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder={placeholder || `Message ${isDM ? '' : '#'}${currentChannelName}`}
          className="flex-1 px-4 py-2 border rounded-lg focus:outline-none focus:border-blue-500"
          data-testid={testId}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey && !isDisabled) {
              e.preventDefault();
              handleSubmit();
            }
          }}
        />
        <input
          type="file"
          multiple
          onChange={handleFileChange}
          className="hidden"
          id="file-input"
          ref={fileInputRef}
          accept="image/*,.pdf,.doc,.docx,.txt"
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          className="p-2 text-gray-500 hover:text-gray-700"
          disabled={isSending}
          data-testid="attachment-button"
        >
          <PaperClipIcon className="h-5 w-5" />
        </button>
        <button
          onClick={handleSubmit}
          disabled={isDisabled}
          className={`p-2 ${isDisabled ? 'text-gray-300 cursor-not-allowed' : 'text-blue-500 hover:text-blue-600'}`}
          data-testid="send-message-button"
        >
          <PaperAirplaneIcon className="h-5 w-5" />
        </button>
      </div>
    </div>
  );
}; 