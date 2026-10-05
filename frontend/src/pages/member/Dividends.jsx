import { useQuery } from '@tanstack/react-query';
import { Gift } from 'lucide-react';
import { memberApi } from '../../api/member';
import { StatusBadge } from '../../components/ui/Badge';
import { Card, CardHeader } from '../../components/ui/Card';
import EmptyState from '../../components/ui/EmptyState';
import PageHeader from '../../components/ui/PageHeader';
import QueryState from '../../components/ui/QueryState';
import StatCard from '../../components/ui/StatCard';
import { Money, Table, Td, Th } from '../../components/ui/Table';
import { formatDate, formatNaira } from '../../lib/format';

export default function Dividends() {
  const query = useQuery({ queryKey: ['me', 'dividends'], queryFn: memberApi.dividends });
  return (
    <div className="space-y-6">
      <PageHeader title="My Dividends" description="Dividends are worked out on your eligible investments and paid each December." />
      <QueryState query={query}>
        {(data) => (
          <>
            <div className="grid gap-4 sm:grid-cols-3">
              <StatCard label="Latest dividend" icon={Gift} tone="green" value={data.latest ? formatNaira(data.latest.net_amount) : '—'}
                hint={data.latest ? `${data.latest.financial_year} · ${data.latest.status.toLowerCase()}` : 'Not yet published'} />
              <StatCard label="Latest rate" value={data.latest ? `${Number(data.latest.rate)}%` : '—'} />
              <StatCard label="Total dividends paid" value={formatNaira(data.total_paid)} tone="slate" />
            </div>
            <Card>
              <CardHeader title="Dividend history" />
              {data.history.length ? (
                <Table caption="Dividend history">
                  <thead>
                    <tr><Th>Year</Th><Th align="right">Investment basis</Th><Th align="right">Rate</Th><Th align="right">Gross</Th><Th align="right">Amount</Th><Th>Status</Th><Th>Paid on</Th></tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {data.history.map((d) => (
                      <tr key={d.cycle_reference}>
                        <Td className="font-semibold">{d.financial_year}</Td>
                        <Td align="right"><Money value={d.basis_amount} /></Td>
                        <Td align="right">{Number(d.rate)}%</Td>
                        <Td align="right"><Money value={d.gross_amount} /></Td>
                        <Td align="right"><Money value={d.net_amount} className="font-semibold" /></Td>
                        <Td><StatusBadge status={d.status} /></Td>
                        <Td className="whitespace-nowrap">{formatDate(d.paid_at)}</Td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              ) : (
                <EmptyState icon={Gift} title="No dividends yet">Your dividend appears here once the cooperative publishes the year's results.</EmptyState>
              )}
            </Card>
          </>
        )}
      </QueryState>
    </div>
  );
}
