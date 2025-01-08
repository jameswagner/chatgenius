import { useState } from 'react';
import { MagnifyingGlassIcon } from '@heroicons/react/24/outline';
import { api } from '../../services/api';
import { Message } from '../../types/chat';

interface SearchBarProps {
  onResultsFound: (messages: Message[]) => void;
}

export const SearchBar = ({ onResultsFound }: SearchBarProps) => {
  const [query, setQuery] = useState('');

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    try {
      const results = await api.messages.search(query);
      onResultsFound(results);
    } catch (err) {
      console.error('Search failed:', err);
    }
  };

  return (
    <form onSubmit={handleSearch} className="max-w-xl">
      <div className="relative">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search messages..."
          className="w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 focus:outline-none focus:border-blue-500"
        />
        <MagnifyingGlassIcon 
          className="absolute left-3 top-2.5 h-5 w-5 text-gray-400"
        />
      </div>
    </form>
  );
}; 