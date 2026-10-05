import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { authApi, onSessionExpired, refreshSession, setAccessToken } from '../api/client';

const AuthContext = createContext(null);

/**
 * Session state for the whole app.
 *   status: "loading" while the refresh cookie is checked on start-up,
 *           then "authenticated" or "anonymous".
 */
export function AuthProvider({ children }) {
  const queryClient = useQueryClient();
  const [state, setState] = useState({ status: 'loading', user: null });

  const signedIn = useCallback((data) => {
    setAccessToken(data.access);
    setState({ status: 'authenticated', user: data.user });
    return data.user;
  }, []);

  const signedOut = useCallback(() => {
    setAccessToken(null);
    queryClient.clear();
    setState({ status: 'anonymous', user: null });
  }, [queryClient]);

  // Restore the session from the httpOnly refresh cookie, if there is one.
  useEffect(() => {
    let cancelled = false;
    refreshSession()
      .then((data) => !cancelled && signedIn(data))
      .catch(() => !cancelled && setState({ status: 'anonymous', user: null }));
    return () => {
      cancelled = true;
    };
  }, [signedIn]);

  useEffect(() => onSessionExpired(signedOut), [signedOut]);

  const value = useMemo(
    () => ({
      ...state,
      login: async (identifier, password) => signedIn(await authApi.login(identifier, password)),
      logout: async () => {
        try {
          await authApi.logout();
        } finally {
          signedOut();
        }
      },
      /** After a password change the server issues a fresh session. */
      replaceSession: signedIn,
      reloadUser: async () => {
        const user = await authApi.me();
        setState({ status: 'authenticated', user });
        return user;
      },
    }),
    [state, signedIn, signedOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside <AuthProvider>');
  return context;
}

/** Where a signed-in user belongs: password change first, then their portal. */
export function homePath(user) {
  if (!user) return '/login';
  if (user.must_change_password) return '/change-password';
  if (user.portals.includes('member') && !user.portals.includes('officer')) return '/member';
  if (user.portals.includes('officer')) return '/admin';
  return '/login';
}
