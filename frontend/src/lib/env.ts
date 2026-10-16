export const env = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1',
  wsUrl: import.meta.env.VITE_WS_URL ?? 'ws://localhost:8000/ws',
} as const;
