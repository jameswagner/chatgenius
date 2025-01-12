import { useState, useEffect } from 'react';
import { api } from '../../services/api';
import { socketService } from '../../services/socket';

type Status = 'online' | 'away' | 'busy' | 'offline';

interface StatusOption {
  value: Status;
  label: string;
  icon: string;
}

const STATUS_OPTIONS: StatusOption[] = [
  { value: 'online', label: 'Online', icon: '🟢' },
  { value: 'away', label: 'Away', icon: '🌙' },
  { value: 'busy', label: 'Busy', icon: '⛔' },
  { value: 'offline', label: 'Appear Offline', icon: '⭘' },
];

export const StatusSelector = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [currentStatus, setCurrentStatus] = useState<Status | null>(null);
  const userId = localStorage.getItem('userId');

  // Fetch initial status
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const user = await api.users.getCurrentUser();
        setCurrentStatus(user.status as Status);
      } catch (error) {
        console.error('Failed to fetch user status:', error);
      }
    };
    fetchStatus();
  }, []);

  const handleStatusChange = async (status: Status) => {
    try {
      await api.users.updateStatus(status);
      setCurrentStatus(status);
      setIsOpen(false);
    } catch (error) {
      console.error('Failed to update status:', error);
    }
  };

  // Listen for status updates
  useEffect(() => {
    if (!userId) return;

    socketService.on('user.status', (data: { userId: string; status: string }) => {
      if (data.userId === userId) {
        setCurrentStatus(data.status as Status);
      }
    });

    return () => {
      socketService.off('user.status', () => {});
    };
  }, [userId]);

  const currentOption = currentStatus ? STATUS_OPTIONS.find(opt => opt.value === currentStatus) : null;

  return (
    <div className="relative">
      <button
        data-testid="status-selector-button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-1 rounded hover:bg-gray-100"
      >
        {currentOption ? (
          <>
            <span>{currentOption.icon}</span>
            <span>{currentOption.label}</span>
          </>
        ) : (
          <span className="w-16 h-4 bg-gray-100 animate-pulse rounded"></span>
        )}
      </button>

      {isOpen && (
        <div className="absolute top-full right-0 mt-1 bg-white rounded-lg shadow-lg border border-gray-200 py-1 w-48">
          {STATUS_OPTIONS.map(option => (
            <button
              key={option.value}
              data-testid={`status-option-${option.value}`}
              onClick={() => handleStatusChange(option.value)}
              className={`w-full px-4 py-2 text-left flex items-center gap-2 hover:bg-gray-100
                ${currentStatus === option.value ? 'bg-gray-50' : ''}`}
            >
              <span>{option.icon}</span>
              <span>{option.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}; 