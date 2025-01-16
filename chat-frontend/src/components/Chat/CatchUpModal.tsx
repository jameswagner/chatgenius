import React, { useState } from 'react';
import { Channel } from '../../types/chat';
import DatePicker from 'react-datepicker';
import 'react-datepicker/dist/react-datepicker.css';

interface CatchUpModalProps {
  onClose: () => void;
  channels: Channel[];
  onChannelSelect: (selectedChannels: string[], dateRange: { start: Date; end: Date }) => void;
  onFetchQaResponse: (channelId: string) => void;
}

export const CatchUpModal: React.FC<CatchUpModalProps> = ({ onClose, channels, onChannelSelect, onFetchQaResponse }) => {
  const [selectedChannel, setSelectedChannel] = useState<string | null>(null);
  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);
  const [startDate, setStartDate] = useState<Date | null>(yesterday);
  const [endDate, setEndDate] = useState<Date | null>(yesterday);

  const sortedChannels = [...channels].sort((a, b) => a.name.localeCompare(b.name));

  const handleRadioChange = (channelId: string) => {
    setSelectedChannel(channelId);
  };

  const handleSubmit = () => {
    if (startDate && endDate && selectedChannel) {
      onFetchQaResponse(selectedChannel);
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-80 relative z-50">
        <h3 className="text-lg font-bold text-gray-900 mb-4">Select Channels</h3>
        <ul className="mb-4">
          {sortedChannels.map(channel => (
            <li key={channel.id}>
              <label className="flex items-center text-gray-900">
                <input
                  type="radio"
                  name="channel"
                  checked={selectedChannel === channel.id}
                  onChange={() => handleRadioChange(channel.id)}
                  className="mr-2"
                />
                {channel.name}
              </label>
            </li>
          ))}
        </ul>
        <div className="mb-4">
          <h4 className="text-gray-900 mb-2">Select Date Range</h4>
          <DatePicker
            selected={startDate}
            onChange={(date: Date) => setStartDate(date)}
            selectsStart
            startDate={startDate}
            endDate={endDate}
            placeholderText="Start Date"
            className="w-full p-2 border rounded mb-2 text-gray-900"
          />
          <DatePicker
            selected={endDate}
            onChange={(date: Date) => setEndDate(date)}
            selectsEnd
            startDate={startDate}
            endDate={endDate}
            minDate={startDate || undefined}
            placeholderText="End Date"
            className="w-full p-2 border rounded text-gray-900"
          />
        </div>
        <div className="flex justify-end space-x-2">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-600 hover:text-gray-800"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            className={`px-4 py-2 rounded ${selectedChannel ? 'bg-blue-500 text-white hover:bg-blue-600' : 'bg-gray-400 text-gray-700'}`}
            disabled={!selectedChannel || !startDate || !endDate}
          >
            Confirm
          </button>
        </div>
      </div>
    </div>
  );
}; 