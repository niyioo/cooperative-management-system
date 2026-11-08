import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Briefcase } from 'lucide-react';
import { memberApi } from '../../api/member';
import { StatusBadge } from '../../components/ui/Badge';
import { Card, CardBody, CardHeader } from '../../components/ui/Card';
import EmptyState from '../../components/ui/EmptyState';
import PageHeader from '../../components/ui/PageHeader';
import QueryState from '../../components/ui/QueryState';
import { Money, Table, Td, Th } from '../../components/ui/Table';
import { formatDate, formatNaira } from '../../lib/format';

export default function Investments() {
  const query = useQuery({ queryKey: ['me', 'investments'], queryFn: memberApi.investments });
  const dividends = useQuery({ queryKey: ['me', 'dividends'], queryFn: memberApi.dividends });

  return (
    <div className="space-y-6">
      <PageHeader title="My Investments" description="Your investment accounts and the dividends they earn." />
      <QueryState query={query}>
        {(data) => (
          <>
            <Card>
              <CardBody className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-slate-700">Total investment principal</p>
                  <p className="text-xs text-slate-500">Across all your investment accounts</p>
                </div>
                <p className="tabular text-2xl font-bold text-slate-900">{formatNaira(data.total_principal)}</p>
              </CardBody>
            </Card>
            {data.accounts.length ? (
              data.accounts.map((account) => <InvestmentAccount key={account.id} account={account} />)
            ) : (
              <Card><EmptyState icon={Briefcase} title="No investments yet">Ask the cooperative office about investment schemes such as share capital.</EmptyState></Card>
            )}
          </>
        )}
      </QueryState>
      <QueryState query={dividends}>
        {(data) =>
          data.latest && (
            <Card>
              <CardHeader title={`${data.latest.financial_year} dividend`} />
              <CardBody>
                <dl className="grid gap-4 sm:grid-cols-4">
                  <div><dt className="text-xs text-slate-500">Investment year</dt><dd className="font-semibold">{data.latest.financial_year}</dd></div>
                  <div><dt className="text-xs text-slate-500">Dividend rate</dt><dd className="font-semibold">{Number(data.latest.rate)}%</dd></div>
                  <div><dt className="text-xs text-slate-500">Dividend amount</dt><dd className="tabular font-semibold">{formatNaira(data.latest.net_amount)}</dd></div>
                  <div><dt className="text-xs text-slate-500">Dividend status</dt><dd><StatusBadge status={data.latest.status} /></dd></div>
                </dl>
              </CardBody>
            </Card>
          )
        }
      </QueryState>
    </div>
  );
}

function InvestmentAccount({ account }) {
  const [open, setOpen] = useState(false);
  const history = useQuery({ queryKey: ['me', 'investment-tx', account.id], queryFn: () => memberApi.investmentTransactions(account.id), enabled: open });
  return (
    <Card>
      <CardHeader
        title={account.product}
        description={`Account ${account.account_number} · opened ${formatDate(account.opened_on)}`}
        action={<div className="text-right"><p className="tabular text-lg font-bold">{formatNaira(account.principal)}</p><StatusBadge status={account.status} /></div>}
      />
      <CardBody>
        <button type="button" className="text-sm font-semibold text-brand-600 hover:underline" onClick={() => setOpen(!open)} aria-expanded={open}>
          {open ? 'Hide investment history' : 'Show investment history'}
        </button>
      </CardBody>
      {open && (
        <QueryState query={history}>
          {(data) => (
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
          )}
        </QueryState>
      )}
    </Card>
  );
}
