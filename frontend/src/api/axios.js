import axios from 'axios';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

// The access token lives only in memory, never in localStorage, so a script
// injected into the page can't steal it. The refresh token is an httpOnly
// cookie the browser sends to /auth/ endpoints by itself.
let accessToken = null;
export const tokenStore = {
    get: () => accessToken,
    set: (token) => { accessToken = token; },
    clear: () => { accessToken = null; },
};

export const axiosInstance = axios.create({
    baseURL: BASE_URL,
    headers: { 'Content-Type': 'application/json' },
    withCredentials: true,
    timeout: 20000,
});

axiosInstance.interceptors.request.use((config) => {
    const token = tokenStore.get();
    if (token) config.headers['Authorization'] = `Bearer ${token}`;
    return config;
});

// One refresh at a time: requests that fail together wait for the same one.
let refreshing = null;
export function refreshAccessToken() {
    if (!refreshing) {
        refreshing = axios
            .post(`${BASE_URL}/auth/login/refresh/`, {}, { withCredentials: true, timeout: 15000 })
            .then(({ data }) => { tokenStore.set(data.access); return data.access; })
            .finally(() => { refreshing = null; });
    }
    return refreshing;
}

let onSessionExpired = () => {};
export function setSessionExpiredHandler(handler) { onSessionExpired = handler; }

axiosInstance.interceptors.response.use(
    (response) => response,
    async (error) => {
        const original = error.config;
        const isAuthCall = original?.url?.includes('/auth/login');
        if (error.response?.status === 401 && original && !original._retry && !isAuthCall) {
            original._retry = true;
            try {
                const token = await refreshAccessToken();
                original.headers['Authorization'] = `Bearer ${token}`;
                return axiosInstance(original);
            } catch (refreshError) {
                tokenStore.clear();
                onSessionExpired();
                return Promise.reject(refreshError);
            }
        }
        return Promise.reject(error);
    }
);

export default axiosInstance;
