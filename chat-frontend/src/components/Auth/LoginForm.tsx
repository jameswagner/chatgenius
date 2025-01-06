import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../services/api';

interface FormData {
  email: string;
  password: string;
}

export const LoginForm = () => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState<FormData>({ email: '', password: '' });
  const [error, setError] = useState<string>('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    console.log('1. Form submission started');
    
    try {
      console.log('2. About to call API');
      const response = await api.auth.login(formData.email, formData.password);
      console.log('3. API Response:', response);

      if (!response.token || !response.user_id) {
        console.log('4a. Invalid response');
        setError('Invalid response from server');
        return;
      }

      console.log('4b. Valid response, storing data');
      localStorage.setItem('token', response.token);
      localStorage.setItem('userId', response.user_id);
      
      console.log('5. About to navigate');
      navigate('/chat');
      
    } catch (error: any) {
      console.log('X. Error in submission:', error);
      setError(error.message || 'Login failed');
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && <div className="text-red-500">{error}</div>}
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
        Login
      </button>
    </form>
  );
}; 