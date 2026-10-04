import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Download, FileWarning } from 'lucide-react';
import { adminApi } from '../../../api/admin';
import FormModal from '../../../components/officer/FormModal';
import ContributionHistory from '../../../components/savings/ContributionHistory';
import { Alert, ErrorAlert } from '../../../components/ui/Alert';
import Button from '../../../components/ui/Button';
import { Card, CardBody, CardHeader } from '../../../components/ui/Card';
import EmptyState from '../../../components/ui/EmptyState';
import { CheckboxField, TextField } from '../../../components/ui/Field';
import QueryState from '../../../components/ui/QueryState';
import StatCard from '../../../components/ui/StatCard';
import { Money, Table, Td, Th } from '../../../components/ui/Table';
import { currentPeriod } from '../../../lib/choices';
import { saveBlob } from '../../../lib/download';
import { formatDate, formatNaira, formatPeriod } from '../../../lib/format';
import { P, useCan } from '../../../lib/permissions';

/** The payroll (IPPIS) deduction schedule for the statutory monthly contribution (BR-29). */
export function MonthlyDeductions() {
  const can = useCan();
  const [period, setPeriod] = useState(currentPeriod());
  const [includeArrears, setIncludeArrears] = useState(true);
  const params = { period, include_arrears: includeArrears };
  const schedule = useQuery({ queryKey: ['admin', 'deduction-schedule', params], queryFn: () => adminApi.deductionSchedule(params), enabled: !!period });
  const download = useMutation({ mutationFn: () => adminApi.downloadDeductionSchedule(params), onSuccess: (r) => saveBlob(r, `emdi-deductions-${period}.xlsx`) });

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader
          title="Monthly deduction schedule"
          description="What payroll should deduct from each member for the monthly contribution. The file uses the Contributions batch layout, so once payroll has deducted, upload the same sheet under Transactions › Batches."
        />
        <CardBody className="flex flex-wrap items-end gap-4">
          <div className="w-44"><TextField label="Payroll month" type="month" value={period} onChange={(e) => setPeriod(e.target.value)} /></div>
          <CheckboxField label="Add each member's arrears to the deduction" checked={includeArrears} onChange={(e) => setIncludeArrears(e.target.checked)} />
          <div className="ml-auto flex flex-wrap gap-2">
            <Link to="/admin/reports/contribution-arrears" className="inline-flex items-center gap-1 rounded-lg px-3 py-2 text-sm font-semibold text-brand-600 hover:bg-brand-50">
              <FileWarning className="h-4 w-4" aria-hidden="true" /> Arrears report
            </Link>
            {can(P.POST_SAVINGS_CONTRIBUTION) && (
              <Button icon={Download} loading={download.isPending} onClick={() => download.mutate()} disabled={!schedule.data?.rows.length}>
                Download for payroll (.xlsx)
              </Button>
            )}
          </div>
        </CardBody>
        <ErrorAlert error={download.error} className="mx-5 mb-4" />
      </Card>

      <QueryState query={schedule}>
        {(data) => (
          <>
            {data.include_arrears === false && includeArrears && (
              <Alert tone="info">{formatPeriod(data.period)} has passed, so arrears are not added; they go on the current month&apos;s schedule.</Alert>
            )}
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <StatCard label="Members to deduct" value={data.totals.members} tone="slate" hint={`${data.product.name} · minimum ${formatNaira(data.product.minimum)}`} />
              <StatCard label="Monthly contributions" value={formatNaira(data.totals.monthly)} />
              <StatCard label="Arrears added" value={formatNaira(data.totals.arrears)} tone="amber" />
              <StatCard label="Total to deduct" value={formatNaira(data.totals.amount)} tone="green"
                hint={data.totals.already_recorded ? `${data.totals.already_recorded} already recorded for ${formatPeriod(data.period)}, left out` : undefined} />
            </div>
            <Card>
              <CardHeader title={`Deductions for ${formatPeriod(data.period)}`} description={`Reference ${data.reference}`} />
              {data.rows.length ? (
                <Table caption={`Deductions for ${formatPeriod(data.period)}`}>
                  <thead>
                    <tr><Th>Member</Th><Th>Staff / IPPIS no.</Th><Th>Department</Th><Th align="right">Monthly</Th><Th align="right">Arrears</Th><Th align="right">Deduct</Th></tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {data.rows.map((r) => (
                      <tr key={r.account_id} className="hover:bg-slate-50">
                        <Td>
                          <Link to={`/admin/savings/accounts/${r.account_id}`} className="font-medium text-brand-600 hover:underline">{r.name}</Link>
                          <p className="text-xs text-slate-500">{r.membership_number}</p>
                        </Td>
                        <Td className="text-xs text-slate-600">{r.staff_number || '—'}<br />{r.ippis_number || '—'}</Td>
                        <Td>{r.department || '—'}</Td>
                        <Td align="right"><Money value={r.monthly} /></Td>
                        <Td align="right">{Number(r.arrears) ? <Money value={r.arrears} className="text-red-700" /> : <span className="text-slate-400">—</span>}</Td>
                        <Td align="right"><Money value={r.amount} className="font-semibold" /></Td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              ) : (
                <EmptyState title="Nothing to deduct for this month">Every member's contribution for the month is already recorded, or no member has a monthly amount.</EmptyState>
              )}
            </Card>
          </>
        )}
      </QueryState>
    </div>
  );
}

/** The statutory monthly contribution on an account page; renders nothing for other accounts. */
export function MonthlyContributionPanel({ account }) {
  const { id } = useParams();
  const can = useCan();
  const query = useQuery({ queryKey: ['admin', 'savings-account', id, 'monthly-contribution'], queryFn: () => adminApi.savingsAccounts.sub(id, 'monthly-contribution'), retry: false });
  if (query.isError && query.error?.response?.status === 404) return null;

  return (
    <QueryState query={query}>
      {(data) => {
        const behind = Number(data.arrears) > 0;
        return (
          <Card>
            <CardHeader
              title="Monthly contribution"
              description={`Deducted through payroll · minimum ${formatNaira(data.minimum)} · tracked from ${formatPeriod(data.tracked_from)}`}
              action={can(P.POST_SAVINGS_CONTRIBUTION) && data.tracked && <ChangeAmountButton account={account} data={data} />}
            />
            <CardBody className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-4">
                <Figure label="This month" value={formatNaira(data.amount)} />
                <Figure label="Expected so far" value={formatNaira(data.expected_total)} hint={`${data.months_due} month${data.months_due === 1 ? '' : 's'} due`} />
                <Figure label="Paid" value={formatNaira(data.paid_total)} />
                <Figure label="Arrears" value={behind ? formatNaira(data.arrears) : 'None'} tone={behind ? 'text-red-700' : 'text-emerald-700'}
                  hint={behind ? `About ${data.months_behind} month${data.months_behind === 1 ? '' : 's'} behind` : undefined} />
              </div>
              {!data.tracked && <Alert tone="info">Arrears are not counted while the account is not active or the member is inactive or closed.</Alert>}
              {data.pending_change && (
                <Alert tone="info">Changes to <strong>{formatNaira(data.pending_change.amount)}</strong> from {formatPeriod(data.pending_change.effective_from)}.</Alert>
              )}
              {data.changes.length > 0 && (
                <div>
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Amount history</p>
                  <ul className="space-y-1 text-sm">
                    {data.changes.map((c) => (
                      <li key={`${c.effective_from}-${c.created_at}`} className="flex flex-wrap justify-between gap-2">
                        <span><span className="tabular font-semibold">{formatNaira(c.amount)}</span> from {formatPeriod(c.effective_from)}{c.reason ? ` · ${c.reason}` : ''}</span>
                        <span className="text-xs text-slate-500">set {formatDate(c.created_at)}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </CardBody>
            <ContributionHistory history={data.history} caption="Last 12 months" />
          </Card>
        );
      }}
    </QueryState>
  );
}

function Figure({ label, value, hint, tone = 'text-slate-900' }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className={`tabular mt-1 text-xl font-bold ${tone}`}>{value}</p>
      {hint && <p className="text-xs text-slate-500">{hint}</p>}
    </div>
  );
}

function ChangeAmountButton({ account, data }) {
  return (
    <FormModal trigger="Change amount" triggerVariant="secondary" triggerSize="sm" title={`Monthly contribution · ${account.account_number}`} submitLabel="Save"
      defaultValues={{ amount: '', effective_from: currentPeriod(), reason: '' }}
      onSubmit={(v) => adminApi.savingsAccounts.action(account.id, 'monthly-contribution', v)}
      renderFields={({ register, errors }) => (
        <>
          <p className="text-sm text-slate-600">
            {account.member.full_name} contributes {formatNaira(data.amount)} a month now. The member is told of the change in the portal and by e-mail.
          </p>
          <TextField label="New monthly amount (₦)" required inputMode="decimal"
            hint={data.maximum ? `Between ${formatNaira(data.minimum)} and ${formatNaira(data.maximum)}.` : `At least ${formatNaira(data.minimum)}.`}
            {...register('amount', { required: 'Enter an amount.' })} error={errors.amount?.message} />
          <TextField label="From month" type="month" min={currentPeriod()} {...register('effective_from')} error={errors.effective_from?.message}
            hint="This month or later. A later change already scheduled is replaced." />
          <TextField label="Reason" {...register('reason')} error={errors.reason?.message} hint="e.g. the member's written request" />
        </>
      )} />
  );
}
