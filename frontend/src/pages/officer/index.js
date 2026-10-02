/**
 * The officer portal, loaded as one lazy chunk so members never download it
 * (or the charting library it uses). See app/router.jsx.
 */
export { default as AdminLayout } from '../../layouts/AdminLayout';
export { default as AuditLogs } from './AuditLogs';
export { default as OfficerNotifications } from './notifications/Notifications';
export { ReportPage, ReportsHome } from './reports/Reports';
export { default as OfficerDashboard } from './Dashboard';
export { ClosureDetail, ClosureList } from './closures/Closures';
export { DividendCycleDetail, DividendCycles } from './dividends/Dividends';
export { InvestmentAccountDetail, InvestmentAccounts, InvestmentProducts, InvestmentReturns, InvestmentsLayout } from './investments/Investments';
export { LoanApplicationDetail, LoanApplications, LoansLayout } from './loans/LoanApplications';
export { LoanDetail as OfficerLoanDetail, LoanList, LoanProducts, OverdueLoans } from './loans/Loans';
export { default as MemberDetail } from './members/MemberDetail';
export { default as MemberForm } from './members/MemberForm';
export { default as MemberImports } from './members/MemberImports';
export { default as MemberList } from './members/MemberList';
export { SavingsAccountDetail, SavingsAccounts, SavingsLayout } from './savings/SavingsAccounts';
export { SavingsCycleDetail, SavingsCycles, SavingsProducts } from './savings/SavingsCycles';
export { CooperativeSettings, Departments, Officers, Roles, SettingsIndex, SettingsLayout } from './settings/Settings';
export { BatchDetail, Batches, Ledger, PendingEntries, TransactionsLayout } from './transactions/Transactions';
