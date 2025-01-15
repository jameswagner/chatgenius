const isDevelopment = import.meta.env.DEV;

export const API_BASE_URL = isDevelopment 
  ? `http://localhost:5000`
  : `https://chatgenius-production-3f81.up.railway.app`;

export const WS_URL = isDevelopment
  ? `ws://localhost:5000`
  : `wss://chatgenius-production-3f81.up.railway.app`;