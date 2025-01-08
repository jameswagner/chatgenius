import { useState, useEffect } from 'react';
import { api } from '../../services/api';

interface User {
  id: string;
  name: string;
}

interface UserSelectorProps {
  onClose: () => void;
  onUserSelect: (userId: string, userName: string) => Promise<void>;
}

export const UserSelector = ({ onClose, onUserSelect }: UserSelectorProps) => {
  const [users, setUsers] = useState<User[]>([]);
  const currentUserId = localStorage.getItem('userId');

  useEffect(() => {
    const fetchUsers = async () => {
      try {
        const response = await api.users.list();
        const sortedUsers = [...response].sort((a, b) => a.name.localeCompare(b.name));
        setUsers(sortedUsers);
      } catch (err) {
        console.error('Failed to fetch users:', err);
      }
    };
    fetchUsers();
  }, []);

  return (
    <>
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[100]">
        <div className="bg-white rounded-lg p-6 w-80 relative z-[100]">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-lg font-bold text-gray-900">New Message</h3>
            <button onClick={onClose} className="text-gray-500 hover:text-gray-700">✕</button>
          </div>
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {users.map(user => (
              <button
                key={user.id}
                onClick={() => onUserSelect(user.id, user.name)}
                disabled={user.id === currentUserId}
                className={`w-full text-left p-2 rounded text-gray-900 ${
                  user.id === currentUserId 
                    ? 'bg-gray-100 text-gray-500 cursor-not-allowed' 
                    : 'hover:bg-gray-100'
                }`}
              >
                {user.name}
              </button>
            ))}
          </div>
        </div>
      </div>
      <div className="fixed inset-0 z-[99]" onClick={onClose}></div>
    </>
  );
}; 