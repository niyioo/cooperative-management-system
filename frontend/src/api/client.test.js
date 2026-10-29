import axios from 'axios';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api, onSessionExpired, refreshSession, setAccessToken } from './client';

/** A fake transport: responds 401 until `token` is presented, then 200. */
function fakeServer(token) {
  const seen = [];
  api.defaults.adapter = async (config) => {
    seen.push(config.headers.Authorization);
    if (config.headers.Authorization === `Bearer ${token}`) {
      return { data: { ok: true, url: config.url }, status: 200, statusText: 'OK', headers: {}, config };
    }
    const error = new Error('Unauthorized');
    error.config = config;
    error.response = { status: 401, data: {}, headers: {}, config };
    throw error;
  };
  return seen;
}

afterEach(() => {
  vi.restoreAllMocks();
  setAccessToken(null);
  onSessionExpired(() => {});
});

describe('API client', () => {
  it('sends the in-memory access token', async () => {
    const seen = fakeServer('abc');
    setAccessToken('abc');
    await api.get('/me/dashboard/');
    expect(seen).toEqual(['Bearer abc']);
  });

  it('shares one refresh between concurrent 401s, then retries each request', async () => {
    fakeServer('fresh');
    setAccessToken('expired');
    const refresh = vi.spyOn(axios, 'post').mockImplementation(
      () => new Promise((resolve) => setTimeout(() => resolve({ data: { access: 'fresh' } }), 10)),
    );
    const results = await Promise.all([api.get('/me/savings/'), api.get('/me/loans/'), api.get('/me/dividends/')]);
    expect(refresh).toHaveBeenCalledTimes(1);
    expect(refresh.mock.calls[0][0]).toMatch(/\/auth\/token\/refresh\/$/);
    expect(refresh.mock.calls[0][2].headers['X-Requested-With']).toBe('XMLHttpRequest');
    expect(results.map((r) => r.data.url)).toEqual(['/me/savings/', '/me/loans/', '/me/dividends/']);
  });

  it('expires the session when the refresh fails, without retrying forever', async () => {
    const seen = fakeServer('never');
    setAccessToken('expired');
    vi.spyOn(axios, 'post').mockRejectedValue(new Error('refresh rejected'));
    const expired = vi.fn();
    onSessionExpired(expired);
    await expect(api.get('/me/savings/')).rejects.toThrow('Unauthorized');
    expect(expired).toHaveBeenCalledTimes(1);
    expect(seen).toHaveLength(1);
  });

  it('never refreshes for the login endpoint itself', async () => {
    fakeServer('never');
    const refresh = vi.spyOn(axios, 'post');
    await expect(api.post('/auth/login/', {})).rejects.toThrow('Unauthorized');
    expect(refresh).not.toHaveBeenCalled();
  });

  it('allows a new refresh after the previous one settles', async () => {
    const refresh = vi.spyOn(axios, 'post').mockResolvedValue({ data: { access: 't' } });
    await refreshSession();
    await refreshSession();
    expect(refresh).toHaveBeenCalledTimes(2);
  });
});
