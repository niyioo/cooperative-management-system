import { useAuth } from '../auth/AuthProvider';

/** Permission codes, mirrored from backend apps/accounts/perms.py. */
export const P = {
  MANAGE_OFFICERS: 'accounts.manage_officers',
  MANAGE_ROLES: 'accounts.manage_roles',
  MANAGE_SETTINGS: 'configuration.manage_settings',
  VIEW_AUDIT_LOG: 'audit.view_audit_log',
  VIEW_MEMBER: 'members.view_member',
  ADD_MEMBER: 'members.add_member',
  CHANGE_MEMBER: 'members.change_member',
  IMPORT_MEMBERS: 'members.import_members',
  CHANGE_MEMBER_STATUS: 'members.change_member_status',
  MANAGE_MEMBER_DOCUMENTS: 'members.manage_member_documents',
  VIEW_SAVINGS: 'savings.view_savings',
  MANAGE_SAVINGS_PRODUCTS: 'savings.manage_savings_products',
  MANAGE_SAVINGS_CYCLES: 'savings.manage_savings_cycles',
  CLOSE_SAVINGS_CYCLE: 'savings.close_savings_cycle',
  POST_SAVINGS_CONTRIBUTION: 'savings.post_savings_contribution',
  POST_SAVINGS_WITHDRAWAL: 'savings.post_savings_withdrawal',
  VIEW_LOANS: 'loans.view_loans',
  MANAGE_LOAN_PRODUCTS: 'loans.manage_loan_products',
  REVIEW_LOAN_APPLICATION: 'loans.review_loan_application',
  APPROVE_LOAN_APPLICATION: 'loans.approve_loan_application',
  DISBURSE_LOAN: 'loans.disburse_loan',
  RECORD_LOAN_REPAYMENT: 'loans.record_loan_repayment',
  MARK_LOAN_DEFAULT: 'loans.mark_loan_default',
  VIEW_INVESTMENTS: 'investments.view_investments',
  MANAGE_INVESTMENT_PRODUCTS: 'investments.manage_investment_products',
  MANAGE_INVESTMENT_ACCOUNTS: 'investments.manage_investment_accounts',
  POST_INVESTMENT_TRANSACTION: 'investments.post_investment_transaction',
  VIEW_DIVIDENDS: 'dividends.view_dividends',
  MANAGE_DIVIDEND_CYCLES: 'dividends.manage_dividend_cycles',
  CALCULATE_DIVIDENDS: 'dividends.calculate_dividends',
  APPROVE_DIVIDENDS: 'dividends.approve_dividends',
  PAY_DIVIDENDS: 'dividends.pay_dividends',
  VIEW_ALL_TRANSACTIONS: 'ledger.view_all_transactions',
  APPROVE_TRANSACTION: 'ledger.approve_transaction',
  REVERSE_TRANSACTION: 'ledger.reverse_transaction',
  POST_ADJUSTMENT: 'ledger.post_adjustment',
  MANAGE_BATCHES: 'ledger.manage_batches',
  APPROVE_BATCH: 'ledger.approve_batch',
  VIEW_CLOSURE_REQUESTS: 'closures.view_closure_requests',
  REVIEW_CLOSURE_REQUEST: 'closures.review_closure_request',
  APPROVE_CLOSURE_REQUEST: 'closures.approve_closure_request',
  EXECUTE_ACCOUNT_CLOSURE: 'closures.execute_account_closure',
  VIEW_REPORTS: 'reports.view_reports',
  EXPORT_REPORTS: 'reports.export_reports',
  MANAGE_ANNOUNCEMENTS: 'notifications.manage_announcements',
  SEND_NOTIFICATIONS: 'notifications.send_notifications',
};

/**
 * can(perm) or can([perm, perm]) -> true if the officer holds any of them.
 * Hiding a button is a convenience only; the server enforces every permission.
 */
export function useCan() {
  const { user } = useAuth();
  const held = new Set(user?.permissions || []);
  return (perms) => (Array.isArray(perms) ? perms.some((p) => held.has(p)) : held.has(perms));
}

export function Can({ perm, children, fallback = null }) {
  const can = useCan();
  return can(perm) ? children : fallback;
}
