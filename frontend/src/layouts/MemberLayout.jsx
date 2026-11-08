import { useState } from 'react';
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  ArrowLeftRight,
  Bell,
  Briefcase,
  DoorOpen,
  FilePlus2,
  Gift,
  HandCoins,
  Handshake,
  LayoutDashboard,
  LogOut,
  Menu,
  PiggyBank,
  ShieldCheck,
  UserRound,
  X,
} from 'lucide-react';
import BrandLogo from '../components/brand/BrandLogo';
import { memberApi } from '../api/member';
import { useAuth } from '../auth/AuthProvider';

const NAV = [
  { to: '/member', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/member/savings', label: 'My Savings', icon: PiggyBank },
  { to: '/member/loans', label: 'My Loans', icon: HandCoins, end: true },
  { to: '/member/investments', label: 'My Investments', icon: Briefcase },
  { to: '/member/dividends', label: 'My Dividends', icon: Gift },
  { to: '/member/transactions', label: 'Transactions', icon: ArrowLeftRight },
  { to: '/member/loans/apply', label: 'Apply for Loan', icon: FilePlus2 },
  { to: '/member/guarantees', label: 'Guarantees', icon: Handshake, badge: 'guarantees' },
  { to: '/member/closure', label: 'Account Closure', icon: DoorOpen },
  { to: '/member/notifications', label: 'Notifications', icon: Bell },
  { to: '/member/profile', label: 'Profile', icon: UserRound },
];

function NavItems({ onNavigate, counts = {} }) {
  return (
    <nav className="space-y-1 px-3" aria-label="Member portal">
      {NAV.map(({ to, label, icon: Icon, end, badge }) => (
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
          {badge && counts[badge] > 0 && (
            <span className="rounded-full bg-amber-400 px-1.5 text-[11px] font-bold text-slate-900" aria-label={`${counts[badge]} waiting`}>{counts[badge]}</span>
          )}
        </NavLink>
      ))}
    </nav>
  );
}

export default function MemberLayout() {
  const { user, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();
  const unread = useQuery({ queryKey: ['me', 'unread'], queryFn: memberApi.unreadCount, refetchInterval: 60_000 });
  const guarantees = useQuery({
    queryKey: ['me', 'guarantee-requests', 'awaiting'],
    queryFn: () => memberApi.guaranteeRequests({ awaiting: 'true', page_size: 1 }),
    refetchInterval: 60_000,
  });
  const isOfficer = user.portals.includes('officer');

  const sidebar = (
    <div className="flex h-full flex-col bg-brand-900 py-5">
      <div className="px-5">
        <BrandLogo size={44} layout="horizontal" tone="dark" showInstitute={false} />
      </div>
      <p className="mt-6 px-6 text-xs font-semibold uppercase tracking-wider text-brand-200">Member portal</p>
      <div className="mt-2 flex-1 overflow-y-auto">
        <NavItems onNavigate={() => setMenuOpen(false)} counts={{ guarantees: guarantees.data?.count }} />
      </div>
      {isOfficer && (
        <Link to="/admin" className="mx-3 mt-4 flex items-center gap-2 rounded-lg border border-white/20 px-3 py-2 text-sm font-medium text-white hover:bg-white/10">
          <ShieldCheck className="h-4 w-4" aria-hidden="true" /> Officer portal
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
            <p className="truncate text-xs text-slate-500">{user.member?.membership_number}</p>
          </div>
          <div className="flex items-center gap-1">
            <Link to="/member/notifications" className="relative rounded-lg p-2 text-slate-600 hover:bg-slate-100" aria-label={`Notifications${unread.data?.unread ? `, ${unread.data.unread} unread` : ''}`}>
              <Bell className="h-5 w-5" />
              {unread.data?.unread > 0 && (
                <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-bold text-white">
                  {unread.data.unread}
                </span>
              )}
            </Link>
            <button type="button" onClick={logout} className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100">
              <LogOut className="h-4 w-4" aria-hidden="true" />
              <span className="hidden sm:inline">Sign out</span>
            </button>
          </div>
        </header>

        <main id="main" key={location.pathname} className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6 lg:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
