const TONES = {
  green: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
  amber: 'bg-amber-50 text-amber-800 ring-amber-600/20',
  red: 'bg-red-50 text-red-700 ring-red-600/20',
  blue: 'bg-brand-50 text-brand-700 ring-brand-600/20',
  slate: 'bg-slate-100 text-slate-700 ring-slate-500/20',
};

// Status values used across the API, mapped to a colour. The label text always
// accompanies the colour, so colour is never the only signal.
const STATUS_TONES = {
  ACTIVE: 'green', POSTED: 'green', PAID: 'green', COMPLETED: 'green', APPROVED: 'green', DISBURSED: 'green', OPEN: 'green',
  PENDING: 'amber', SUBMITTED: 'amber', UNDER_REVIEW: 'amber', RETURNED: 'amber', PENDING_DISBURSEMENT: 'amber', DUE: 'amber', PARTIAL: 'amber',
  DRAFT: 'slate', REJECTED: 'red', DEFAULTED: 'red', OVERDUE: 'red', SUSPENDED: 'red',
  CLOSED: 'slate', CANCELLED: 'slate', WITHDRAWN: 'slate', REVERSED: 'slate', INACTIVE: 'slate', WITHHELD: 'slate',
  UPCOMING: 'blue', PUBLISHED: 'blue', CALCULATED: 'blue', SCHEDULED: 'blue', ACCEPTED: 'green', DECLINED: 'red',
  LIVE: 'green', ENDED: 'slate',
};

export function Badge({ tone = 'slate', children }) {
  return <span className={`inline-flex items-center whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ring-inset ${TONES[tone]}`}>{children}</span>;
}

export function StatusBadge({ status, label }) {
  const text = label || (status || '').toLowerCase().replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase());
  return <Badge tone={STATUS_TONES[status] || 'slate'}>{text}</Badge>;
}
