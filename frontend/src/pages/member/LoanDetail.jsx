import { useQuery } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { memberApi } from '../../api/member';
import { Alert } from '../../components/ui/Alert';
import { StatusBadge } from '../../components/ui/Badge';
import { Card, CardHeader } from '../../components/ui/Card';
import EmptyState from '../../components/ui/EmptyState';
import QueryState from '../../components/ui/QueryState';
import StatCard from '../../components/ui/StatCard';
import { Money, Table, Td, Th } from '../../components/ui/Table';
import { formatDate, formatNaira } from '../../lib/format';

const RATE_BASIS = { PER_ANNUM: 'per year', PER_MONTH: 'per month', PER_LOAN: 'for the whole term' };

export default function LoanDetail() {
  const { id } = useParams();
  const loan = useQuery({ queryKey: ['me', 'loan', id], queryFn: () => memberApi.loan(id) });
  const repayments = useQuery({ queryKey: ['me', 'loan-repayments', id], queryFn: () => memberApi.loanRepayments(id) });

  return (
    <QueryState query={loan}>
      {(data) => (
        <div className="space-y-6">
          <div>
            <Link to="/member/loans" className="inline-flex items-center gap-1 text-sm font-medium text-brand-600 hover:underline">
              <ArrowLeft className="h-4 w-4" aria-hidden="true" /> My loans
            </Link>
            <div className="mt-2 flex flex-wrap items-center gap-3">
              <h1 className="text-2xl font-bold text-slate-900">{data.reference}</h1>
              <StatusBadge status={data.status} label={data.status_label} />
            </div>
            <p className="mt-1 text-sm text-slate-500">
              {data.product_name} · {Number(data.interest_rate)}% {RATE_BASIS[data.interest_rate_basis]} ({data.interest_method === 'FLAT' ? 'flat' : 'reducing balance'})
              · {data.term_months} months · disbursed {formatDate(data.disbursed_on)}
            </p>
          </div>

          {Number(data.arrears.amount) > 0 && (
            <Alert tone="warning" title="You have overdue repayments">
              {formatNaira(data.arrears.amount)} across {data.arrears.instalments} instalment(s), the oldest due {formatDate(data.arrears.oldest_due_date)}.
            </Alert>
          )}

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
            <StatCard label="Loan amount" value={formatNaira(data.principal)} />
            <StatCard label="Interest" value={formatNaira(data.total_interest)} hint={data.interest_collection === 'UPFRONT' ? 'Deducted at disbursement' : 'Repaid with instalments'} />
            <StatCard label="Amount repaid" value={formatNaira(data.amount_repaid)} tone="green" />
            <StatCard label="Outstanding balance" value={formatNaira(data.outstanding)} tone="amber" />
            <StatCard label="Next repayment" value={data.next_instalment ? formatNaira(data.next_instalment.remaining) : '—'}
              hint={data.next_instalment ? `Due ${formatDate(data.next_instalment.due_date)}` : 'Fully repaid'} tone="slate" />
          </div>

          <Card>
            <CardHeader title="Repayment schedule" description="Instalments fall due at the end of each month." />
            <Table caption="Repayment schedule">
              <thead>
                <tr><Th>#</Th><Th>Due date</Th><Th align="right">Principal</Th><Th align="right">Interest</Th><Th align="right">Total</Th><Th align="right">Paid</Th><Th>Status</Th></tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.schedule.map((row) => (
                  <tr key={row.number}>
                    <Td>{row.number}</Td>
                    <Td className="whitespace-nowrap">{formatDate(row.due_date)}</Td>
                    <Td align="right"><Money value={row.principal_due} /></Td>
                    <Td align="right"><Money value={row.interest_due} /></Td>
                    <Td align="right"><Money value={row.total_due} className="font-semibold" /></Td>
                    <Td align="right"><Money value={row.paid} /></Td>
                    <Td><StatusBadge status={row.status} /></Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </Card>

          <Card>
            <CardHeader title="Repayment history" />
            <QueryState query={repayments}>
              {(history) =>
                history.results.length ? (
                  <Table caption="Repayment history">
                    <thead>
                      <tr><Th>Date</Th><Th>Reference</Th><Th align="right">Amount</Th><Th align="right">Principal</Th><Th align="right">Interest</Th><Th>Status</Th></tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {history.results.map((r) => (
                        <tr key={r.id}>
                          <Td className="whitespace-nowrap">{formatDate(r.value_date)}</Td>
                          <Td>
                            <p>{r.reference}</p>
                            <p className="text-xs text-slate-500">{r.description}</p>
                          </Td>
                          <Td align="right"><Money value={r.amount} className="font-semibold" /></Td>
                          <Td align="right"><Money value={r.principal_component} /></Td>
                          <Td align="right"><Money value={r.interest_component} /></Td>
                          <Td><StatusBadge status={r.status} /></Td>
                        </tr>
                      ))}
                    </tbody>
                  </Table>
                ) : (
                  <EmptyState title="No repayments yet" />
                )
              }
            </QueryState>
          </Card>
        </div>
      )}
    </QueryState>
  );
}
