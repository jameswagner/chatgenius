const handleSubmit = async (e: React.FormEvent) => {
  e.preventDefault();
  try {
    const response = await api.auth.register(
      formData.name,
      formData.email,
      formData.password
    );
    
    localStorage.setItem('token', response.token);
    localStorage.setItem('userId', response.user_id);
    navigate('/chat');
  } catch (error) {
    console.error('Registration failed:', error);
    // Show error to user
  }
}; 