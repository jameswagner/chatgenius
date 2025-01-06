import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../services/api';

interface FormData {
  name: string;
  email: string;
  password: string;
}

export const RegisterForm = () => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState<FormData>({ name: '', email: '', password: '' });
  const [error, setError] = useState<string>('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(''); // Clear previous errors

    try {
      const response = await api.auth.register(
        formData.name,
        formData.email,
        formData.password
      );
      if (response.token && response.user_id) {
        localStorage.setItem('token', response.token);
        localStorage.setItem('userId', response.user_id);
        navigate('/chat');
      } else {
        setError('Invalid response from server');
      }
    } catch (error: any) {
      console.error('Registration failed:', error);
      setError(error.message || 'Registration failed. Please try again.');
      // Don't navigate on error
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && <div className="text-red-500">{error}</div>}
      <div>
        <input
          type="text"
          placeholder="Name"
          value={formData.name}
          onChange={(e) => setFormData({ ...formData, name: e.target.value })}
          className="w-full p-2 border rounded"
          required
        />
      </div>
      <div>
        <input
          type="email"
          placeholder="Email"
          value={formData.email}
          onChange={(e) => setFormData({ ...formData, email: e.target.value })}
          className="w-full p-2 border rounded"
          required
        />
      </div>
      <div>
        <input
          type="password"
          placeholder="Password"
          value={formData.password}
          onChange={(e) => setFormData({ ...formData, password: e.target.value })}
          className="w-full p-2 border rounded"
          required
        />
      </div>
      <button type="submit" className="w-full bg-blue-500 text-white p-2 rounded">
        Register
      </button>
    </form>
  );
}; 