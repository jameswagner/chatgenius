import { useState } from 'react';
import { LoginForm, RegisterForm } from './';
import { Navigate } from 'react-router-dom';

export const AuthPage = () => {
  const [isLogin, setIsLogin] = useState(true);
  const token = localStorage.getItem('token');

  // Redirect to chat if already logged in
  if (token) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="min-h-screen bg-purple-900 flex items-center justify-center">
      <div className="bg-white p-8 rounded-lg shadow-lg w-full max-w-md">
        <div className="flex justify-center mb-8">
          <h1 className="text-2xl font-bold text-purple-900">
            {isLogin ? 'Welcome Back' : 'Create Account'}
          </h1>
        </div>

        {isLogin ? <LoginForm /> : <RegisterForm />}

        <div className="mt-6 text-center">
          <button
            onClick={() => setIsLogin(!isLogin)}
            className="text-purple-600 hover:text-purple-800"
          >
            {isLogin ? 'Need an account? Register' : 'Already have an account? Login'}
          </button>
        </div>
      </div>
    </div>
  );
}; 