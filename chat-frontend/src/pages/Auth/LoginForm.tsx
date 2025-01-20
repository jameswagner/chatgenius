import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../services/api';

interface Persona {
  id: string;
  name: string;
  email: string;
  role: string;
}

export const LoginForm = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [selectedPersona, setSelectedPersona] = useState<string>('');
  const navigate = useNavigate();

  useEffect(() => {
    // Fetch available personas
    const fetchPersonas = async () => {
      try {
        const data = await api.personas.list();
        setPersonas(data);
      } catch (error) {
        console.error('Failed to fetch personas:', error);
      }
    };
    fetchPersonas();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    
    try {
      let response;
      if (selectedPersona) {
        response = await api.auth.loginAsPersona(selectedPersona);
      } else {
        response = await api.auth.login(email, password);
      }

      console.log('Server response:', response);

      if (!response.token || !response.user.id) {
        setError('Invalid response from server');
        return;
      }

      localStorage.setItem('token', response.token);
      localStorage.setItem('userId', response.user.id);
      
      navigate('/chat');
      
    } catch (error: any) {
      setError(error.message || 'Login failed');
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && (
        <div className="bg-red-100 text-red-600 p-2 rounded text-center">
          {error}
        </div>
      )}

      {/* Persona Selector */}
      {personas.length > 0 && (
        <div>
          <label htmlFor="persona" className="block text-sm font-medium text-gray-700">
            Login as Persona (Optional)
          </label>
          <select
            id="persona"
            value={selectedPersona}
            onChange={(e) => {
              setSelectedPersona(e.target.value);
              if (e.target.value) {
                setEmail('');
                setPassword('');
              }
            }}
            className="w-full p-2 border rounded mb-4 text-gray-900"
          >
            <option value="">Select a persona</option>
            {personas.map(persona => (
              <option key={persona.id} value={persona.id}>
                {persona.name} - {persona.role}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Regular Login Fields - hidden if persona is selected */}
      {!selectedPersona && (
        <>
          <div>
            <label htmlFor="login-email" className="block text-sm font-medium text-gray-700">Email</label>
            <input
              id="login-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2"
              required={!selectedPersona}
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
              required={!selectedPersona}
            />
          </div>
        </>
      )}

      <button
        type="submit"
        className="w-full bg-purple-600 text-white py-2 px-4 rounded hover:bg-purple-700"
      >
        {selectedPersona ? 'Login as Persona' : 'Login'}
      </button>
    </form>
  );
}; 