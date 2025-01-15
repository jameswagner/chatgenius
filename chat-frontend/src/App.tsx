import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthPage } from './pages/Auth';
import { ChatLayout } from './components/Chat/ChatLayout';
import { useEffect, useState } from 'react';

// Protected Route component
const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const token = localStorage.getItem('token');
  if (!token) {
    return <Navigate to="/auth" replace />;
  }
  return <>{children}</>;
};

function App() {
  const [isInitialized, setIsInitialized] = useState(false);

  useEffect(() => {
    // Check auth status on app load
    setIsInitialized(true);
  }, []);

  // Add health check route handler
  useEffect(() => {
    const handleHealth = async (e: any) => {
      if (e.request.url.endsWith('/api/health')) {
        e.respondWith(new Response('healthy', { status: 200 }));
      }
    };
    
    window.addEventListener('fetch', handleHealth);
    return () => window.removeEventListener('fetch', handleHealth);
  }, []);

  if (!isInitialized) {
    return null; // or a loading spinner
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/auth" element={<AuthPage />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <ChatLayout />
            </ProtectedRoute>
          }
        />
        <Route path="*" element={<Navigate to="/auth" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
