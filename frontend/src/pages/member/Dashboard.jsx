import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Briefcase, CalendarCheck, CalendarClock, Gift, HandCoins, Landmark, Megaphone, PiggyBank, TreePine, Wallet } from 'lucide-react';
import { memberApi } from '../../api/member';
import { Alert } from '../../components/ui/Alert';
import { StatusBadge } from '../../components/ui/Badge';
import { Card, CardBody, CardHeader } from '../../components/ui/Card';
import EmptyState from '../../components/ui/EmptyState';
import QueryState from '../../components/ui/QueryState';
import StatCard from '../../components/ui/StatCard';
import { Money, Table, Td, Th } from '../../components/ui/Table';
import { formatDate, formatNaira, formatPeriod } from '../../lib/format';

export default function Dashboard() {
  const query = useQuery({ queryKey: ['me', 'dashboard'], queryFn: memberApi.dashboard });
  return <QueryState query={query}>{(data) => <DashboardView data={data} />}</QueryState>;
}

function MonthlyContributionPanel({ monthly }) {
  const behind = Number(monthly.arrears) > 0;
  return (
    <div className={`rounded-xl border p-5 ${behind ? 'border-amber-200 bg-amber-50' : 'border-emerald-200 bg-emerald-50'}`}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <span className={`rounded-lg p-2 ${behind ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'}`}>
            <CalendarCheck className="h-5 w-5" aria-hidden="true" />
          </span>
          <div>
            <p className="text-sm font-semibold text-slate-800">Monthly contribution</p>
            <p className="tabular text-2xl font-bold text-slate-900">
              {formatNaira(monthly.amount)} <span className="text-sm font-medium text-slate-500">a month · deducted from pay into Regular Savings</span>
            </p>
            <p className="mt-1 text-sm text-slate-600">
              Minimum {formatNaira(monthly.minimum)}
              {monthly.pending_change && <> · changes to <strong>{formatNaira(monthly.pending_change.amount)}</strong> from {formatPeriod(monthly.pending_change.effective_from)}</>}
            </p>
          </div>
        </div>
        <div className="text-right">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Arrears</p>
          <p className={`tabular text-2xl font-bold ${behind ? 'text-amber-800' : 'text-emerald-700'}`}>{behind ? formatNaira(monthly.arrears) : 'Up to date'}</p>
          {behind && <p className="text-xs text-amber-800">About {monthly.months_behind} month{monthly.months_behind === 1 ? '' : 's'} behind</p>}
          <Link to="/member/savings" className="mt-1 inline-block text-sm font-semibold text-brand-600 hover:underline">View or change</Link>
        </div>
      </div>
    </div>
  );
}

function DashboardView({ data }) {
  const { member, summary, upcoming_repayment: upcoming, loan_applications: applications, recent_transactions: recent } = data;
  const dividend = summary.latest_dividend;
  const monthly = data.monthly_contribution;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-brand-600">Welcome back</p>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">WELCOME, {member.full_name.toUpperCase()}</h1>
          <p className="mt-1 text-sm text-slate-500">
            Membership number <span className="font-semibold text-slate-700">{member.membership_number}</span> · Member since {formatDate(member.date_joined)}
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm text-slate-500">
          Account status <StatusBadge status={member.status} label={member.status_label} />
        </div>
      </div>

      {data.closure_request && (
        <Alert tone="info" title="Account closure request in progress">
          Your request {data.closure_request.reference} is {data.closure_request.status_label.toLowerCase()}.{' '}
          <Link to="/member/closure" className="font-semibold underline">View request</Link>
        </Alert>
      )}

      {monthly && <MonthlyContributionPanel monthly={monthly} />}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label={`Christmas Savings ${summary.christmas_year}`} value={formatNaira(summary.christmas_savings)} icon={TreePine} tone="green" hint="January – October" />
        <StatCard label="Other Savings" value={formatNaira(summary.other_savings)} icon={PiggyBank} />
        <StatCard label="Total Savings" value={formatNaira(summary.total_savings)} icon={Wallet} tone="slate" />
        <StatCard label="Active Loan" value={formatNaira(summary.active_loan_principal)} icon={HandCoins} tone="amber"
          hint={summary.active_loans ? `${summary.active_loans} running loan${summary.active_loans > 1 ? 's' : ''}` : 'No running loan'} />
        <StatCard label="Outstanding Loan" value={formatNaira(summary.outstanding_loan)} icon={Landmark} tone="amber" hint="Principal and interest still owed" />
        <StatCard label="Investment" value={formatNaira(summary.investment)} icon={Briefcase} tone="violet" />
        <StatCard label="Dividend" value={dividend ? formatNaira(dividend.net_amount) : '—'} icon={Gift} tone="green"
          hint={dividend ? `${dividend.financial_year} · ${dividend.status.toLowerCase()}` : 'No dividend published yet'} />
        <div className="flex flex-col justify-between rounded-xl border border-brand-100 bg-brand-50 p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-brand-800">
            <CalendarClock className="h-4 w-4" aria-hidden="true" /> Upcoming repayment
          </div>
          {upcoming ? (
            <div className="mt-2">
              <p className="tabular text-2xl font-bold text-brand-900">{formatNaira(upcoming.remaining)}</p>
              <p className="text-xs text-brand-700">
                Due {formatDate(upcoming.due_date)} · {upcoming.loan_reference}
              </p>
            </div>
          ) : (
            <p className="mt-2 text-sm text-brand-700">Nothing due.</p>
          )}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader title="Recent transactions" action={<Link to="/member/transactions" className="text-sm font-semibold text-brand-600 hover:underline">View all</Link>} />
          {recent.length ? (
            <Table caption="Recent transactions">
              <thead>
                <tr><Th>Date</Th><Th>Description</Th><Th align="right">Amount</Th><Th>Status</Th></tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {recent.map((t) => (
                  <tr key={t.id}>
                    <Td className="whitespace-nowrap">{formatDate(t.value_date)}</Td>
                    <Td>
                      <p className="font-medium text-slate-800">{t.type_label}</p>
                      <p className="text-xs text-slate-500">{t.reference}</p>
                    </Td>
                    <Td align="right">
                      <Money value={t.amount} className={t.entry_side === 'CREDIT' ? 'text-emerald-700' : 'text-slate-800'} />
                    </Td>
                    <Td><StatusBadge status={t.status} label={t.status_label} /></Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          ) : (
            <EmptyState title="No transactions yet" />
          )}
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader title="Loan applications" action={<Link to="/member/loans/apply" className="text-sm font-semibold text-brand-600 hover:underline">Apply</Link>} />
            <CardBody>
              {applications.length ? (
                <ul className="space-y-3">
                  {applications.map((a) => (
                    <li key={a.id} className="flex items-center justify-between gap-3">
                      <Link to={`/member/loans/applications/${a.id}`} className="min-w-0">
                        <p className="truncate text-sm font-medium text-slate-800 hover:underline">{a.product} · {formatNaira(a.amount_requested)}</p>
                        <p className="text-xs text-slate-500">{a.reference}</p>
                      </Link>
                      <StatusBadge status={a.status} label={a.status_label} />
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-slate-500">No application in progress.</p>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Announcements" />
            <CardBody>
              {data.announcements.length ? (
                <ul className="space-y-4">
                  {data.announcements.map((a) => (
                    <li key={a.id}>
                      <p className="flex items-center gap-2 text-sm font-semibold text-slate-800">
                        {a.is_important && <Megaphone className="h-4 w-4 text-amber-600" aria-label="Important" />}
                        {a.title}
                      </p>
                      <p className="mt-1 text-sm text-slate-600">{a.body}</p>
                      <p className="mt-1 text-xs text-slate-400">{formatDate(a.publish_at)}</p>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-slate-500">No announcements.</p>
              )}
            </CardBody>
          </Card>
        </div>
      </div>
    </div>
  );
}
