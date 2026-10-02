import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Info, TreePine } from 'lucide-react';
import { memberApi } from '../../api/member';
import { Alert } from '../../components/ui/Alert';
import { StatusBadge } from '../../components/ui/Badge';
import { Card, CardBody, CardHeader } from '../../components/ui/Card';
import EmptyState from '../../components/ui/EmptyState';
import PageHeader from '../../components/ui/PageHeader';
import Pagination from '../../components/ui/Pagination';
import QueryState from '../../components/ui/QueryState';
import { SelectField } from '../../components/ui/Field';
import { Money, Table, Td, Th } from '../../components/ui/Table';
import { formatDate, formatNaira, monthLabel } from '../../lib/format';

export default function Savings() {
  const savings = useQuery({ queryKey: ['me', 'savings'], queryFn: memberApi.savings });
  return (
    <div className="space-y-6">
      <PageHeader title="My Savings" description="Your Christmas Savings and other savings, kept separately." />
      <Alert tone="info">
        Savings are shown for your information. Withdrawals are not available through the portal; speak to the cooperative office about your savings.
      </Alert>
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
