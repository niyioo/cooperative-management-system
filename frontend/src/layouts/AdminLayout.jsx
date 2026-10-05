import { Suspense, useState } from 'react';
import { Link, NavLink, Outlet } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  ArrowLeftRight,
  BarChart3,
  Bell,
  Briefcase,
  DoorOpen,
  Gift,
  HandCoins,
  History,
  LayoutDashboard,
  LogOut,
  Menu,
  PiggyBank,
  Settings,
  UserRound,
  Users,
  X,
} from 'lucide-react';
import BrandLogo from '../components/brand/BrandLogo';
import { LoadingBlock } from '../components/ui/Spinner';
import { adminApi } from '../api/admin';
import { useAuth } from '../auth/AuthProvider';
import { P, useCan } from '../lib/permissions';

// `perm` may be a list (any of). `badge` picks pending counts from the dashboard's approvals.
const NAV = [
  { to: '/admin', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/admin/members', label: 'Members', icon: Users, perm: P.VIEW_MEMBER },
  { to: '/admin/closures', label: 'Account Closures', icon: DoorOpen, perm: P.VIEW_CLOSURE_REQUESTS, badge: (a) => a.closure_requests },
  { to: '/admin/savings', label: 'Savings', icon: PiggyBank, perm: P.VIEW_SAVINGS },
  {
    to: '/admin/loans', label: 'Loans', icon: HandCoins, perm: P.VIEW_LOANS,
    badge: (a) => (a.applications_to_review || 0) + (a.applications_to_decide || 0) + (a.loans_to_disburse || 0),
  },
  { to: '/admin/investments', label: 'Investments', icon: Briefcase, perm: P.VIEW_INVESTMENTS },
  { to: '/admin/dividends', label: 'Dividends', icon: Gift, perm: P.VIEW_DIVIDENDS },
  {
    to: '/admin/transactions', label: 'Transactions', icon: ArrowLeftRight,
    perm: [P.VIEW_ALL_TRANSACTIONS, P.APPROVE_TRANSACTION, P.MANAGE_BATCHES, P.APPROVE_BATCH],
    badge: (a) => (a.entries || 0) + (a.batches || 0),
  },
  { to: '/admin/reports', label: 'Reports', icon: BarChart3, perm: P.VIEW_REPORTS },
  { to: '/admin/notifications', label: 'Notifications', icon: Bell, perm: [P.MANAGE_ANNOUNCEMENTS, P.SEND_NOTIFICATIONS] },
  { to: '/admin/settings', label: 'Settings', icon: Settings, perm: [P.MANAGE_SETTINGS, P.MANAGE_OFFICERS, P.MANAGE_ROLES] },
  { to: '/admin/audit-logs', label: 'Audit Logs', icon: History, perm: P.VIEW_AUDIT_LOG },
];

function NavItems({ approvals, onNavigate }) {
  const can = useCan();
  return (
    <nav className="space-y-1 px-3" aria-label="Officer portal">
      {NAV.filter((item) => !item.perm || can(item.perm)).map(({ to, label, icon: Icon, end, badge }) => {
        const count = badge && approvals ? badge(approvals) : 0;
        return (
          <NavLink
            key={to}
            to={to}
            end={end}
            onClick={onNavigate}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                isActive ? 'bg-brand-600 text-white' : 'text-slate-300 hover:bg-white/10 hover:text-white'
              }`
            }
          >
            <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
            <span className="flex-1">{label}</span>
            {count > 0 && (
              <span className="rounded-full bg-amber-400 px-1.5 text-[11px] font-bold text-slate-900" aria-label={`${count} awaiting action`}>
                {count}
              </span>
            )}
          </NavLink>
        );
      })}
    </nav>
  );
}

export default function AdminLayout() {
  const { user, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  // The dashboard payload carries the approval counts; shared cache key with the Dashboard page.
  const dashboard = useQuery({ queryKey: ['admin', 'dashboard'], queryFn: adminApi.dashboard, refetchInterval: 60_000 });
  const isMember = user.portals.includes('member');

  const sidebar = (
    <div className="flex h-full flex-col bg-brand-900 py-5">
      <div className="px-5">
        <BrandLogo size={44} layout="horizontal" tone="dark" showInstitute={false} />
      </div>
      <p className="mt-6 px-6 text-xs font-semibold uppercase tracking-wider text-brand-200">Officer portal</p>
      <div className="mt-2 flex-1 overflow-y-auto">
        <NavItems approvals={dashboard.data?.approvals} onNavigate={() => setMenuOpen(false)} />
      </div>
      {isMember && (
        <Link to="/member" className="mx-3 mt-4 flex items-center gap-2 rounded-lg border border-white/20 px-3 py-2 text-sm font-medium text-white hover:bg-white/10">
          <UserRound className="h-4 w-4" aria-hidden="true" /> My member portal
        </Link>
      )}
    </div>
  );

  return (
    <div className="flex min-h-screen bg-slate-50">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2">
        Skip to content
      </a>

      <aside className="no-print hidden w-64 shrink-0 lg:block">
        <div className="sticky top-0 h-screen">{sidebar}</div>
      </aside>

      {menuOpen && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Menu">
          <button type="button" className="absolute inset-0 bg-slate-900/60" onClick={() => setMenuOpen(false)} aria-label="Close menu" />
          <div className="relative h-full w-72 max-w-[85vw]">
            {sidebar}
            <button type="button" onClick={() => setMenuOpen(false)} className="absolute right-3 top-4 rounded p-1 text-white hover:bg-white/10" aria-label="Close menu">
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="no-print sticky top-0 z-30 flex h-16 items-center justify-between gap-3 border-b border-slate-200 bg-white/95 px-4 backdrop-blur sm:px-6">
          <button type="button" className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 lg:hidden" onClick={() => setMenuOpen(true)} aria-label="Open menu">
            <Menu className="h-5 w-5" />
          </button>
          <div className="min-w-0 flex-1 lg:flex-none">
            <p className="truncate text-sm font-semibold text-slate-900">{user.full_name}</p>
            <p className="truncate text-xs text-slate-500">{user.roles.join(' · ') || 'Officer'}</p>
          </div>
          <div className="flex items-center gap-1">
            <Link to="/change-password" className="hidden rounded-lg px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 sm:inline">
              Change password
            </Link>
            <button type="button" onClick={logout} className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100">
              <LogOut className="h-4 w-4" aria-hidden="true" />
              <span className="hidden sm:inline">Sign out</span>
            </button>
          </div>
        </header>

        <main id="main" className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 lg:py-8">
          <Suspense fallback={<LoadingBlock />}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  );
}
