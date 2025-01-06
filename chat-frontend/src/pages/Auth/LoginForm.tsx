import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../services/api';

export const LoginForm = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const response = await api.auth.login(email, password);
      localStorage.setItem('token', response.token);
      localStorage.setItem('userId', response.user.id);
      navigate('/');
    } catch (err) {
      setError('Invalid email or password');
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && (
        <div className="bg-red-100 text-red-600 p-2 rounded text-center">
          {error}
        </div>
      )}
      <div>
        <label htmlFor="login-email" className="block text-sm font-medium text-gray-700">Email</label>
        <input
          id="login-email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2"
          required
        />
      </div>
      <div>
        <label htmlFor="login-password" className="block text-sm font-medium text-gray-700">Password</label>
        <input
          id="login-password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2"
          required
        />
      </div>
      <button
        type="submit"
        className="w-full bg-purple-600 text-white py-2 px-4 rounded hover:bg-purple-700"
      >
        Login
      </button>
    </form>
  );
}; 