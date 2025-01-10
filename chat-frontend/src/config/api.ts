const port = import.meta.env.VITE_BACKEND_PORT || 5000;
export const API_BASE_URL = `http://localhost:${port}`;
export const WS_URL = `ws://localhost:${port}`; 