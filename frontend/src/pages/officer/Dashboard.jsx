import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, Briefcase, ChevronRight, Gift, HandCoins, PiggyBank, Users } from 'lucide-react';
import { adminApi } from '../../api/admin';
import TrendPanel from '../../components/officer/TrendPanel';
import { useAuth } from '../../auth/AuthProvider';
import { Alert } from '../../components/ui/Alert';
import { StatusBadge } from '../../components/ui/Badge';
import { Card, CardBody, CardHeader } from '../../components/ui/Card';
import EmptyState from '../../components/ui/EmptyState';
import PageHeader from '../../components/ui/PageHeader';
import QueryState from '../../components/ui/QueryState';
import StatCard from '../../components/ui/StatCard';
import { Money, Table, Td, Th } from '../../components/ui/Table';
import { formatDate, formatDateTime, formatNaira, formatPeriod } from '../../lib/format';

const APPROVALS = [
  ['entries', 'Transactions awaiting approval', '/admin/transactions/pending'],
  ['batches', 'Batches awaiting approval', '/admin/transactions/batches'],
  ['applications_to_review', 'Loan applications to review', '/admin/loans'],
  ['applications_to_decide', 'Loan applications to decide', '/admin/loans'],
  ['loans_to_disburse', 'Approved loans to disburse', '/admin/loans'],
  ['closure_requests', 'Open account closure requests', '/admin/closures'],
];

const TRENDS = [
  ['savings_contributions', 'Savings contributions'],
  ['loan_disbursements', 'Loan disbursements'],
  ['loan_repayments', 'Loan repayments'],
  ['investment_contributions', 'Investment contributions'],
];

/** This month's statutory monthly contributions: expected, collected so far, and who is behind (BR-29). */
function MonthlyContributions({ m }) {
  const share = Number(m.expected) ? Math.min(100, Math.round((Number(m.collected) / Number(m.expected)) * 100)) : 0;
  return (
    <Card>
      <CardHeader
        title={`Monthly contributions · ${formatPeriod(m.month)}`}
        description="Payroll deductions into Regular Savings"
        action={<Link to="/admin/savings/deductions" className="text-sm font-semibold text-brand-600 hover:underline">Deduction schedule</Link>}
      />
      <CardBody>
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Expected this month</p>
            <p className="tabular mt-1 text-2xl font-bold text-slate-900">{formatNaira(m.expected)}</p>
            <p className="text-xs text-slate-500">{m.members} contributing member(s)</p>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Collected so far</p>
            <p className="tabular mt-1 text-2xl font-bold text-emerald-700">{formatNaira(m.collected)}</p>
            <div className="mt-2 h-2 rounded-full bg-slate-100" role="img" aria-label={`${share}% collected`}>
              <div className="h-2 rounded-full bg-emerald-500" style={{ width: `${share}%` }} />
            </div>
            <p className="mt-1 text-xs text-slate-500">{m.members_paid} of {m.members} member(s) recorded · {share}%</p>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Members in arrears</p>
            <p className={`tabular mt-1 text-2xl font-bold ${m.arrears_members ? 'text-amber-700' : 'text-slate-900'}`}>{m.arrears_members}</p>
            <p className="text-xs text-slate-500">behind on earlier months</p>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Total arrears</p>
            <p className={`tabular mt-1 text-2xl font-bold ${Number(m.arrears_amount) ? 'text-red-700' : 'text-slate-900'}`}>{formatNaira(m.arrears_amount)}</p>
            <Link to="/admin/reports/contribution-arrears" className="text-xs font-semibold text-brand-600 hover:underline">Arrears report</Link>
          </div>
        </div>
      </CardBody>
    </Card>
  );
}

function Approvals({ approvals }) {
  const items = APPROVALS.filter(([key]) => key in approvals);
  if (!items.length) return null;
  return (
    <Card>
      <CardHeader title="Awaiting your action" description="Work queues for your role." />
      <ul className="divide-y divide-slate-100">
        {items.map(([key, label, to]) => (
          <li key={key}>
            <Link to={to} className="flex items-center justify-between gap-3 px-5 py-3 text-sm hover:bg-slate-50">
              <span className="text-slate-700">{label}</span>
              <span className="flex items-center gap-2">
                <span className={`tabular rounded-full px-2 py-0.5 text-xs font-bold ${approvals[key] ? 'bg-amber-100 text-amber-900' : 'bg-slate-100 text-slate-500'}`}>
                  {approvals[key]}
                </span>
                <ChevronRight className="h-4 w-4 text-slate-400" aria-hidden="true" />
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </Card>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const dashboard = useQuery({ queryKey: ['admin', 'dashboard'], queryFn: adminApi.dashboard, refetchInterval: 60_000 });

  return (
    <>
      <PageHeader title={`Welcome, ${user.first_name}`} description="EMDI Cooperative Society at a glance." />
      <QueryState query={dashboard}>
        {(d) => (
          <div className="space-y-6">
            {d.announcements?.length > 0 && (
              <section aria-label="Announcements for officers" className="space-y-2">
                {d.announcements.map((a) => (
                  <Alert key={a.id} tone={a.is_important ? 'warning' : 'info'} title={a.title}>
                    <p className="whitespace-pre-line">{a.body}</p>
                  </Alert>
                ))}
              </section>
            )}
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {d.members && <StatCard label="Members" value={d.members.total} hint={`${d.members.active} active`} icon={Users} />}
              {d.savings && (
                <StatCard label="Total savings" value={formatNaira(d.savings.total)} icon={PiggyBank} tone="green"
                  hint={`Christmas ${d.savings.christmas_year}: ${formatNaira(d.savings.christmas)} · Other: ${formatNaira(d.savings.other)}`} />
              )}
              {d.loans && (
                <StatCard label="Loans outstanding" value={formatNaira(d.loans.outstanding)} icon={HandCoins} tone="amber"
                  hint={`${d.loans.running_count} running loan(s)`} />
              )}
              {d.investments && <StatCard label="Investments" value={formatNaira(d.investments.total)} icon={Briefcase} tone="violet" />}
              {d.dividends && (
                <StatCard label="Dividends payable" value={formatNaira(d.dividends.liability)} icon={Gift} tone="slate"
                  hint={d.dividends.latest_cycle ? `${d.dividends.latest_cycle.financial_year} cycle: ${d.dividends.latest_cycle.status_label}` : 'No dividend cycle yet'} />
              )}
              {d.loans && (
                <StatCard label="Overdue loans" value={d.loans.overdue_count} icon={AlertTriangle} tone={d.loans.overdue_count ? 'amber' : 'slate'}
                  hint={`${formatNaira(d.loans.overdue_amount)} in arrears`} />
              )}
            </div>

            {d.savings?.monthly_contributions && <MonthlyContributions m={d.savings.monthly_contributions} />}

            <div className="grid gap-6 lg:grid-cols-3">
              <div className="space-y-6 lg:col-span-2">
                {d.trends && (
                  <section aria-labelledby="trends-title">
                    <h2 id="trends-title" className="mb-3 text-base font-semibold text-slate-900">Monthly activity</h2>
                    <div className="grid gap-4 sm:grid-cols-2">
                      {TRENDS.filter(([key]) => key in d.trends[0]).map(([key, title]) => (
                        <TrendPanel key={key} title={title} data={d.trends} dataKey={key} />
                      ))}
                    </div>
                  </section>
                )}

                {d.transactions && (
                  <Card>
                    <CardHeader title="Recent transactions" action={<Link to="/admin/transactions" className="text-sm font-semibold text-brand-600 hover:underline">View ledger</Link>} />
                    {d.transactions.recent.length ? (
                      <Table caption="Recent transactions">
                        <thead><tr><Th>Date</Th><Th>Type</Th><Th>Account</Th><Th align="right">Amount</Th><Th>Status</Th></tr></thead>
                        <tbody className="divide-y divide-slate-100">
                          {d.transactions.recent.map((t) => (
                            <tr key={t.id}>
                              <Td className="whitespace-nowrap">{formatDate(t.value_date)}</Td>
                              <Td><p>{t.type_label}</p><p className="text-xs text-slate-500">{t.reference}</p></Td>
                              <Td className="text-xs text-slate-600">{t.account?.label}</Td>
                              <Td align="right"><Money value={t.signed_amount} className={Number(t.signed_amount) < 0 ? 'text-red-700' : ''} /></Td>
                              <Td><StatusBadge status={t.status} label={t.status_label} /></Td>
                            </tr>
                          ))}
                        </tbody>
                      </Table>
                    ) : <EmptyState title="No transactions yet" />}
                  </Card>
                )}
              </div>

              <div className="space-y-6">
                <Approvals approvals={d.approvals} />

                {d.loans && (
                  <Card>
                    <CardHeader title="Overdue loans" action={<Link to="/admin/loans/overdue" className="text-sm font-semibold text-brand-600 hover:underline">All</Link>} />
                    {d.loans.overdue_members.length ? (
                      <ul className="divide-y divide-slate-100">
                        {d.loans.overdue_members.map((o) => (
                          <li key={o.loan_id}>
                            <Link to={`/admin/loans/${o.loan_id}`} className="flex justify-between gap-3 px-5 py-3 text-sm hover:bg-slate-50">
                              <span>
                                <span className="block font-medium text-slate-900">{o.member}</span>
                                <span className="text-xs text-slate-500">{o.reference} · {o.days_overdue} days</span>
                              </span>
                              <Money value={o.arrears} className="font-semibold text-red-700" />
                            </Link>
                          </li>
                        ))}
                      </ul>
                    ) : <EmptyState title="No overdue loans" />}
                  </Card>
                )}

                {d.savings?.contribution_arrears && (
                  <Card>
                    <CardHeader title="Behind on monthly contributions" action={<Link to="/admin/savings/deductions" className="text-sm font-semibold text-brand-600 hover:underline">Deductions</Link>} />
                    {d.savings.contribution_arrears.top.length ? (
                      <ul className="divide-y divide-slate-100">
                        {d.savings.contribution_arrears.top.map((o) => (
                          <li key={o.account_id}>
                            <Link to={`/admin/savings/accounts/${o.account_id}`} className="flex justify-between gap-3 px-5 py-3 text-sm hover:bg-slate-50">
                              <span>
                                <span className="block font-medium text-slate-900">{o.member}</span>
                                <span className="text-xs text-slate-500">{o.membership_number} · about {o.months_behind} month(s)</span>
                              </span>
                              <Money value={o.arrears} className="font-semibold text-red-700" />
                            </Link>
                          </li>
                        ))}
                      </ul>
                    ) : <EmptyState title="Everyone is up to date" />}
                  </Card>
                )}

                {d.loans && (
                  <Card>
                    <CardHeader title="Latest loan applications" />
                    {d.loans.recent_applications.length ? (
                      <ul className="divide-y divide-slate-100">
                        {d.loans.recent_applications.map((a) => (
                          <li key={a.id}>
                            <Link to={`/admin/loans/applications/${a.id}`} className="block px-5 py-3 text-sm hover:bg-slate-50">
                              <span className="flex justify-between gap-2">
                                <span className="font-medium text-slate-900">{a.member}</span>
                                <Money value={a.amount_requested} />
                              </span>
                              <span className="mt-1 flex items-center justify-between gap-2 text-xs text-slate-500">
                                <span>{a.product} · {formatDateTime(a.submitted_at)}</span>
                                <StatusBadge status={a.status} label={a.status_label} />
                              </span>
                            </Link>
                          </li>
                        ))}
                      </ul>
                    ) : <EmptyState title="No applications yet" />}
                  </Card>
                )}
              </div>
            </div>
          </div>
        )}
      </QueryState>
    </>
  );
}
