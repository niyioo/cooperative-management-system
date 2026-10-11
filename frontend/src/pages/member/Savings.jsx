import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CalendarClock, Info, TreePine } from 'lucide-react';
import { memberApi } from '../../api/member';
import ContributionHistory from '../../components/savings/ContributionHistory';
import { Alert, ErrorAlert } from '../../components/ui/Alert';
import { StatusBadge } from '../../components/ui/Badge';
import { Card, CardBody, CardHeader } from '../../components/ui/Card';
import Button from '../../components/ui/Button';
import EmptyState from '../../components/ui/EmptyState';
import Modal from '../../components/ui/Modal';
import PageHeader from '../../components/ui/PageHeader';
import Pagination from '../../components/ui/Pagination';
import QueryState from '../../components/ui/QueryState';
import { SelectField, TextField } from '../../components/ui/Field';
import { Money, Table, Td, Th } from '../../components/ui/Table';
import { applyFieldErrors } from '../../lib/errors';
import { formatDate, formatNaira, formatPeriod, monthLabel } from '../../lib/format';

export default function Savings() {
  const savings = useQuery({ queryKey: ['me', 'savings'], queryFn: memberApi.savings });
  return (
    <div className="space-y-6">
      <PageHeader title="My Savings" description="Your monthly contribution, Christmas Savings and other savings, kept separately." />
      <Alert tone="info">
        Savings are shown for your information. Withdrawals are not available through the portal; speak to the cooperative office about your savings.
      </Alert>
      <MonthlyContribution />
      <ChristmasSavings />
      <QueryState query={savings}>
        {(data) => (
          <>
            <OtherSavings other={data.other} />
            <Card>
              <CardBody className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-slate-700">Total savings</p>
                  <p className="text-xs text-slate-500">Christmas Savings for {data.christmas.year} plus all other savings, for information.</p>
                </div>
                <p className="tabular text-2xl font-bold text-slate-900">{formatNaira(data.total)}</p>
              </CardBody>
            </Card>
          </>
        )}
      </QueryState>
    </div>
  );
}

function MonthlyContribution() {
  const query = useQuery({ queryKey: ['me', 'monthly-contribution'], queryFn: memberApi.monthlyContribution, retry: false });
  const [showHistory, setShowHistory] = useState(false);
  if (query.isError && query.error?.response?.status === 404) return null;

  return (
    <QueryState query={query}>
      {(data) => {
        const behind = Number(data.arrears) > 0;
        return (
          <Card>
            <CardHeader
              title="Monthly contribution"
              description={`Deducted from your pay each month into ${data.product} (account ${data.account_number})`}
              action={data.tracked && <ChangeMonthlyContribution data={data} />}
            />
            <CardBody className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">This month</p>
                  <p className="tabular mt-1 text-2xl font-bold text-slate-900">{formatNaira(data.amount)}</p>
                  <p className="text-xs text-slate-500">Minimum {formatNaira(data.minimum)}</p>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Arrears</p>
                  <p className={`tabular mt-1 text-2xl font-bold ${behind ? 'text-red-700' : 'text-emerald-700'}`}>{behind ? formatNaira(data.arrears) : 'None'}</p>
                  <p className="text-xs text-slate-500">
                    {behind ? `About ${data.months_behind} month${data.months_behind === 1 ? '' : 's'} behind` : 'You are up to date'} · since {formatPeriod(data.tracked_from)}
                  </p>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Paid since {formatPeriod(data.tracked_from)}</p>
                  <p className="tabular mt-1 text-2xl font-bold text-slate-900">{formatNaira(data.paid_total)}</p>
                  <p className="text-xs text-slate-500">of {formatNaira(data.expected_total)} expected</p>
                </div>
              </div>
              {data.pending_change && (
                <Alert tone="info">
                  Your monthly contribution changes to <strong>{formatNaira(data.pending_change.amount)}</strong> from {formatPeriod(data.pending_change.effective_from)}.
                </Alert>
              )}
              {behind && (
                <Alert tone="warning">
                  Your contributions are {formatNaira(data.arrears)} short. The cooperative may add arrears to a coming payroll deduction; speak to the cooperative office if this looks wrong.
                </Alert>
              )}
              <button type="button" className="text-sm font-medium text-brand-600 hover:underline" onClick={() => setShowHistory(!showHistory)} aria-expanded={showHistory}>
                {showHistory ? 'Hide month by month' : 'Show month by month'}
              </button>
            </CardBody>
            {showHistory && <ContributionHistory history={data.history} caption="Monthly contribution, month by month" />}
          </Card>
        );
      }}
    </QueryState>
  );
}

function ChangeMonthlyContribution({ data }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const { register, handleSubmit, setError, reset, formState: { errors } } = useForm({ defaultValues: { amount: '' } });
  const mutation = useMutation({
    mutationFn: (values) => memberApi.changeMonthlyContribution(values.amount),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['me'] });
      setOpen(false);
    },
    onError: (error) => applyFieldErrors(error, setError),
  });
  const submit = handleSubmit((values) => mutation.mutate(values));

  return (
    <>
      <Button size="sm" variant="secondary" icon={CalendarClock} onClick={() => { mutation.reset(); reset({ amount: '' }); setOpen(true); }}>
        Change amount
      </Button>
      <Modal open={open} onClose={() => setOpen(false)} title="Change your monthly contribution"
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)}>Cancel</Button>
            <Button loading={mutation.isPending} onClick={submit}>Save new amount</Button>
          </>
        }>
        <form className="space-y-4" onSubmit={submit} noValidate>
          <ErrorAlert error={mutation.error} />
          <p>
            You now contribute <strong>{formatNaira(data.pending_change?.amount ?? data.amount)}</strong> a month. A new amount applies from next month,
            because this month&apos;s deduction may already be with payroll.
          </p>
          <TextField label="New monthly amount (₦)" required inputMode="decimal" autoFocus
            hint={data.maximum ? `Between ${formatNaira(data.minimum)} and ${formatNaira(data.maximum)}.` : `At least ${formatNaira(data.minimum)}.`}
            {...register('amount', {
              required: 'Enter an amount.',
              validate: (v) => {
                if (Number(v) < Number(data.minimum)) return `The minimum is ${formatNaira(data.minimum)}.`;
                if (data.maximum && Number(v) > Number(data.maximum)) return `The maximum is ${formatNaira(data.maximum)}.`;
                return true;
              },
            })}
            error={errors.amount?.message} />
          <button type="submit" className="hidden" aria-hidden="true" tabIndex={-1} />
        </form>
      </Modal>
    </>
  );
}

function ChristmasSavings() {
  const [year, setYear] = useState(null);
  const query = useQuery({ queryKey: ['me', 'christmas', year], queryFn: () => memberApi.christmas(year), retry: false });

  if (query.isError && query.error?.response?.status === 404) {
    return (
      <Card>
        <CardHeader title="Christmas Savings" />
        <EmptyState icon={TreePine} title="No Christmas Savings yet">Your account opens when the cooperative opens the year's Christmas Savings.</EmptyState>
      </Card>
    );
  }

  return (
    <QueryState query={query}>
      {(data) => (
        <Card>
          <CardHeader
            title={`Christmas Savings ${data.year}`}
            description={`Account ${data.account_number} · contributions from January to October`}
            action={
              data.years.length > 1 && (
                <div className="w-32">
                  <SelectField aria-label="Year" value={data.year} onChange={(e) => setYear(e.target.value)}>
                    {data.years.map((y) => <option key={y} value={y}>{y}</option>)}
                  </SelectField>
                </div>
              )
            }
          />
          <CardBody>
            <ul className="grid grid-cols-2 gap-3 sm:grid-cols-5">
              {data.months.map((key) => {
                const amount = data.contributions[key];
                const paid = Number(amount) > 0;
                return (
                  <li key={key} className={`rounded-lg border px-3 py-2 ${paid ? 'border-emerald-200 bg-emerald-50' : 'border-slate-200 bg-slate-50'}`}>
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{monthLabel(key, true).split(' ')[0]}</p>
                    <p className={`tabular mt-1 text-sm font-bold ${paid ? 'text-emerald-800' : 'text-slate-400'}`}>{paid ? formatNaira(amount) : '—'}</p>
                  </li>
                );
              })}
            </ul>
            <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4">
              <p className="text-sm text-slate-600">
                Expected {formatNaira(data.expected_monthly)} a month · {formatNaira(data.expected_total)} for the year
              </p>
              <p className="text-right">
                <span className="block text-xs font-semibold uppercase text-slate-500">Total</span>
                <span className="tabular text-xl font-bold text-slate-900">{formatNaira(data.total)}</span>
              </p>
            </div>
            {Number(data.paid_out) > 0 && (
              <p className="mt-3 flex items-center gap-2 text-sm text-emerald-700">
                <Info className="h-4 w-4" aria-hidden="true" /> {formatNaira(data.paid_out)} has been paid out to you.
              </p>
            )}
          </CardBody>
        </Card>
      )}
    </QueryState>
  );
}

function OtherSavings({ other }) {
  return (
    <Card>
      <CardHeader title="Other savings" description="Regular and other savings accounts" />
      {other.accounts.length ? (
        <div className="divide-y divide-slate-100">
          {other.accounts.map((account) => <AccountHistory key={account.id} account={account} />)}
        </div>
      ) : (
        <EmptyState title="No other savings accounts" />
      )}
      <CardBody className="flex justify-between border-t border-slate-100 text-sm">
        <span className="font-semibold text-slate-700">Total other savings</span>
        <span className="tabular font-bold">{formatNaira(other.balance)}</span>
      </CardBody>
    </Card>
  );
}

function AccountHistory({ account }) {
  const [open, setOpen] = useState(false);
  const [page, setPage] = useState(1);
  const history = useQuery({ queryKey: ['me', 'savings-tx', account.id, page], queryFn: () => memberApi.savingsTransactions(account.id, page), enabled: open });

  return (
    <div>
      <button type="button" onClick={() => setOpen(!open)} className="flex w-full flex-wrap items-center justify-between gap-3 px-5 py-4 text-left hover:bg-slate-50" aria-expanded={open}>
        <div>
          <p className="font-semibold text-slate-800">{account.product}</p>
          <p className="text-xs text-slate-500">Account {account.account_number}</p>
        </div>
        <div className="text-right">
          <p className="tabular font-bold text-slate-900">{formatNaira(account.balance)}</p>
          <p className="text-xs text-brand-600">{open ? 'Hide history' : 'Show contribution history'}</p>
        </div>
      </button>
      {open && (
        <QueryState query={history}>
          {(data) =>
            data.results.length ? (
              <>
                <Table caption={`${account.product} history`}>
                  <thead><tr><Th>Date</Th><Th>Description</Th><Th align="right">Amount</Th><Th>Status</Th></tr></thead>
                  <tbody className="divide-y divide-slate-100">
                    {data.results.map((t) => (
                      <tr key={t.id}>
                        <Td className="whitespace-nowrap">{formatDate(t.value_date)}</Td>
                        <Td>{t.description || t.type_label}</Td>
                        <Td align="right"><Money value={t.signed_amount} className={t.entry_side === 'CREDIT' ? 'text-emerald-700' : 'text-red-700'} /></Td>
                        <Td><StatusBadge status={t.status} label={t.status_label} /></Td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
                <Pagination page={page} count={data.count} onChange={setPage} />
              </>
            ) : (
              <EmptyState title="No contributions yet" />
            )
          }
        </QueryState>
      )}
    </div>
  );
}
