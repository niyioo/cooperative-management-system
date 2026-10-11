import { Suspense, lazy } from 'react';
import { Navigate, createBrowserRouter, createHashRouter } from 'react-router-dom';
import { GuestOnly, HomeRedirect, RequireAuth, RequirePortal } from '../auth/guards';
import RequirePerm from '../components/officer/RequirePerm';
import { LoadingBlock } from '../components/ui/Spinner';
import AuthLayout from '../layouts/AuthLayout';
import MemberLayout from '../layouts/MemberLayout';
import { P, useCan } from '../lib/permissions';
import ChangePassword from '../pages/auth/ChangePassword';
import ForgotPassword from '../pages/auth/ForgotPassword';
import Login from '../pages/auth/Login';
import SetPassword from '../pages/auth/SetPassword';
import AccountClosure from '../pages/member/AccountClosure';
import ApplicationDetail from '../pages/member/ApplicationDetail';
import ApplyForLoan from '../pages/member/ApplyForLoan';
import Dashboard from '../pages/member/Dashboard';
import Dividends from '../pages/member/Dividends';
import Guarantees from '../pages/member/Guarantees';
import Investments from '../pages/member/Investments';
import LoanDetail from '../pages/member/LoanDetail';
import Loans from '../pages/member/Loans';
import Notifications from '../pages/member/Notifications';
import Profile from '../pages/member/Profile';
import Savings from '../pages/member/Savings';
import Transactions from '../pages/member/Transactions';
import NotFound from '../pages/NotFound';
// The officer portal is one lazy chunk: members never download it.
const officerModule = () => import('../pages/officer');
const officer = (name) => lazy(() => officerModule().then((m) => ({ default: m[name] })));
const AdminLayout = officer('AdminLayout');
const AuditLogs = officer('AuditLogs');
const OfficerNotifications = officer('OfficerNotifications');
const ReportsHome = officer('ReportsHome');
const ReportPage = officer('ReportPage');
const OfficerDashboard = officer('OfficerDashboard');
const ClosureDetail = officer('ClosureDetail');
const ClosureList = officer('ClosureList');
const DividendCycleDetail = officer('DividendCycleDetail');
const DividendCycles = officer('DividendCycles');
const InvestmentAccountDetail = officer('InvestmentAccountDetail');
const InvestmentAccounts = officer('InvestmentAccounts');
const InvestmentProducts = officer('InvestmentProducts');
const InvestmentReturns = officer('InvestmentReturns');
const InvestmentsLayout = officer('InvestmentsLayout');
const LoanApplicationDetail = officer('LoanApplicationDetail');
const LoanApplications = officer('LoanApplications');
const LoansLayout = officer('LoansLayout');
const OfficerLoanDetail = officer('OfficerLoanDetail');
const LoanList = officer('LoanList');
const LoanProducts = officer('LoanProducts');
const OverdueLoans = officer('OverdueLoans');
const MemberDetail = officer('MemberDetail');
const MemberForm = officer('MemberForm');
const MemberImports = officer('MemberImports');
const MemberList = officer('MemberList');
const SavingsAccountDetail = officer('SavingsAccountDetail');
const SavingsAccounts = officer('SavingsAccounts');
const SavingsLayout = officer('SavingsLayout');
const SavingsCycleDetail = officer('SavingsCycleDetail');
const SavingsCycles = officer('SavingsCycles');
const SavingsProducts = officer('SavingsProducts');
const MonthlyDeductions = officer('MonthlyDeductions');
const CooperativeSettings = officer('CooperativeSettings');
const Departments = officer('Departments');
const Officers = officer('Officers');
const Roles = officer('Roles');
const SettingsIndex = officer('SettingsIndex');
const SettingsLayout = officer('SettingsLayout');
const BatchDetail = officer('BatchDetail');
const Batches = officer('Batches');
const Ledger = officer('Ledger');
const PendingEntries = officer('PendingEntries');
const TransactionsLayout = officer('TransactionsLayout');

/** Officers who can approve but not browse the full ledger land on their approval queue. */
function LedgerIndex() {
  const can = useCan();
  if (can(P.VIEW_ALL_TRANSACTIONS)) return <Ledger />;
  if (can(P.APPROVE_TRANSACTION)) return <Navigate to="pending" replace />;
  return <Navigate to="batches" replace />;
}

/** A guarded group: `<RequirePerm>` wrapping child routes. */
const guarded = (perm, children) => ({ element: <RequirePerm perm={perm} />, children });

const officerRoutes = [
  { index: true, element: <OfficerDashboard /> },
  {
    path: 'members',
    ...guarded(P.VIEW_MEMBER, [
      { index: true, element: <MemberList /> },
      { path: 'new', ...guarded(P.ADD_MEMBER, [{ index: true, element: <MemberForm /> }]) },
      { path: 'imports', ...guarded(P.IMPORT_MEMBERS, [{ index: true, element: <MemberImports /> }]) },
      { path: ':id', element: <MemberDetail /> },
      { path: ':id/edit', ...guarded(P.CHANGE_MEMBER, [{ index: true, element: <MemberForm /> }]) },
    ]),
  },
  {
    path: 'closures',
    ...guarded(P.VIEW_CLOSURE_REQUESTS, [
      { index: true, element: <ClosureList /> },
      { path: ':id', element: <ClosureDetail /> },
    ]),
  },
  {
    path: 'savings',
    ...guarded(P.VIEW_SAVINGS, [
      {
        element: <SavingsLayout />,
        children: [
          { index: true, element: <SavingsAccounts /> },
          { path: 'accounts/:id', element: <SavingsAccountDetail /> },
          { path: 'deductions', element: <MonthlyDeductions /> },
          { path: 'cycles', element: <SavingsCycles /> },
          { path: 'cycles/:id', element: <SavingsCycleDetail /> },
          { path: 'products', ...guarded(P.MANAGE_SAVINGS_PRODUCTS, [{ index: true, element: <SavingsProducts /> }]) },
        ],
      },
    ]),
  },
  {
    path: 'loans',
    ...guarded(P.VIEW_LOANS, [
      {
        element: <LoansLayout />,
        children: [
          { index: true, element: <LoanApplications /> },
          { path: 'applications/:id', element: <LoanApplicationDetail /> },
          { path: 'active', element: <LoanList /> },
          { path: 'overdue', element: <OverdueLoans /> },
          { path: 'products', ...guarded(P.MANAGE_LOAN_PRODUCTS, [{ index: true, element: <LoanProducts /> }]) },
          { path: ':id', element: <OfficerLoanDetail /> },
        ],
      },
    ]),
  },
  {
    path: 'investments',
    ...guarded(P.VIEW_INVESTMENTS, [
      {
        element: <InvestmentsLayout />,
        children: [
          { index: true, element: <InvestmentAccounts /> },
          { path: 'accounts/:id', element: <InvestmentAccountDetail /> },
          { path: 'returns', element: <InvestmentReturns /> },
          { path: 'products', ...guarded(P.MANAGE_INVESTMENT_PRODUCTS, [{ index: true, element: <InvestmentProducts /> }]) },
        ],
      },
    ]),
  },
  {
    path: 'dividends',
    ...guarded(P.VIEW_DIVIDENDS, [
      { index: true, element: <DividendCycles /> },
      { path: ':id', element: <DividendCycleDetail /> },
    ]),
  },
  {
    path: 'transactions',
    ...guarded([P.VIEW_ALL_TRANSACTIONS, P.APPROVE_TRANSACTION, P.MANAGE_BATCHES, P.APPROVE_BATCH], [
      {
        element: <TransactionsLayout />,
        children: [
          { index: true, element: <LedgerIndex /> },
          { path: 'pending', ...guarded([P.APPROVE_TRANSACTION, P.VIEW_ALL_TRANSACTIONS], [{ index: true, element: <PendingEntries /> }]) },
          { path: 'batches', ...guarded([P.MANAGE_BATCHES, P.APPROVE_BATCH], [{ index: true, element: <Batches /> }]) },
          { path: 'batches/:id', ...guarded([P.MANAGE_BATCHES, P.APPROVE_BATCH], [{ index: true, element: <BatchDetail /> }]) },
        ],
      },
    ]),
  },
  {
    path: 'reports',
    ...guarded(P.VIEW_REPORTS, [
      { index: true, element: <ReportsHome /> },
      { path: ':key', element: <ReportPage /> },
    ]),
  },
  {
    path: 'notifications',
    ...guarded([P.MANAGE_ANNOUNCEMENTS, P.SEND_NOTIFICATIONS], [{ index: true, element: <OfficerNotifications /> }]),
  },
  {
    path: 'settings',
    ...guarded([P.MANAGE_SETTINGS, P.MANAGE_OFFICERS, P.MANAGE_ROLES], [
      {
        element: <SettingsLayout />,
        children: [
          { index: true, element: <SettingsIndex /> },
          { path: 'cooperative', ...guarded(P.MANAGE_SETTINGS, [{ index: true, element: <CooperativeSettings /> }]) },
          { path: 'departments', ...guarded(P.MANAGE_SETTINGS, [{ index: true, element: <Departments /> }]) },
          { path: 'officers', ...guarded(P.MANAGE_OFFICERS, [{ index: true, element: <Officers /> }]) },
          { path: 'roles', element: <Roles /> },
        ],
      },
    ]),
  },
  { path: 'audit-logs', ...guarded(P.VIEW_AUDIT_LOG, [{ index: true, element: <AuditLogs /> }]) },
  { path: '*', element: <NotFound /> },
];

const routes = [
  { path: '/', element: <HomeRedirect /> },
  {
    element: <AuthLayout />,
    children: [
      {
        element: <GuestOnly />,
        children: [
          { path: '/login', element: <Login /> },
          { path: '/forgot-password', element: <ForgotPassword /> },
        ],
      },
      // Emailed links work whether or not someone is signed in.
      { path: '/reset-password', element: <SetPassword mode="reset" /> },
      { path: '/activate', element: <SetPassword mode="activate" /> },
    ],
  },
  {
    element: <RequireAuth />,
    children: [
      { element: <AuthLayout />, children: [{ path: '/change-password', element: <ChangePassword /> }] },
      {
        element: <RequirePortal portal="member" />,
        children: [
          {
            path: '/member',
            element: <MemberLayout />,
            children: [
              { index: true, element: <Dashboard /> },
              { path: 'savings', element: <Savings /> },
              { path: 'loans', element: <Loans /> },
              { path: 'loans/apply', element: <ApplyForLoan /> },
              { path: 'loans/applications/:id', element: <ApplicationDetail /> },
              { path: 'loans/:id', element: <LoanDetail /> },
              { path: 'investments', element: <Investments /> },
              { path: 'dividends', element: <Dividends /> },
              { path: 'guarantees', element: <Guarantees /> },
              { path: 'transactions', element: <Transactions /> },
              { path: 'closure', element: <AccountClosure /> },
              { path: 'notifications', element: <Notifications /> },
              { path: 'profile', element: <Profile /> },
            ],
          },
        ],
      },
      {
        element: <RequirePortal portal="officer" />,
        children: [
          {
            path: '/admin',
            element: <Suspense fallback={<LoadingBlock label="Loading the officer portal…" />}><AdminLayout /></Suspense>,
            children: officerRoutes,
          },
        ],
      },
    ],
  },
  { path: '*', element: <NotFound /> },
];

// Hash URLs (/#/member) work on static hosts such as GitHub Pages without
// server rewrites. Set VITE_ROUTER=browser when the host rewrites to index.html.
export const router =
  import.meta.env.VITE_ROUTER === 'browser'
    ? createBrowserRouter(routes, { basename: import.meta.env.BASE_URL })
    : createHashRouter(routes);
