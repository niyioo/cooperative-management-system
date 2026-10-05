/**
 * API client.
 *
 * - The access token lives only in memory (never localStorage), so injected
 *   scripts can't steal a long-lived credential.
 * - The refresh token is an httpOnly cookie the browser sends to /auth/token/refresh/.
 * - Refreshes are single-flight: concurrent 401s share one refresh. Refresh
 *   tokens rotate on every use, so two parallel refreshes would log the user out.
 */
import axios from 'axios';

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1').replace(/\/$/, '');

const XHR = { 'X-Requested-With': 'XMLHttpRequest' };

let accessToken = null;
let refreshInFlight = null;
let sessionExpiredHandler = () => {};

export function setAccessToken(token) {
  accessToken = token;
}

export function onSessionExpired(handler) {
  sessionExpiredHandler = handler;
}

export const api = axios.create({ baseURL: API_BASE_URL, withCredentials: true });

api.interceptors.request.use((config) => {
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`;
  return config;
});

/** Exchange the refresh cookie for a new access token. Resolves to {access, user}. */
export function refreshSession() {
  if (!refreshInFlight) {
    refreshInFlight = axios
      .post(`${API_BASE_URL}/auth/token/refresh/`, null, { withCredentials: true, headers: XHR })
      .then((response) => {
        accessToken = response.data.access;
        return response.data;
      })
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}

const NO_RETRY = ['/auth/login/', '/auth/token/refresh/', '/auth/logout/'];

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const { config, response } = error;
    const retryable = response?.status === 401 && config && !config._retried && !NO_RETRY.some((p) => config.url?.includes(p));
    if (!retryable) return Promise.reject(error);
    config._retried = true;
    try {
      await refreshSession();
    } catch (refreshError) {
      accessToken = null;
      sessionExpiredHandler();
      return Promise.reject(error);
    }
    return api(config);
  },
);

export const authApi = {
  login: (identifier, password) => api.post('/auth/login/', { identifier, password }).then((r) => r.data),
  logout: () => api.post('/auth/logout/', null, { headers: XHR }),
  me: () => api.get('/auth/me/').then((r) => r.data),
  changePassword: (data) => api.post('/auth/password/change/', data).then((r) => r.data),
  requestReset: (email) => api.post('/auth/password/reset/', { email }).then((r) => r.data),
  confirmReset: (data) => api.post('/auth/password/reset/confirm/', data).then((r) => r.data),
  activate: (data) => api.post('/auth/activate/', data).then((r) => r.data),
};
