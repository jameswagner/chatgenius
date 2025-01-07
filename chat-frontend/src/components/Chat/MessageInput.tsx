import { useState, useRef } from 'react';
import { PaperAirplaneIcon, PaperClipIcon } from '@heroicons/react/24/outline';

interface MessageInputProps {
  channelId: string;
  onSendMessage: (content: string, files: File[], threadId?: string) => void;
  threadId?: string;
  placeholder?: string;
  currentChannelName: string;
}

export const MessageInput = ({ channelId, onSendMessage, threadId, currentChannelName, placeholder }: MessageInputProps) => {
  const [message, setMessage] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(e.target.files || []);
    if (selectedFiles.length > 3) {
      alert('Maximum 3 files allowed');
      return;
    }
    
    const validFiles = selectedFiles.filter(file => {
      if (file.size > 1024 * 1024) {
        alert(`File ${file.name} is larger than 1MB`);
        return false;
      }
      return true;
    });

    setFiles(validFiles);
  };

  const handleSubmit = () => {
    if (message.trim() || files.length > 0) {
      onSendMessage(message, files, threadId);
      setMessage('');
      setFiles([]);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  return (
    <div className="p-4 border-t">
      {files.length > 0 && (
        <div className="mb-2 flex gap-2">
          {files.map(file => (
            <div key={file.name} className="flex items-center gap-1 bg-gray-100 px-2 py-1 rounded">
              <span className="text-sm">{file.name}</span>
              <button 
                onClick={() => setFiles(files.filter(f => f !== file))}
                className="text-gray-500 hover:text-gray-700"
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
          placeholder={placeholder || `Message ${currentChannelName}`}
          className="flex-1 px-4 py-2 border rounded-lg focus:outline-none focus:border-blue-500"
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleSubmit();
            }
          }}
        />
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileSelect}
          multiple
          className="hidden"
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          className="p-2 text-gray-500 hover:text-gray-700"
        >
          <PaperClipIcon className="h-5 w-5" />
        </button>
        <button
          onClick={handleSubmit}
          className="p-2 text-blue-500 hover:text-blue-600"
        >
          <PaperAirplaneIcon className="h-5 w-5" />
        </button>
      </div>
    </div>
  );
}; 