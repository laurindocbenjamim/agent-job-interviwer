export const getApiUrl = () => {
  if (import.meta.env.VITE_API_URL) {
    return import.meta.env.VITE_API_URL;
  }
  const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
  // If no env var is set, fallback to localhost:8000 for local dev, 
  // or use the current origin in production (assuming they are hosted on the same domain)
  // If backend is on a different domain, VITE_API_URL MUST be set in Render.
  return isLocalhost ? 'http://localhost:8000' : window.location.origin;
};

export const getWsUrl = () => {
  if (import.meta.env.VITE_WS_URL) {
    return import.meta.env.VITE_WS_URL;
  }
  const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
  if (isLocalhost) {
    return 'ws://localhost:8000';
  }
  // If no VITE_WS_URL is set, derive it from the current location
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}`;
};

export const API_BASE_URL = getApiUrl();
export const WS_BASE_URL = getWsUrl();
