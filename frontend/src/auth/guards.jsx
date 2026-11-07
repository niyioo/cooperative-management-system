import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { FullPageSpinner } from '../components/ui/Spinner';
import { homePath, useAuth } from './AuthProvider';

/**
 * Route guards decide what to *show*; the server still enforces every rule.
 * A member who forced their way to an officer URL would get only 403s.
 */
export function RequireAuth() {
  const { status, user } = useAuth();
  const location = useLocation();
  if (status === 'loading') return <FullPageSpinner />;
  if (status === 'anonymous') return <Navigate to="/login" replace state={{ from: location }} />;
  if (user.must_change_password && location.pathname !== '/change-password') return <Navigate to="/change-password" replace />;
  return <Outlet />;
}

export function RequirePortal({ portal }) {
  const { user } = useAuth();
  if (!user.portals.includes(portal)) return <Navigate to={homePath(user)} replace />;
  return <Outlet />;
}

export function GuestOnly() {
  const { status, user } = useAuth();
  if (status === 'loading') return <FullPageSpinner />;
  if (status === 'authenticated') return <Navigate to={homePath(user)} replace />;
  return <Outlet />;
}

export function HomeRedirect() {
  const { status, user } = useAuth();
  if (status === 'loading') return <FullPageSpinner />;
  return <Navigate to={homePath(user)} replace />;
}
